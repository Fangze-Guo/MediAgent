import importlib
import yaml
import json
from pathlib import Path
from .helper import generate_spatial_bounding_box

def load_params(params):
    if isinstance(params, (str, Path)):
        params = str(params)
        if params.endswith(".yaml"):
            return yaml.load(open(params, "r"), Loader=yaml.FullLoader)
        elif params.endswith(".json"):
            return json.load(open(params, "r"))
        else:
            raise ValueError(f"Unsupported params type: {params}")
    elif isinstance(params, dict):
        return params
    else:
        raise ValueError(f"Unsupported params type: {type(params)}")


def create_object(class_path, params=None, update_params=None):
    module_name, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    if not params is None:
        params = load_params(params)

        if update_params is not None:
            params.update(update_params)

        return cls(**params)
    return cls()


from . import io
from . import parallel
from . import sklearn_wrapper