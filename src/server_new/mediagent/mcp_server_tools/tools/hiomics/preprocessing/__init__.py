from pathlib import Path

FILE = Path(__file__).resolve()
ROOT = FILE.parents[1]
CFG_DIR = ROOT / "configs/preprocessing"


import hiomics.preprocessing.sklearn_wrapper as sklearn_wrapper

METHOD = {
    "StandardScaler": sklearn_wrapper.StandardScaler,
    "MinMaxScaler": sklearn_wrapper.MinMaxScaler,
    "Pipeline": sklearn_wrapper.Pipeline,
}


def get_method(method):
    assert method in METHOD, f"Method {method} not found"
    return METHOD[method]