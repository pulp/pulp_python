from pulpcore.plugin.cache import CacheKeys, SyncContentCache
from pulpcore.plugin.util import cache_key

MEDIA_TYPE_KEY = "media_type"


class PythonApiCache(SyncContentCache):
    """
    Cache for the Simple API.

    Keys on the negotiated media type so HTML and JSON are cached separately,
    including when the same Accept header is used with `?format=json`.
    """

    def __init__(self, base_key=None):
        keys = (CacheKeys.path, CacheKeys.method, MEDIA_TYPE_KEY)
        super().__init__(base_key=base_key, keys=keys)

    def make_key(self, request):
        all_keys = {
            CacheKeys.path: request.path,
            CacheKeys.method: request.method,
            MEDIA_TYPE_KEY: getattr(request, "accepted_media_type", "") or "",
        }
        return ":".join(all_keys[k] for k in self.keys)


def find_base_path_cached(request, cached):
    """
    Resolve the distribution base_path for use as the Redis cache base_key.
    """
    path = request.resolver_match.kwargs["path"]
    return cache_key(path)
