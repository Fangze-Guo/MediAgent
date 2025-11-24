import pickle
import numpy as np
from pathlib import Path
import sklearn
import sklearn.feature_selection
from sklearn.metrics import calinski_harabasz_score
import pandas as pd
from loguru import logger
from . import create_object

class SklearnWrapper:
    def __init__(self, class_path=None, params=None):
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
    
class SklearnPreprocessingWrapper(SklearnWrapper):
    def __init__(self, name):
        super().__init__(class_path=f"sklearn.preprocessing.{name}")

class SklearnClusterWrapper(SklearnWrapper):
    def __init__(self, class_path=None, params=None, n_clusters_key="n_clusters", name=None):
        if name is not None and class_path is not None:
            raise ValueError("Cannot specify both name and class_path")
        if name is None and class_path is None:
            raise ValueError("Must specify either name or class_path")
        if name is not None:
            # Try to find the clustering algorithm in sklearn.cluster first
            try:
                getattr(sklearn.cluster, name)
                class_path = f"sklearn.cluster.{name}"
            except AttributeError:
                # If not found in sklearn.cluster, try sklearn.mixture
                try:
                    getattr(sklearn.mixture, name)
                    class_path = f"sklearn.mixture.{name}"
                    # For mixture models, the parameter is usually n_components
                    n_clusters_key = "n_components"
                except AttributeError:
                    raise ValueError(f"Clustering algorithm '{name}' not found in sklearn.cluster or sklearn.mixture")

        super().__init__(class_path, params)
        self.n_clusters_key = n_clusters_key

    def fit(self, X: np.ndarray, n_clusters=None, n_clusters_range=[3, 10]):
        if n_clusters is None:
            models, scores = [], []
            for i in range(n_clusters_range[0], n_clusters_range[1] + 1):
                model = create_object(self.class_path, self.params, update_params={self.n_clusters_key: i})
                model.fit(X)
                models.append(model)
                scores.append(calinski_harabasz_score(X, model.predict(X)))
                logger.debug(f"n_clusters: {i}, calinski_harabasz_score: {scores[-1]}")
            logger.info(f"n_clusters will be set to {n_clusters_range[0] + np.argmax(scores)} after searching in {n_clusters_range[0]} ~ {n_clusters_range[1]}")
            self.model = models[np.argmax(scores)]
        else:
            self.model = create_object(self.class_path, self.params, update_params={self.n_clusters_key: n_clusters})
            self.model.fit(X)
        self.is_trained = True

    def predict(self, X: np.ndarray):
        assert self.is_trained, "Model is not trained"
        return self.model.predict(X)

class SklearnFeatureSelectionWrapper(SklearnWrapper):
    def __init__(self, name, params=None):
        super().__init__(class_path=f"sklearn.feature_selection.{name}", params=params)

class SelectKBestWrapper(SklearnWrapper):
    def __init__(self, params=None):
        super().__init__(class_path="sklearn.feature_selection.SelectKBest", params=params)
        self.update_params = {
            "score_func": sklearn.feature_selection.f_classif,
        }

    def fit(self, X: np.ndarray, y=None):
        model = create_object(self.class_path, self.params, update_params=self.update_params)
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
