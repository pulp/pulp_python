from typing import Annotated, Literal, Union, get_args

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_snake
from pypi_attestations import (
    Attestation,
    Distribution,
    Publisher,
)


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


def verify_provenance(filename, sha256, provenance, offline=False):
    """Verify the provenance object is valid for the package."""
    dist = Distribution(name=filename, digest=sha256)
    for bundle in provenance.attestation_bundles:
        publisher = bundle.publisher
        policy = publisher._as_policy()
        for attestation in bundle.attestations:
            sig_bundle = attestation.to_bundle()
            checkpoint = sig_bundle.log_entry._inner.inclusion_proof.checkpoint
            staging = "sigstage.dev" in checkpoint.envelope
            attestation.verify(policy, dist, staging=staging, offline=offline)
