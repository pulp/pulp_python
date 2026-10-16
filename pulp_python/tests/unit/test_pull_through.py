from types import SimpleNamespace
from uuid import uuid4

from pulp_python.app.utils import (
    PULL_THROUGH_PARAM,
    sign_pull_through_path,
    unsign_pull_through_token,
)

FILENAME = "shelf_reader-0.1-py2-none-any.whl"
URL = f"https://files.example.com/packages/ab/cd/{FILENAME}"


def _token(remote, **kwargs):
    path = sign_pull_through_path(remote, FILENAME, URL, **kwargs)
    filename, token = path.split(f"?{PULL_THROUGH_PARAM}=")
    assert filename == FILENAME
    return token


def test_round_trip():
    remote = SimpleNamespace(pk=uuid4())
    token = _token(remote, sha256="a" * 64, metadata_sha256="b" * 64)

    assert unsign_pull_through_token(remote, token, FILENAME) == (URL, "a" * 64)
    assert unsign_pull_through_token(remote, token, f"{FILENAME}.metadata") == (
        f"{URL}.metadata",
        "b" * 64,
    )


def test_metadata_requires_signed_digest():
    remote = SimpleNamespace(pk=uuid4())
    token = _token(remote, sha256="a" * 64)

    assert unsign_pull_through_token(remote, token, f"{FILENAME}.metadata") is None


def test_rejects_other_remote():
    token = _token(SimpleNamespace(pk=uuid4()), sha256="a" * 64)

    assert unsign_pull_through_token(SimpleNamespace(pk=uuid4()), token, FILENAME) is None


def test_rejects_other_filename():
    remote = SimpleNamespace(pk=uuid4())
    token = _token(remote, sha256="a" * 64)

    assert unsign_pull_through_token(remote, token, "evil-1.0-py3-none-any.whl") is None


def test_rejects_tampered_token():
    remote = SimpleNamespace(pk=uuid4())
    token = _token(remote, sha256="a" * 64)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")

    assert unsign_pull_through_token(remote, tampered, FILENAME) is None
    assert unsign_pull_through_token(remote, "not-a-token", FILENAME) is None
