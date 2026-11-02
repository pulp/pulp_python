"""Functional tests for verifying attestations signed with a server-configured key.

These tests exercise the attestation / provenance upload paths with
attestations that carry an RSA signature instead of a Sigstore certificate.

A static test keypair is shipped in .ci/assets/keys/ and the matching
public key is configured for the default domain in PULP_ATTESTATION_VERIFICATION_KEYS so that
signature verification is fully exercised end-to-end.
"""

import base64
import hashlib
import json
import os

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as crypto_padding
from cryptography.hazmat.primitives.asymmetric import rsa

from pulpcore.tests.functional.utils import PulpTaskError

from pulp_python.tests.functional.constants import PYTHON_EGG_FILENAME, PYTHON_URL

DSSE_PAYLOAD_TYPE = "application/vnd.in-toto+json"

TEST_PRIVATE_KEY_PATH = "/etc/pki/attestation/test-key-private.pem"
TEST_PUBLIC_KEY_PATH = "/etc/pki/attestation/test-key.pem"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_statement(filename, sha256):
    """Build a minimal in-toto statement with an SLSA v1 provenance predicate."""
    return json.dumps(
        {
            "_type": "https://in-toto.io/Statement/v1",
            "predicateType": "https://slsa.dev/provenance/v1",
            "subject": [{"name": filename, "digest": {"sha256": sha256}}],
            "predicate": {
                "buildDefinition": {"buildType": "https://konflux-ci.dev/PythonWheelBuild@v1"},
                "runDetails": {"builder": {"id": "https://konflux-ci.dev/calunga"}},
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
    """Return a single key-signed Attestation dict without verification material."""
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
    """Load the static test attestation signing key from .ci/assets/keys/."""
    if not os.path.exists(TEST_PRIVATE_KEY_PATH):
        pytest.skip(
            f"Test attestation private key not found at {TEST_PRIVATE_KEY_PATH} (not running in CI container?)"
        )
    if pulp_settings.ATTESTATION_VERIFICATION_KEYS.get("default") != TEST_PUBLIC_KEY_PATH:
        pytest.fail(
            f"ATTESTATION_VERIFICATION_KEYS does not map the default domain to {TEST_PUBLIC_KEY_PATH}"
        )
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


def test_key_signed_provenance_stored(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """A key-signed provenance is accepted and stored when verify=True."""
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


def test_key_signed_wrong_subject_name_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """Verification rejects a key-signed attestation whose subject name does not match."""
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


def test_key_signed_wrong_digest_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """Verification rejects a key-signed attestation whose digest does not match."""
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


def test_key_signed_bad_signature_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """A key-signed attestation with a valid subject but tampered signature is rejected."""
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


def test_key_signed_attestation_via_content_upload(
    python_bindings, python_content_factory, monitor_task, test_private_key
):
    """Key-signed attestations can be uploaded alongside a package via the content API."""
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
    assert publisher["kind"] == "Pulp User"


def test_invalid_certificate_not_verified_with_key(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """An attestation with an unparseable certificate is rejected, not verified with the key."""
    content = python_content_factory()

    stmt = _build_statement(content.filename, content.sha256)
    att = _make_attestation(stmt, _sign(stmt, test_private_key))
    att["verification_material"] = {
        "certificate": _b64(b"not-a-certificate"),
        "transparency_entries": [{"log_index": 0}],
    }
    prov = _make_provenance(att)

    task = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file=_provenance_file(prov),
        verify=True,
    ).task
    with pytest.raises(PulpTaskError) as exc_info:
        monitor_task(task)
    assert "invalid X.509 certificate" in exc_info.value.task.error["description"]


def test_key_signed_attestation_with_other_key_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """An attestation signed with a key other than the domain's configured key is rejected."""
    content = python_content_factory()
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    stmt = _build_statement(content.filename, content.sha256)
    att = _make_attestation(stmt, _sign(stmt, other_key))
    prov = _make_provenance(att)

    task = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file=_provenance_file(prov),
        verify=True,
    ).task
    with pytest.raises(PulpTaskError) as exc_info:
        monitor_task(task)
    assert "signature verification failed" in exc_info.value.task.error["description"]


def test_key_signed_attestation_rejected_in_domain_without_key(
    python_bindings, domain_factory, download_python_file, monitor_task, test_private_key
):
    """A key configured for the default domain is not trusted in another domain."""
    domain = domain_factory()
    python_file = download_python_file(PYTHON_EGG_FILENAME, PYTHON_URL)
    with open(python_file, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()

    stmt = _build_statement(PYTHON_EGG_FILENAME, sha256)
    att = _make_attestation(stmt, _sign(stmt, test_private_key))
    body = {
        "file": python_file,
        "relative_path": PYTHON_EGG_FILENAME,
        "attestations": json.dumps([att]),
    }
    task = python_bindings.ContentPackagesApi.create(**body, pulp_domain=domain.name).task
    with pytest.raises(PulpTaskError) as exc_info:
        monitor_task(task)
    err_msg = f"ATTESTATION_VERIFICATION_KEYS has no key for domain '{domain.name}'"
    assert err_msg in exc_info.value.task.error["description"]


def test_key_signed_attestation_with_trusted_publisher_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """A key-signed attestation cannot claim a Trusted Publisher, which needs a certificate."""
    content = python_content_factory()

    stmt = _build_statement(content.filename, content.sha256)
    att = _make_attestation(stmt, _sign(stmt, test_private_key))
    prov = _make_provenance(att)
    prov["attestation_bundles"][0]["publisher"] = {
        "kind": "GitHub",
        "repository": "pypa/sampleproject",
        "workflow": "release.yml",
    }

    task = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file=_provenance_file(prov),
        verify=True,
    ).task
    with pytest.raises(PulpTaskError) as exc_info:
        monitor_task(task)
    err_msg = "publisher kind 'GitHub' requires a Sigstore certificate"
    assert err_msg in exc_info.value.task.error["description"]


def test_key_signed_malformed_subject_rejected(
    python_bindings, python_content_factory, monitor_task, test_private_key, _provenance_file
):
    """A key-signed attestation with a malformed subject is rejected, not crashed on."""
    content = python_content_factory()

    stmt = json.dumps({"_type": "https://in-toto.io/Statement/v1", "subject": None}).encode()
    att = _make_attestation(stmt, _sign(stmt, test_private_key))
    prov = _make_provenance(att)

    task = python_bindings.ContentProvenanceApi.create(
        package=content.pulp_href,
        file=_provenance_file(prov),
        verify=True,
    ).task
    with pytest.raises(PulpTaskError) as exc_info:
        monitor_task(task)
    assert "malformed statement" in exc_info.value.task.error["description"]
