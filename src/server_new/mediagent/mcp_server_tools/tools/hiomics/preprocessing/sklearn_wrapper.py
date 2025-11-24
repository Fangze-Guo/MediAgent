from pathlib import Path
import numpy as np
import pickle
from loguru import logger
from sklearn.pipeline import Pipeline as SklearnPipeline
from sklearn.base import BaseEstimator, TransformerMixin
import pandas as pd

from hiomics.utils import create_object, load_params

from . import CFG_DIR

__all__ = ["StandardScaler", "MinMaxScaler", "Pipeline"]

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.linear_model import LassoCV


class CorrelationSelector(BaseEstimator, TransformerMixin):
    """
    基于特征间相关性的特征选择器，符合sklearn estimator规范
    
    参数:
    method : str, default='spearman'
        相关性计算方法 ('pearson' 或 'spearman')
    k : int, default=None
        要保留的特征数量，如果指定了k，则会忽略threshold
    threshold : float, default=0.75
        相关性阈值，超过此阈值的特征会被剔除
    """
    
    def __init__(self, method='spearman', k=None, threshold=0.75):
        self.method = method
        self.k = k
        self.threshold = threshold
        
    def fit(self, X, y=None):
        """拟合选择器"""
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        
        # 计算相关性矩阵
        corr_matrix = X_df.corr(method=self.method)
        upper = corr_matrix.where(np.triu(np.ones(corr_matrix.shape), k=1).astype(bool))
        
        if self.k is not None:
            # 基于k选择特征
            # 计算每个特征与其他特征的平均相关性
            avg_corr = upper.abs().mean(axis=0, skipna=True)
            # 选择平均相关性最低的k个特征
            self.selected_features_ = avg_corr.nsmallest(self.k).index.tolist()
        else:
            # 基于threshold选择特征
            to_drop = [column for column in upper.columns if any(upper[column].abs() > self.threshold)]
            self.selected_features_ = [col for col in X_df.columns if col not in to_drop]
        
        # print(f"CorrelationSelector: Selected {len(self.selected_features_)} features")
        return self
    
    def transform(self, X):
        """转换数据"""
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        return X_df[self.selected_features_].values
    
    def get_feature_names_out(self, input_features=None):
        """获取输出特征名称"""
        return np.array([f"correlation__{feat}" for feat in self.selected_features_])


class LassoSelector(BaseEstimator, TransformerMixin):
    """
    基于LASSO的特征选择器，符合sklearn estimator规范
    
    参数:
    cv : int, default=5
        交叉验证折数
    random_state : int, default=None
        随机种子
    """
    
    def __init__(self, cv=5, random_state=None):
        self.cv = cv
        self.random_state = random_state
        
    def fit(self, X, y):
        """拟合选择器"""
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        
        # 使用LASSO进行特征选择
        lasso = LassoCV(cv=self.cv, random_state=self.random_state)
        lasso.fit(X_df, y)
        
        # 获取非零系数对应的特征
        self.selected_features_ = X_df.columns[lasso.coef_ != 0].tolist()
        self.lasso_model_ = lasso
        
        # print(f"LassoSelector: Selected {len(self.selected_features_)} features")
        return self
    
    def transform(self, X):
        """转换数据"""
        X_df = pd.DataFrame(X) if not isinstance(X, pd.DataFrame) else X
        return X_df[self.selected_features_].values
    
    def get_feature_names_out(self, input_features=None):
        """获取输出特征名称"""
        return np.array([f"lasso__{feat}" for feat in self.selected_features_])

class Debug(BaseEstimator, TransformerMixin):
    def __init__(self, step_name=None):
        self.step_name = step_name

    def transform(self, X):
        logger.info(f"[Shape] {self.step_name}: {X.shape[1]}")
        return X

    def fit(self, X, y=None, **fit_params):
        return self

    def fit_transform(self, X, y=None, **fit_params):
        self.fit(X, y, **fit_params)
        return self.transform(X)

    def get_feature_names_out(self, input_features=None):
        return input_features

class SklearnPreprocessingWrapper:
    def __init__(self, method, params=None):
        self.class_path = f"sklearn.preprocessing.{method}"
        self.params = params
        self.is_trained = False

    def fit(self, X: np.ndarray):
        model = create_object(self.class_path, self.params)
        model.fit(X)
        self.model = model
        self.is_trained = True

    def save(self, pkl_path: str):
        pkl_path = Path(pkl_path)
        pkl_path.parent.mkdir(parents=True, exist_ok=True)
        pickle.dump(self, open(pkl_path, "wb"))

    def predict(self, X: np.ndarray):
        assert self.is_trained, "Model is not trained"
        return self.model.transform(X)

    @classmethod
    def load(cls, pkl_path: str):
        pkl_path = Path(pkl_path)
        return pickle.load(open(pkl_path, "rb"))

class StandardScaler(SklearnPreprocessingWrapper):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "StandardScaler.yaml"
            logger.info(f"Using default params for StandardScaler: {params}")
        super().__init__(method="StandardScaler", params=params)

class MinMaxScaler(SklearnPreprocessingWrapper):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "MinMaxScaler.yaml"
            logger.info(f"Using default params for MinMaxScaler: {params}")
        params = load_params(params)
        if "feature_range" in params:
            params["feature_range"] = tuple(params["feature_range"])
        super().__init__(method="MinMaxScaler", params=params)

class Pipeline:
    def __init__(self, params=None):
        if params is None:
            raise ValueError("params is required")
        
        self.params = load_params(params)
        self.is_trained = False
        self._build_pipeline()

    def _build_pipeline(self):
        """Build the sklearn pipeline from configuration"""
        steps = []
        for step_config in self.params["steps"]:
            print(step_config)
            step_name = step_config["name"]
            method = step_config["method"]
            step_params = step_config.get("params", None)
            
            # Handle special parameter conversions
            if step_params and "feature_range" in step_params:
                step_params["feature_range"] = tuple(step_params["feature_range"])
            
            # Create the step object
            step_obj = create_object(method, step_params)
            steps.append((step_name, step_obj))
            debug_obj = Debug(f"After {step_name}")
            steps.append((f"after_{step_name}", debug_obj))
        
        logger.info(f"Building pipeline with {steps}")
        self.model = SklearnPipeline(steps)

    def fit(self, X: np.ndarray):
        """Fit the pipeline on training data"""
        self.model.fit(X)
        self.is_trained = True

    def predict(self, X: np.ndarray):
        """Transform data using the fitted pipeline"""
        assert self.is_trained, "Pipeline is not trained"
        return self.model.transform(X)

    def save(self, pkl_path: str):
        """Save the pipeline to a pickle file"""
        pkl_path = Path(pkl_path)
        pkl_path.parent.mkdir(parents=True, exist_ok=True)
        pickle.dump(self, open(pkl_path, "wb"))

    @classmethod
    def load(cls, pkl_path: str):
        """Load a pipeline from a pickle file"""
        pkl_path = Path(pkl_path)
        return pickle.load(open(pkl_path, "rb"))

if __name__ == "__main__":
    for method in __all__:
        scaler = globals()[method]()
        scaler.fit(np.random.rand(10, 10))
        scaler.predict(np.random.rand(10, 10))