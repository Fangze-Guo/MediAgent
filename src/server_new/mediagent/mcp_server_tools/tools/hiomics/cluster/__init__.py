import hiomics.cluster.sklearn_wrapper as sklearn_wrapper

METHOD = {
    "KMeans": sklearn_wrapper.KMeans,
    "GaussianMixture": sklearn_wrapper.GaussianMixture,
}


def get_method(method):
    assert method in METHOD, f"Method {method} not found"
    return METHOD[method]