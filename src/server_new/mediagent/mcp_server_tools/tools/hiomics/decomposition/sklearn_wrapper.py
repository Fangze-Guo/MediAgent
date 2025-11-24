from pathlib import Path
import numpy as np
import pickle
from loguru import logger
import sklearn
import sklearn.feature_selection
import pandas as pd

from hiomics.utils import create_object, load_params

FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
CFG_DIR = ROOT / "configs/decomposition"

__all__ = ["SelectKBest", "PCA", "PCA1"]

class SklearnDecompositionWrapper:
    def __init__(self, class_path, params=None):
        self.class_path = class_path
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

class SelectKBest(SklearnDecompositionWrapper):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "SelectKBest.yaml"
            logger.info(f"Using default params for SelectKBest: {params}")

        params = load_params(params)
        if "score_func" in params:
            params["score_func"] = getattr(sklearn.feature_selection, params["score_func"])
        else:
            logger.info("No score_func provided, using f_classif")
            params["score_func"] = sklearn.feature_selection.f_classif

        if "k" in params:
            params["k"] = int(params["k"])
        else:
            logger.info("No k provided, using 20")
            params["k"] = 20
        
        super().__init__(class_path="sklearn.feature_selection.SelectKBest", params=params)

    def fit(self, X: np.ndarray, y=None):
        model = create_object(self.class_path, self.params)
        if y is None:
            logger.debug("No target provided, using dummy target with random state 0")
            rng = np.random.default_rng(0)
            y = rng.random(len(X))
            model.fit(X, y)
        else:
            model.fit(X, y)
        self.model = model
        self.is_trained = True

    def predict(self, X: np.ndarray):
        new_X = super().predict(X)
        columns = self.model.get_feature_names_out()
        return pd.DataFrame(new_X, columns=columns)

class PCA(SklearnDecompositionWrapper):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "PCA.yaml"
            logger.info(f"Using default params for PCA: {params}")
        params = load_params(params)
        super().__init__(class_path="sklearn.decomposition.PCA", params=params)

    def predict(self, X: np.ndarray):
        new_X = super().predict(X)
        columns = [f"PCA_{i+1}" for i in range(new_X.shape[1])]
        return pd.DataFrame(new_X, columns=columns)

class PCA1(PCA):
    def __init__(self, params=None):
        super().__init__(params=params)
        self.params["n_components"] = 1
        logger.info(f"In PCA1, n_components is set to 1")

if __name__ == "__main__":
    import pandas as pd
    for method in __all__:
        scaler = globals()[method]()
        feat_df = pd.DataFrame(np.random.rand(100, 100), columns=[f"feat_{i}" for i in range(100)])
        scaler.fit(feat_df)
        print(scaler.predict(feat_df).columns)