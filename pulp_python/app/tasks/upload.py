import time

from datetime import datetime, timezone
from django.db import transaction
from django.contrib.sessions.models import Session
from pydantic import TypeAdapter
from pulpcore.plugin.models import Artifact, CreatedResource, Content, ContentArtifact
from pulpcore.plugin.util import get_domain, get_current_authenticated_user, get_prn

from pulp_python.app.models import PythonPackageContent, PythonRepository, PackageProvenance
from pulp_python.app.provenance import (
    Attestation,
    AttestationBundle,
    AnyPublisher,
    Provenance,
    verify_provenance,
)
from pulp_python.app.utils import artifact_to_metadata_artifact, artifact_to_python_content_data


def upload(artifact_sha256, filename, attestations=None, repository_pk=None):
    """
    Uploads a Python Package to Pulp

    Args:
        artifact_sha256: the sha256 of the artifact in Pulp to create a package from
        filename: the full filename of the package to create
        attestations: optional list of attestations to create a provenance from
        repository_pk: the optional pk of the repository to add the content to
    """
    domain = get_domain()
    pre_check = PythonPackageContent.objects.filter(sha256=artifact_sha256, _pulp_domain=domain)
    content_to_add = [pre_check.first() or create_content(artifact_sha256, filename, domain)]
    if attestations:
        content_to_add += [create_provenance(content_to_add[0], attestations, domain)]
    content_to_add = Content.objects.filter(pk__in=[c.pk for c in content_to_add])
    content_to_add.touch()
    if repository_pk:
        repository = PythonRepository.objects.get(pk=repository_pk)
        with repository.new_version() as new_version:
            new_version.add_content(content_to_add)


def upload_group(session_pk, repository_pk=None):
    """
    Uploads a Python Package to Pulp

    Args:
        session_pk: the session that has the artifacts to upload
        repository_pk: optional repository to add Content to
    """
    s_query = Session.objects.select_for_update().filter(pk=session_pk)
    domain = get_domain()
    while True:
        with transaction.atomic():
            session_data = s_query.first().get_decoded()
            now = datetime.now(tz=timezone.utc)
            start_time = datetime.fromisoformat(session_data["start"])
            if now >= start_time:
                content_to_add = Content.objects.none()
                for artifact_sha256, filename, attestations in session_data["artifacts"]:
                    pre_check = PythonPackageContent.objects.filter(
                        sha256=artifact_sha256, _pulp_domain=domain
                    ).first()
                    content = [pre_check or create_content(artifact_sha256, filename, domain)]
                    if attestations:
                        content += [create_provenance(content[0], attestations, domain)]
                    content = Content.objects.filter(pk__in=[c.pk for c in content])
                    content.touch()
                    content_to_add |= content

                if repository_pk:
                    repository = PythonRepository.objects.get(pk=repository_pk)
                    with repository.new_version() as new_version:
                        new_version.add_content(content_to_add)
                return
            else:
                sleep_time = start_time - now
        time.sleep(sleep_time.seconds)


def create_content(artifact_sha256, filename, domain):
    """
    Creates PythonPackageContent from artifact.

    Args:
        artifact_sha256: validated artifact
        filename: file name
        domain: the pulp_domain to perform this task in
    Returns:
        the newly created PythonPackageContent
    """
    artifact = Artifact.objects.get(sha256=artifact_sha256, pulp_domain=domain)
    data = artifact_to_python_content_data(filename, artifact, domain)

    @transaction.atomic()
    def create():
        content = PythonPackageContent.objects.create(**data)
        ContentArtifact.objects.create(artifact=artifact, content=content, relative_path=filename)

        if metadata_artifact := artifact_to_metadata_artifact(filename, artifact):
            ContentArtifact.objects.create(
                artifact=metadata_artifact, content=content, relative_path=f"{filename}.metadata"
            )
        return content

    new_content = create()
    resource = CreatedResource(content_object=new_content)
    resource.save()

    return new_content


def create_provenance(package, attestations, domain):
    """
    Creates PackageProvenance from attestations.

    Args:
        package: the package to create the provenance for
        attestations: the attestations to create the provenance from
        domain: the pulp_domain to perform this task in
    Returns:
        the newly created PackageProvenance
    """
    attestations = TypeAdapter(list[Attestation]).validate_python(attestations)

    user = get_current_authenticated_user()
    publisher = AnyPublisher(kind="Pulp User", prn=get_prn(user))
    att_bundle = AttestationBundle(publisher=publisher, attestations=attestations)
    provenance = Provenance(attestation_bundles=[att_bundle])
    verify_provenance(package.filename, package.sha256, provenance)
    provenance_json = provenance.model_dump(mode="json")

    prov_sha256 = PackageProvenance.calculate_sha256(provenance_json)
    prov_model, _ = PackageProvenance.objects.get_or_create(
        sha256=prov_sha256,
        _pulp_domain=domain,
        defaults={"package": package, "provenance": provenance_json},
    )
    resource = CreatedResource(content_object=prov_model)
    resource.save()

    return prov_model
