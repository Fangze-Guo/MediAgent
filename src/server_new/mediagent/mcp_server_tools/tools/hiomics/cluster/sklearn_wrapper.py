from pathlib import Path
from loguru import logger
import numpy as np
import pickle
import sklearn

from hiomics.utils import create_object, load_params
from sklearn.metrics import calinski_harabasz_score


FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
CFG_DIR = ROOT / "configs/cluster"


def gmm_bic_score(estimator, X):
    return -estimator.bic(X)

def aic_score(estimator, X):
    return -estimator.aic(X)

def ch_score(estimator, X):
    return calinski_harabasz_score(X, estimator.predict(X))

SCORE_METHOD = {
    "CalinskiHarabasz": ch_score,
    "AIC": aic_score,
    "BIC": gmm_bic_score,
}
__all__ = ["KMeans", "GaussianMixture"]

class SklearnClusterWrapper:
    def __init__(self, class_path=None, params=None, n_clusters_key="n_clusters"):
        self.class_path = class_path
        self.params = load_params(params)
        self.n_clusters_key = n_clusters_key

        self.n_clusters = self.params.get("n_clusters", None)
        if n_clusters_key != "n_clusters" and "n_clusters" in self.params:
            del self.params["n_clusters"]

        if self.n_clusters is None:
            n_clusters_range = self.params.get("n_clusters_range", None)
            if n_clusters_range is None:
                logger.error("If n_clusters is not provided, n_clusters_range must be provided")
                raise ValueError("n_clusters_range is not provided")
            self.n_clusters_range = n_clusters_range
            if "n_clusters_range" in self.params:
                del self.params["n_clusters_range"]

            score_method = self.params.get("n_clusters_score_method", None)
            if score_method is None:
                logger.info("No score_func provided, using CalinskiHarabasz")
                score_method = "CalinskiHarabasz"
            if score_method not in SCORE_METHOD:
                logger.error(f"Score method {score_method} not found")
                raise ValueError(f"Score method {score_method} not found")
            self.score_func = SCORE_METHOD[score_method]
            if "n_clusters_score_method" in self.params:
                del self.params["n_clusters_score_method"]

    def fit(self, X: np.ndarray):
        n_clusters = self.n_clusters
        if n_clusters is None:
            n_clusters_range = self.n_clusters_range
            models, scores = [], []
            for i in range(n_clusters_range[0], n_clusters_range[1] + 1):
                model = create_object(self.class_path, self.params, update_params={self.n_clusters_key: i})
                model.fit(X)
                models.append(model)
                scores.append(self.score_func(model, X))
                logger.debug(f"n_clusters: {i}, score: {scores[-1]}")
            logger.info(f"n_clusters will be set to {n_clusters_range[0] + np.argmax(scores)} after searching in {n_clusters_range[0]} ~ {n_clusters_range[1]}")
            self.model = models[np.argmax(scores)]
        else:
            self.model = create_object(self.class_path, self.params, update_params={self.n_clusters_key: n_clusters})
            self.model.fit(X)
        self.is_trained = True

    def predict(self, X: np.ndarray):
        assert self.is_trained, "Model is not trained"
        return self.model.predict(X) + 1 # +1 because the labels start from 0

    def save(self, pkl_path: str):
        pkl_path = Path(pkl_path)
        pkl_path.parent.mkdir(parents=True, exist_ok=True)
        pickle.dump(self, open(pkl_path, "wb"))

    @classmethod
    def load(cls, pkl_path: str):
        pkl_path = Path(pkl_path)
        return pickle.load(open(pkl_path, "rb"))

class KMeans(SklearnClusterWrapper):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "KMeans.yaml"
            logger.info(f"Using default params for KMeans: {params}")
        super().__init__(class_path="sklearn.cluster.KMeans", params=params, n_clusters_key="n_clusters")

class GaussianMixture(SklearnClusterWrapper):
    def __init__(self, params=None):
        if params is None:
            params = CFG_DIR / "GaussianMixture.yaml"
            logger.info(f"Using default params for GaussianMixture: {params}")
        super().__init__(class_path="sklearn.mixture.GaussianMixture", params=params, n_clusters_key="n_components")


if __name__ == "__main__":
    import pandas as pd
    import sklearn.datasets
    for method in __all__:
        model = globals()[method]()
        X, y = sklearn.datasets.make_blobs(n_samples=1000, n_features=10, centers=5, random_state=0)
        model.fit(X)
        print(np.unique(model.predict(X)))