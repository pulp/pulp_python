import json
import logging
from typing import Annotated, Literal, Union, get_args
from urllib.parse import urlparse

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as crypto_padding
from cryptography.x509 import load_der_x509_certificate
from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_snake
from pypi_attestations import Attestation as _UpstreamAttestation
from pypi_attestations import (
    Distribution,
    Envelope,  # noqa - needed in module namespace for Pydantic model rebuild
    Publisher,
    VerificationError,
    VerificationMaterial,
)
from sigstore.dsse import Envelope as DSSEEnvelope
from sigstore.dsse import _pae

log = logging.getLogger(__name__)

_verification_key_cache = {}

SLSA_PROVENANCE_V02 = "https://slsa.dev/provenance/v0.2"


class _PermissivePolicy:
    """A permissive verification policy that always succeeds."""

    def verify(self, cert):
        """Succeed regardless of the publisher's identity."""
        pass


class AnyPublisher(BaseModel):
    """A fallback publisher for any kind not matching other publisher types."""

    model_config = ConfigDict(alias_generator=to_snake, extra="allow")

    kind: str

    def _as_policy(self):
        """Return a permissive policy that always succeed."""
        return _PermissivePolicy()


# Get the underlying Union type of the original Publisher
# Publisher is Annotated[Union[...], Field(discriminator="kind")]
_OriginalPublisherTypes = get_args(Publisher.__origin__)
# Add AnyPublisher to the list of original publisher types
_ExtendedPublisherTypes = (*_OriginalPublisherTypes, AnyPublisher)
_ExtendedPublisherUnion = Union[_ExtendedPublisherTypes]
# Create a new type that fallbacks to AnyPublisher
ExtendedPublisher = Annotated[_ExtendedPublisherUnion, Field(union_mode="left_to_right")]


class Attestation(_UpstreamAttestation):
    """
    Attestation object as defined in PEP 740.

    Inherits from the upstream pypi_attestations.Attestation to keep Sigstore
    verification methods (to_bundle, verify), but makes verification_material
    optional to support attestations signed with a custom key instead of Sigstore.
    """

    verification_material: VerificationMaterial | None = None
    """
    Cryptographic materials used to verify `message_signature`.
    """


class AttestationBundle(BaseModel):
    """
    AttestationBundle object as defined in PEP740.

    PyPI only accepts attestations from TrustedPublishers (GitHub, GitLab, Google), but we will
    accept from any user.
    """

    publisher: ExtendedPublisher
    attestations: list[Attestation]


class Provenance(BaseModel):
    """Provenance object as defined in PEP740."""

    version: Literal[1] = 1
    attestation_bundles: list[AttestationBundle]


def _load_verification_key():
    """Load the configured attestation verification public key, with caching."""
    key_path = getattr(settings, "ATTESTATION_VERIFICATION_KEY", None)
    if not key_path:
        return None
    if key_path not in _verification_key_cache:
        with open(key_path, "rb") as f:
            _verification_key_cache[key_path] = serialization.load_pem_public_key(f.read())
    return _verification_key_cache[key_path]


def _has_valid_certificate(attestation):
    """Check whether the attestation contains a valid X.509 certificate."""
    try:
        vm = attestation.verification_material
        if vm is None:
            return False
        cert_bytes = vm.certificate
        load_der_x509_certificate(cert_bytes)
        return True
    except (ValueError, Exception):
        return False


def _verify_statement_subject(attestation, dist):
    """Validate that the in-toto statement subject matches the distribution.

    Returns the parsed statement dict for downstream use.
    """
    try:
        stmt = json.loads(attestation.envelope.statement)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise VerificationError(f"invalid statement: {e}")

    subjects = stmt.get("subject", [])
    if len(subjects) != 1:
        raise VerificationError("expected exactly one subject in statement")

    subject = subjects[0]
    name = subject.get("name", "")
    if name != dist.name:
        raise VerificationError(f"subject does not match distribution name: {name} != {dist.name}")

    digest = subject.get("digest", {}).get("sha256")
    if digest != dist.digest:
        raise VerificationError("subject does not match distribution digest")

    return stmt


def _enrich_publisher_from_statement(stmt, publisher):
    """Populate publisher fields from an SLSA v0.2 provenance statement."""
    if stmt.get("predicateType") != SLSA_PROVENANCE_V02:
        return

    predicate = stmt.get("predicate", {})
    builder_id = predicate.get("builder", {}).get("id")
    build_type = predicate.get("buildType")

    if builder_id:
        publisher.builder_id = builder_id
        try:
            hostname = urlparse(builder_id).hostname
            if hostname:
                publisher.kind = hostname
        except Exception:
            pass

    if build_type:
        publisher.build_type = build_type


def _verify_signature(attestation, public_key):
    """Verify the attestation's RSA signature over the DSSE PAE bytes."""
    statement_bytes = attestation.envelope.statement
    signature_bytes = attestation.envelope.signature
    pae = _pae(DSSEEnvelope._TYPE, statement_bytes)
    try:
        public_key.verify(
            signature_bytes,
            pae,
            crypto_padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature as e:
        raise VerificationError(f"signature verification failed: {e}")


def verify_provenance(filename, sha256, provenance, offline=True):
    """Verify the provenance object is valid for the package.

    Attestations with valid Sigstore certificates are verified through the
    standard Sigstore path. Attestations without certificates are verified
    against a custom public key configured via ATTESTATION_VERIFICATION_KEY.
    Currently, it supports RSA PKCS1v15 signatures and SLSA v0.2 provenance
    publisher enrichment.
    """
    dist = Distribution(name=filename, digest=sha256)
    verification_key = _load_verification_key()
    for bundle in provenance.attestation_bundles:
        publisher = bundle.publisher
        for attestation in bundle.attestations:
            if _has_valid_certificate(attestation):
                policy = publisher._as_policy()
                sig_bundle = attestation.to_bundle()
                checkpoint = sig_bundle.log_entry._inner.inclusion_proof.checkpoint
                staging = "sigstage.dev" in checkpoint.envelope
                attestation.verify(policy, dist, staging=staging, offline=offline)
            else:
                stmt = _verify_statement_subject(attestation, dist)
                _enrich_publisher_from_statement(stmt, publisher)
                if verification_key:
                    _verify_signature(attestation, verification_key)
                else:
                    raise VerificationError(
                        "Attestation has no Sigstore certificate and no custom "
                        "verification key is configured (ATTESTATION_VERIFICATION_KEY)"
                    )
