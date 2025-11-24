from typing import Dict, Any, Union
import pandas as pd

from . import slic

METHODS = {
    "SLIC": slic.run_batch,
}

def run(method: str, 
        params: Union[Dict[str, Any], str],
        df: pd.DataFrame,
        output_dir: str,
        **kwargs,
        ) -> pd.DataFrame:
    assert method in METHODS, f"Method {method} not found"
    method = METHODS[method]
    return method(params, df, output_dir, **kwargs)