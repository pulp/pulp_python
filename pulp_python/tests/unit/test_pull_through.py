from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.conf import settings

from pulpcore.plugin.cache import SyncContentCache

from pulp_python.app import utils
from pulp_python.app.utils import (
    PULL_THROUGH_PARAM,
    clear_pull_through_entries,
    lookup_pull_through_entry,
    sign_pull_through_path,
    store_pull_through_entries,
    unsign_pull_through_token,
)

FILENAME = "shelf_reader-0.1-py2-none-any.whl"
URL = f"https://files.example.com/packages/ab/cd/{FILENAME}"


def _remote(**kwargs):
    kwargs.setdefault("pk", uuid4())
    kwargs.setdefault("url", "https://pypi.org/")
    kwargs.setdefault("includes", [])
    kwargs.setdefault("excludes", [])
    return SimpleNamespace(**kwargs)


def _redis_available():
    if not settings.CACHE_ENABLED:
        return False
    try:
        return SyncContentCache().redis.ping()
    except Exception:
        return False


requires_redis = pytest.mark.skipif(not _redis_available(), reason="Redis is not available")


def _token(remote, **kwargs):
    path = sign_pull_through_path(remote, FILENAME, URL, **kwargs)
    filename, token = path.split(f"?{PULL_THROUGH_PARAM}=")
    assert filename == FILENAME
    return token


def test_round_trip():
    remote = _remote()
    token = _token(remote, sha256="a" * 64, metadata_sha256="b" * 64)

    assert unsign_pull_through_token(remote, token, FILENAME) == (URL, "a" * 64)
    assert unsign_pull_through_token(remote, token, f"{FILENAME}.metadata") == (
        f"{URL}.metadata",
        "b" * 64,
    )


def test_metadata_requires_signed_digest():
    remote = _remote()
    token = _token(remote, sha256="a" * 64)

    assert unsign_pull_through_token(remote, token, f"{FILENAME}.metadata") is None


def test_rejects_other_remote():
    token = _token(_remote(), sha256="a" * 64)

    assert unsign_pull_through_token(_remote(), token, FILENAME) is None


@pytest.mark.parametrize(
    "changes",
    [{"url": "https://example.com/"}, {"includes": ["shelf-reader"]}, {"excludes": ["django"]}],
)
def test_rejects_changed_remote(changes):
    remote = _remote()
    token = _token(remote, sha256="a" * 64)

    assert (
        unsign_pull_through_token(_remote(**{**vars(remote), **changes}), token, FILENAME) is None
    )


def test_rejects_other_filename():
    remote = _remote()
    token = _token(remote, sha256="a" * 64)

    assert unsign_pull_through_token(remote, token, "evil-1.0-py3-none-any.whl") is None


def test_rejects_tampered_token():
    remote = _remote()
    token = _token(remote, sha256="a" * 64)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    assert unsign_pull_through_token(remote, tampered, FILENAME) is None
    assert unsign_pull_through_token(remote, "not-a-token", FILENAME) is None


@requires_redis
def test_stored_entries():
    remote = _remote()
    sdist = "shelf-reader-0.1.tar.gz"
    legacy = "pytz-2011k.tar.bz2"
    entry = {"url": URL, "sha256": "a" * 64, "metadata_sha256": None}
    assert store_pull_through_entries(
        remote,
        {FILENAME: entry, sdist: {"url": f"{URL}/{sdist}"}, legacy: {"url": f"{URL}/{legacy}"}},
    )

    assert lookup_pull_through_entry(remote, FILENAME) == (URL, "a" * 64)
    assert lookup_pull_through_entry(remote, f"{FILENAME}.metadata") is None
    assert lookup_pull_through_entry(remote, sdist) == (f"{URL}/{sdist}", None)
    assert lookup_pull_through_entry(remote, legacy) == (f"{URL}/{legacy}", None)
    assert lookup_pull_through_entry(remote, "evil-1.0-py3-none-any.whl") is None
    assert lookup_pull_through_entry(_remote(), FILENAME) is None

    entry["metadata_sha256"] = "b" * 64
    assert store_pull_through_entries(remote, {FILENAME: entry})
    assert lookup_pull_through_entry(remote, f"{FILENAME}.metadata") == (
        f"{URL}.metadata",
        "b" * 64,
    )
    assert lookup_pull_through_entry(remote, sdist) == (f"{URL}/{sdist}", None)

    clear_pull_through_entries(remote.pk)
    assert lookup_pull_through_entry(remote, FILENAME) is None
    assert lookup_pull_through_entry(remote, legacy) is None


@requires_redis
@pytest.mark.parametrize("ttl", [1200, None])
def test_stored_entries_ttl(monkeypatch, ttl):
    monkeypatch.setattr(utils, "PULL_THROUGH_TTL", ttl)
    remote = _remote()
    assert store_pull_through_entries(remote, {FILENAME: {"url": URL}})

    redis_ttl = SyncContentCache().redis.ttl(utils._pull_through_key(remote, FILENAME))
    if ttl is None:
        assert redis_ttl == -1
    else:
        assert 0 < redis_ttl <= ttl
    clear_pull_through_entries(remote.pk)
