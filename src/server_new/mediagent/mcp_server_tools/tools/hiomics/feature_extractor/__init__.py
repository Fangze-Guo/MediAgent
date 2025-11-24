from typing import Dict, Any, Union
import pandas as pd
from easydict import EasyDict as edict
from . import radiomics_wrapper

METHODS = {
    "radiomics": radiomics_wrapper.extract_radiomics_batch,
}

def run(method: str, 
        params: Union[Dict[str, Any], str],
        df: pd.DataFrame,
        **kwargs,
        ) -> edict:
    assert method in METHODS, f"Method {method} not found"
    method = METHODS[method]
    return method(params, df, **kwargs)