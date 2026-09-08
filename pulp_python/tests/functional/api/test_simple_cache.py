from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import pytest
import requests

from pulp_python.tests.functional.constants import (
    PYPI_SIMPLE_V1_HTML,
    PYPI_SIMPLE_V1_JSON,
    PYPI_TEXT_HTML,
    PYTHON_SM_PROJECT_SPECIFIER,
)


@pytest.fixture
def skip_without_cache(pulp_settings):
    """
    Skip test if server-side caching is not enabled.
    """
    if not pulp_settings.CACHE_ENABLED:
        pytest.skip("CACHE_ENABLED is not set")


@pytest.fixture
def synced_distro(
    skip_without_cache,
    python_remote_factory,
    python_repo_with_sync,
    python_distribution_factory,
):
    """
    Sync a repo and create a distribution for cache tests.
    """
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    return python_distribution_factory(repository=repo)


@pytest.fixture
def synced_distro_no_cache(
    python_remote_factory,
    python_repo_with_sync,
    python_distribution_factory,
):
    """
    Sync a repo and create a distribution (no cache requirement).
    """
    remote = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER)
    repo = python_repo_with_sync(remote)
    return python_distribution_factory(repository=repo)


@pytest.mark.parallel
def test_simple_cache_hit_miss_and_headers(synced_distro):
    """
    First request is a MISS, second is a HIT. Cache headers are present and stable.
    """
    index_url = urljoin(synced_distro.base_url, "simple/")
    detail_url = f"{index_url}aiohttp"

    for url in [index_url, detail_url]:
        r1 = requests.get(url)
        assert r1.status_code == 200
        assert r1.headers["X-PULP-CACHE"] == "MISS"
        assert r1.headers["Cache-Control"] == "max-age=600, public"
        assert r1.headers["ETag"].startswith('"') and r1.headers["ETag"].endswith('"')

        r2 = requests.get(url)
        assert r2.status_code == 200
        assert r2.headers["X-PULP-CACHE"] == "HIT"
        assert r2.headers["Cache-Control"] == r1.headers["Cache-Control"]
        assert r2.headers["ETag"] == r1.headers["ETag"]


@pytest.mark.parallel
def test_simple_cache_separate_accept_headers(synced_distro):
    """
    HTML and JSON responses are cached separately by negotiated media type.
    """
    url = urljoin(synced_distro.base_url, "simple/")

    for header in [PYPI_SIMPLE_V1_HTML, PYPI_SIMPLE_V1_JSON]:
        r = requests.get(url, headers={"Accept": header})
        assert r.status_code == 200
        assert r.headers["X-PULP-CACHE"] == "MISS"

    for header in [PYPI_SIMPLE_V1_HTML, PYPI_SIMPLE_V1_JSON]:
        r = requests.get(url, headers={"Accept": header})
        assert r.status_code == 200
        assert r.headers["X-PULP-CACHE"] == "HIT"


@pytest.mark.parallel
def test_simple_cache_negotiated_media_types_are_separate(synced_distro):
    """
    JSON and HTML responses must not poison each other in the cache.

    Clients like uv/pip send an Accept that allows both JSON and HTML. The
    negotiated JSON response must be cached separately from an explicit HTML
    response.
    """
    url = f"{urljoin(synced_distro.base_url, 'simple/')}aiohttp"
    # pip/uv-style Accept: JSON preferred, HTML still acceptable
    headers = {
        "Accept": (f"{PYPI_SIMPLE_V1_JSON}, {PYPI_SIMPLE_V1_HTML};q=0.1, {PYPI_TEXT_HTML};q=0.01")
    }

    r_json = requests.get(url, headers=headers, params={"format": "json"})
    assert r_json.status_code == 200
    assert PYPI_SIMPLE_V1_JSON in r_json.headers["Content-Type"]
    assert r_json.headers["X-PULP-CACHE"] == "MISS"
    assert r_json.json()["name"] == "aiohttp"

    r_html = requests.get(url, headers={"Accept": PYPI_TEXT_HTML})
    assert r_html.status_code == 200
    assert PYPI_TEXT_HTML in r_html.headers["Content-Type"]
    assert r_html.headers["X-PULP-CACHE"] == "MISS"
    assert b"<a href=" in r_html.content

    r_html_hit = requests.get(url, headers={"Accept": PYPI_TEXT_HTML})
    assert r_html_hit.status_code == 200
    assert r_html_hit.headers["X-PULP-CACHE"] == "HIT"
    assert PYPI_TEXT_HTML in r_html_hit.headers["Content-Type"]

    r_json_hit = requests.get(url, headers=headers, params={"format": "json"})
    assert r_json_hit.status_code == 200
    assert r_json_hit.headers["X-PULP-CACHE"] == "HIT"
    assert PYPI_SIMPLE_V1_JSON in r_json_hit.headers["Content-Type"]


@pytest.mark.parallel
def test_simple_cache_etag_conditional_request(synced_distro):
    """
    Matching If-None-Match returns 304, non-matching returns 200.
    """
    url = urljoin(synced_distro.base_url, "simple/")

    r1 = requests.get(url)
    assert r1.status_code == 200
    etag = r1.headers["ETag"]
    cache_control = r1.headers["Cache-Control"]

    r2 = requests.get(url, headers={"If-None-Match": etag})
    assert r2.status_code == 304
    assert r2.headers["ETag"] == etag
    assert r2.headers["Cache-Control"] == cache_control
    assert "X-PULP-CACHE" not in r2.headers
    assert len(r2.content) == 0

    r3 = requests.get(url, headers={"If-None-Match": '"old"'})
    assert r3.status_code == 200
    assert r3.headers["ETag"] == etag
    assert r3.headers["Cache-Control"] == cache_control
    assert r3.headers["X-PULP-CACHE"] == "HIT"
    assert len(r3.content) > 0


@pytest.mark.parallel
def test_simple_last_modified_header(synced_distro_no_cache):
    """Simple API responses include Last-Modified header."""
    index_url = urljoin(synced_distro_no_cache.base_url, "simple/")
    detail_url = f"{index_url}aiohttp"

    for url in [index_url, detail_url]:
        r = requests.get(url)
        assert r.status_code == 200
        assert "Last-Modified" in r.headers
        parsedate_to_datetime(r.headers["Last-Modified"])


@pytest.mark.parallel
def test_simple_if_modified_since_304(synced_distro_no_cache):
    """If-Modified-Since with matching timestamp returns 304."""
    url = urljoin(synced_distro_no_cache.base_url, "simple/")

    r1 = requests.get(url)
    assert r1.status_code == 200
    last_modified = r1.headers["Last-Modified"]

    r2 = requests.get(url, headers={"If-Modified-Since": last_modified})
    assert r2.status_code == 304
    assert len(r2.content) == 0


@pytest.mark.parallel
def test_simple_if_modified_since_old_timestamp_200(synced_distro_no_cache):
    """If-Modified-Since with old timestamp returns 200 with content."""
    url = urljoin(synced_distro_no_cache.base_url, "simple/")

    r1 = requests.get(url)
    assert r1.status_code == 200

    r2 = requests.get(url, headers={"If-Modified-Since": "Thu, 01 Jan 2009 00:00:00 GMT"})
    assert r2.status_code == 200
    assert len(r2.content) > 0


@pytest.mark.parallel
def test_metadata_conditional_request_headers(synced_distro_no_cache):
    """JSON metadata responses include ETag, Last-Modified, and Cache-Control headers."""
    url = urljoin(synced_distro_no_cache.base_url, "pypi/aiohttp/json/")

    r = requests.get(url)
    assert r.status_code == 200
    assert r.headers["Cache-Control"] == "max-age=900, public"
    assert "ETag" in r.headers
    assert r.headers["ETag"].startswith('"') and r.headers["ETag"].endswith('"')
    assert "Last-Modified" in r.headers
    parsedate_to_datetime(r.headers["Last-Modified"])


@pytest.mark.parallel
def test_metadata_etag_conditional_request(synced_distro_no_cache):
    """JSON metadata: matching If-None-Match returns 304, non-matching returns 200."""
    url = urljoin(synced_distro_no_cache.base_url, "pypi/aiohttp/json/")

    r1 = requests.get(url)
    assert r1.status_code == 200
    etag = r1.headers["ETag"]

    r2 = requests.get(url, headers={"If-None-Match": etag})
    assert r2.status_code == 304
    assert len(r2.content) == 0

    r3 = requests.get(url, headers={"If-None-Match": '"old"'})
    assert r3.status_code == 200
    assert r3.headers["ETag"] == etag


@pytest.mark.parallel
def test_metadata_if_modified_since_304(synced_distro_no_cache):
    """JSON metadata: If-Modified-Since with matching timestamp returns 304."""
    url = urljoin(synced_distro_no_cache.base_url, "pypi/aiohttp/json/")

    r1 = requests.get(url)
    assert r1.status_code == 200
    last_modified = r1.headers["Last-Modified"]

    r2 = requests.get(url, headers={"If-Modified-Since": last_modified})
    assert r2.status_code == 304
    assert len(r2.content) == 0


@pytest.mark.parallel
def test_metadata_if_modified_since_old_timestamp_200(synced_distro_no_cache):
    """JSON metadata: If-Modified-Since with old timestamp returns 200."""
    url = urljoin(synced_distro_no_cache.base_url, "pypi/aiohttp/json/")

    r1 = requests.get(url)
    assert r1.status_code == 200

    r2 = requests.get(url, headers={"If-Modified-Since": "Thu, 01 Jan 2009 00:00:00 GMT"})
    assert r2.status_code == 200
    assert len(r2.content) > 0


def test_unauthenticated_gets_401_not_304(synced_distro_no_cache, pulpcore_bindings, bindings_cfg):
    """Unauthenticated client gets 401, not 304, even with conditional request headers."""
    admin_auth = (bindings_cfg.username, bindings_cfg.password)
    simple_url = urljoin(synced_distro_no_cache.base_url, "simple/")

    r1 = requests.get(simple_url, auth=admin_auth)
    assert r1.status_code == 200
    last_modified = r1.headers["Last-Modified"]
    etag = r1.headers["ETag"]

    ap_response = pulpcore_bindings.AccessPoliciesApi.list(viewset_name="pypi/simple")
    assert ap_response.count == 1
    ap_href = ap_response.results[0].pulp_href
    original_statements = pulpcore_bindings.AccessPoliciesApi.read(ap_href).statements

    anon = requests.Session()
    anon.trust_env = False
    anon.verify = False

    try:
        pulpcore_bindings.AccessPoliciesApi.partial_update(
            ap_href,
            {
                "statements": [
                    {
                        "action": ["list", "retrieve"],
                        "principal": "authenticated",
                        "effect": "allow",
                    },
                    {
                        "action": ["create"],
                        "principal": "authenticated",
                        "effect": "allow",
                        "condition": "index_has_repo_perm:python.modify_pythonrepository",
                    },
                ],
            },
        )

        r_ims = anon.get(simple_url, headers={"If-Modified-Since": last_modified})
        assert r_ims.status_code == 401, (
            f"Expected 401 for unauthenticated If-Modified-Since, got {r_ims.status_code}"
        )

        r_inm = anon.get(simple_url, headers={"If-None-Match": etag})
        assert r_inm.status_code == 401, (
            f"Expected 401 for unauthenticated If-None-Match, got {r_inm.status_code}"
        )

        r_authed = requests.get(
            simple_url, auth=admin_auth, headers={"If-Modified-Since": last_modified}
        )
        assert r_authed.status_code == 304
    finally:
        pulpcore_bindings.AccessPoliciesApi.partial_update(
            ap_href, {"statements": original_statements}
        )
