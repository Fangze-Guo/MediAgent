from pathlib import Path
import pandas as pd
import pickle


class PathData:
    def __init__(self, csv_path: str, base_dir: str = None, id_column: str = "ID", image_column: str = "image_path", mask_column: str = "mask_path"):
        self.csv_path = Path(csv_path)
        self.base_dir = Path(base_dir) if base_dir is not None else None
        self.id_column = id_column
        self.image_column = image_column
        self.mask_column = mask_column
        self.df = pd.read_csv(self.csv_path)
        assert self.df[id_column].is_unique, f"ID column {id_column} is not unique"

    def get_paths(self, column: str):
        if self.base_dir is not None:
            paths = [Path(self.base_dir) / path for path in self.df[column].tolist()]
        else:
            paths = [Path(path) for path in self.df[column].tolist()]
        return paths

    def get_images(self):
        return self.get_paths(self.image_column)

    def get_masks(self):
        return self.get_paths(self.mask_column)

    def new_images(self):
        return self.df.apply(lambda x: Path("data") / x[self.id_column] / "image.nii.gz", axis=1)

    def new_masks(self):
        return self.df.apply(lambda x: Path("data") / x[self.id_column] / "mask.nii.gz", axis=1)

    def set_images(self, images):
        self.df[self.image_column] = images
    
    def set_masks(self, masks):
        self.df[self.mask_column] = masks

    @classmethod
    def from_pkl(cls, pkl_path: str):
        with open(pkl_path, "rb") as f:
            return pickle.load(f)

    def to_pkl(self, pkl_path: str):
        with open(pkl_path, "wb") as f:
            pickle.dump(self, f)

    def to_kwargs(self):
        return {
            "csv_path": str(self.csv_path),
            "base_dir": str(self.base_dir) if self.base_dir is not None else None,
            "id_column": str(self.id_column),
            "image_column": str(self.image_column),
            "mask_column": str(self.mask_column),
        }

    def save(self, data_dir: Path):
        self.df.to_csv(data_dir / "data.csv", index=False)
        self.csv_path = "data.csv"
        self.base_dir = data_dir
        self.to_pkl(data_dir / "data.pkl")


class FeatureData:
    def __init__(self, csv_path: str, feature_columns: list, id_column: str = "FID"):
        self.csv_path = str(csv_path)
        self.id_column = id_column
        self.feature_columns = feature_columns
        self.df = pd.read_csv(self.csv_path)
        assert self.df[id_column].is_unique, f"ID column {id_column} is not unique"
        assert all(col in self.df.columns for col in feature_columns), f"Feature columns {feature_columns} not found in {self.csv_path}"

    def to_kwargs(self):
        return {
            "csv_path": str(self.csv_path),
            "id_column": str(self.id_column),
            "feature_columns": list(self.feature_columns),
        }

    def get_features(self):
        return self.df[self.feature_columns].copy()

    def set_features(self, features):
        if isinstance(features, pd.DataFrame):
            for col in self.feature_columns:
                self.df[col] = features[col]
        elif isinstance(features, np.ndarray):
            assert features.shape == self.df[self.id_column].shape, f"Features shape {features.shape} does not match ID shape {self.df[self.id_column].shape}"
            self.df[self.feature_columns] = features
        else:
            raise ValueError(f"Invalid features type: {type(features)}")

    def to_pkl(self, pkl_path: str):
        with open(pkl_path, "wb") as f:
            pickle.dump(self, f)

    def save(self, data_dir: Path):
        self.df.to_csv(data_dir / "data.csv", index=False)
        self.csv_path = "data.csv"
        self.to_pkl(data_dir / "data.pkl")


