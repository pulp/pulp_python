"""Functional tests for Konflux-style attestation verification.

These tests exercise the attestation / provenance upload paths with
attestations that carry an RSA signature instead of a Sigstore certificate,
mirroring the format produced by Konflux / Calunga builds.

The test signing key is generated at image build time and the matching
public key is configured as PULP_ATTESTATION_VERIFICATION_KEY so that
signature verification is fully exercised end-to-end.
"""

import base64
import json
import os

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as crypto_padding

from pulpcore.tests.functional.utils import PulpTaskError

DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"

TEST_PRIVATE_KEY_PATH = "/etc/pki/attestation/test-key-private.pem"
TEST_PUBLIC_KEY_PATH = "/etc/pki/attestation/test-key.pem"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_statement(filename, sha256):
    """Build a minimal in-toto statement for a Konflux attestation."""
    return json.dumps(
        {
            "_type": "https://in-toto.io/Statement/v0.1",
            "predicateType": "https://slsa.dev/provenance/v0.2",
            "subject": [{"name": filename, "digest": {"sha256": sha256}}],
            "predicate": {
                "buildType": "https://konflux-ci.dev/PythonWheelBuild@v1",
                "builder": {"id": "https://konflux-ci.dev/calunga"},
            },
        }
    ).encode()


def _pae(payload_type, payload):
    """Compute the DSSE Pre-Authentication Encoding."""
    return b"DSSEv1 %d %b %d %b" % (
        len(payload_type),
        payload_type.encode(),
        len(payload),
        payload,
    )


def _sign(statement_bytes, private_key):
    pae = _pae(DSSE_PAYLOAD_TYPE, statement_bytes)
    return private_key.sign(
        pae,
        crypto_padding.PKCS1v15(),
        hashes.SHA256(),
    )


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _make_attestation(statement_bytes, signature_bytes):
    """Return a single PEP-740 Attestation dict (Konflux flavour)."""
    return {
        "version": 1,
        "verification_material": None,
        "envelope": {
            "statement": _b64(statement_bytes),
            "signature": _b64(signature_bytes),
        },
    }


def _make_provenance(attestation):
    """Wrap an attestation into a full PEP-740 Provenance object."""
    return {
        "version": 1,
        "attestation_bundles": [
            {
                "publisher": {"kind": "Konflux", "builder": "calunga"},
                "attestations": [attestation],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_private_key(pulp_settings):
    """Load the CI-generated test attestation signing key."""
    if not os.path.exists(TEST_PRIVATE_KEY_PATH):
        pytest.skip(
            f"Test attestation private key not found at {TEST_PRIVATE_KEY_PATH} (not running in CI container?)"
        )
    if pulp_settings.ATTESTATION_VERIFICATION_KEY != TEST_PUBLIC_KEY_PATH:
        pytest.fail(f"ATTESTATION_VERIFICATION_KEY is not set to {TEST_PUBLIC_KEY_PATH}")
    with open(TEST_PRIVATE_KEY_PATH, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


@pytest.fixture()
def _provenance_file(tmp_path):
    """Return a helper that writes a provenance dict to a temp file."""

    def _write(provenance_dict):
        path = tmp_path / "provenance.json"
        path.write_text(json.dumps(provenance_dict))
        return str(path)

    return _write


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_konflux_provenance_stored(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """A Konflux-style provenance is accepted and stored when verify=True."""
    content = python_content_factory()

    stmt = _build_statement(content.filename, content.sha256)
    sig = _sign(stmt, test_private_key)
    att = _make_attestation(stmt, sig)
    prov = _make_provenance(att)

    task = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file=_provenance_file(prov),
        verify=True,
    ).task
    result = monitor_task(task)

    prov_obj = python_bindings.ContentProvenanceApi.read(result.created_resources[-1])
    assert prov_obj.package == content.pulp_href
    stored_att = prov_obj.provenance["attestation_bundles"][0]["attestations"][0]
    assert stored_att["envelope"]["statement"] == _b64(stmt)
    publisher = prov_obj.provenance["attestation_bundles"][0]["publisher"]
    assert publisher["builder"] == "calunga"
    assert publisher["kind"] == "Konflux"


def test_konflux_wrong_subject_name_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """Verification rejects a Konflux attestation whose subject name does not match."""
    content = python_content_factory()

    wrong_name = "wrong-package-0.1.tar.gz"
    stmt = _build_statement(wrong_name, content.sha256)
    sig = _sign(stmt, test_private_key)
    att = _make_attestation(stmt, sig)
    prov = _make_provenance(att)

    task = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file=_provenance_file(prov),
        verify=True,
    ).task
    with pytest.raises(PulpTaskError) as exc_info:
        monitor_task(task)
    assert "subject does not match distribution name" in exc_info.value.task.error["description"]


def test_konflux_wrong_digest_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """Verification rejects a Konflux attestation whose digest does not match."""
    content = python_content_factory()

    bad_digest = "0" * 64
    stmt = _build_statement(content.filename, bad_digest)
    sig = _sign(stmt, test_private_key)
    att = _make_attestation(stmt, sig)
    prov = _make_provenance(att)

    task = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file=_provenance_file(prov),
        verify=True,
    ).task
    with pytest.raises(PulpTaskError) as exc_info:
        monitor_task(task)
    assert "subject does not match distribution digest" in exc_info.value.task.error["description"]


def test_konflux_bad_signature_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """An attestation with a valid subject but tampered signature is rejected."""
    content = python_content_factory()

    stmt = _build_statement(content.filename, content.sha256)
    sig = _sign(stmt, test_private_key)
    tampered_sig = bytes([b ^ 0xFF for b in sig[:32]]) + sig[32:]
    att = _make_attestation(stmt, tampered_sig)
    prov = _make_provenance(att)

    task = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file=_provenance_file(prov),
        verify=True,
    ).task
    with pytest.raises(PulpTaskError) as exc_info:
        monitor_task(task)
    assert "signature verification failed" in exc_info.value.task.error["description"]


def test_konflux_attestation_via_content_upload(
    python_bindings, python_content_factory, monitor_task, test_private_key
):
    """Konflux-style attestations can be uploaded alongside a package via the content API."""
    content = python_content_factory()

    stmt = _build_statement(content.filename, content.sha256)
    sig = _sign(stmt, test_private_key)
    att = _make_attestation(stmt, sig)

    body = {
        "artifact": content.artifact,
        "relative_path": content.filename,
        "sha256": content.sha256,
        "attestations": json.dumps([att]),
    }
    task = python_bindings.ContentPackagesApi.create(**body).task
    result = monitor_task(task)

    assert len(result.created_resources) == 2
    prov_obj = python_bindings.ContentProvenanceApi.read(result.created_resources[1])
    publisher = prov_obj.provenance["attestation_bundles"][0]["publisher"]
    assert publisher["builder_id"] == "https://konflux-ci.dev/calunga"
    assert publisher["build_type"] == "https://konflux-ci.dev/PythonWheelBuild@v1"
    assert publisher["kind"] == "konflux-ci.dev"
