from hiomics.subregion_clustering import base
from easydict import EasyDict as edict
from pathlib import Path
from typing import Dict, Any, Union

METHODS = {
    "Default": base.subregion_clustering,
}

def run(method: str, 
        args: Union[Dict[str, Any], str],
        sv_feat: edict,
        output_dir: Path,
        **kwargs,
        ) -> edict:
    assert method in METHODS, f"Method {method} not found"
    method = METHODS[method]
    return method(args, sv_feat, output_dir, **kwargs)