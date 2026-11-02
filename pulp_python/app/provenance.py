import json
from typing import Annotated, Literal, Union, get_args

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as crypto_padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import load_der_x509_certificate
from django.conf import settings
from pydantic import BaseModel, ConfigDict, Field, ValidationError
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

from pulpcore.plugin.util import get_domain

_verification_key_cache = {}


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
# Get the kinds of the original publisher types, they can only be proven by a Sigstore certificate
_TrustedPublisherKinds = {t.model_fields["kind"].default for t in _OriginalPublisherTypes}
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


def _load_verification_key(domain_name):
    """Load the attestation verification public key configured for the domain, with caching."""
    keys = settings.ATTESTATION_VERIFICATION_KEYS
    if not isinstance(keys, dict):
        raise VerificationError(
            "ATTESTATION_VERIFICATION_KEYS must map domain names to public key paths"
        )
    key_path = keys.get(domain_name)
    if not key_path:
        return None
    if key_path not in _verification_key_cache:
        try:
            with open(key_path, "rb") as f:
                key = serialization.load_pem_public_key(f.read())
        except (OSError, ValueError, UnsupportedAlgorithm) as e:
            raise VerificationError(
                f"could not load the verification key for domain '{domain_name}' "
                f"from {key_path}: {e}"
            )
        if not isinstance(key, rsa.RSAPublicKey):
            raise VerificationError(
                f"the verification key for domain '{domain_name}' in {key_path} "
                "must be an RSA public key"
            )
        _verification_key_cache[key_path] = key
    return _verification_key_cache[key_path]


def _has_certificate(attestation):
    """Check whether the attestation carries a certificate, rejecting unparseable ones."""
    vm = attestation.verification_material
    if vm is None:
        return False
    try:
        load_der_x509_certificate(vm.certificate)
    except ValueError as e:
        raise VerificationError(f"invalid X.509 certificate in verification_material: {e}")
    return True


def _verify_statement_subject(attestation, dist):
    """Validate that the in-toto statement subject matches the distribution."""
    try:
        stmt = json.loads(attestation.envelope.statement)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise VerificationError(f"invalid statement: {e}")

    try:
        subjects = stmt.get("subject", [])
        if len(subjects) != 1:
            raise VerificationError("expected exactly one subject in statement")

        subject = subjects[0]
        name = subject.get("name", "")
        if name != dist.name:
            raise VerificationError(
                f"subject does not match distribution name: {name} != {dist.name}"
            )

        digest = subject.get("digest", {}).get("sha256")
        if digest != dist.digest:
            raise VerificationError("subject does not match distribution digest")
    except (AttributeError, TypeError) as e:
        raise VerificationError(f"malformed statement: {e}")


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
    except InvalidSignature:
        raise VerificationError("signature verification failed")


def verify_provenance(filename, sha256, provenance, offline=True):
    """Verify the provenance object is valid for the package.

    Each attestation is routed to one of two coexisting verification paths:
    1. Attestations with a valid Sigstore certificate follow the standard PEP 740 path.
    2. Attestations without a certificate are verified against the key configured for the
    current domain in ATTESTATION_VERIFICATION_KEYS using RSA PKCS1v15 signatures.
    Attestations with a certificate that can't be parsed are rejected.
    """
    try:
        dist = Distribution(name=filename, digest=sha256)
    except ValidationError as e:
        raise VerificationError(f"invalid distribution filename {filename}: {e}")
    for bundle in provenance.attestation_bundles:
        publisher = bundle.publisher
        policy = publisher._as_policy()
        for attestation in bundle.attestations:
            if _has_certificate(attestation):
                sig_bundle = attestation.to_bundle()
                checkpoint = sig_bundle.log_entry._inner.inclusion_proof.checkpoint
                staging = "sigstage.dev" in checkpoint.envelope
                attestation.verify(policy, dist, staging=staging, offline=offline)
            else:
                if publisher.kind in _TrustedPublisherKinds:
                    raise VerificationError(
                        f"publisher kind '{publisher.kind}' requires a Sigstore certificate"
                    )
                domain_name = get_domain().name
                verification_key = _load_verification_key(domain_name)
                if verification_key:
                    _verify_statement_subject(attestation, dist)
                    _verify_signature(attestation, verification_key)
                else:
                    raise VerificationError(
                        "attestation has no Sigstore certificate, and "
                        f"ATTESTATION_VERIFICATION_KEYS has no key for domain '{domain_name}'"
                    )
