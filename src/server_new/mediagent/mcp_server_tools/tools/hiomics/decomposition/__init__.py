import hiomics.decomposition.sklearn_wrapper as sklearn_wrapper

METHOD = {
    "SelectKBest": sklearn_wrapper.SelectKBest,
    "PCA": sklearn_wrapper.PCA,
    "PCA1": sklearn_wrapper.PCA1,
}


def get_method(method):
    assert method in METHOD, f"Method {method} not found"
    return METHOD[method]