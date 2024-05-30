import time

from datetime import datetime, timezone
from django.db import transaction
from django.contrib.sessions.models import Session
from pulpcore.plugin.models import Artifact, CreatedResource, ContentArtifact
from pulpcore.plugin.util import get_domain

from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.utils import get_project_metadata_from_artifact, parse_project_metadata


def upload(artifact_sha256, filename, repository_pk=None):
    """
    Uploads a Python Package to Pulp

    Args:
        artifact_sha256: the sha256 of the artifact in Pulp to create a package from
        filename: the full filename of the package to create
        repository_pk: the optional pk of the repository to add the content to
    """
    domain = get_domain()
    pre_check = PythonPackageContent.objects.filter(sha256=artifact_sha256, _pulp_domain=domain)
    content_to_add = pre_check or create_content(artifact_sha256, filename, domain)
    content_to_add.get().touch()
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
            start_time = datetime.fromisoformat(session_data['start'])
            if now >= start_time:
                content_to_add = PythonPackageContent.objects.none()
                for artifact_sha256, filename in session_data['artifacts']:
                    pre_check = PythonPackageContent.objects.filter(
                        sha256=artifact_sha256, _pulp_domain=domain
                    )
                    content = pre_check or create_content(artifact_sha256, filename, domain)
                    content.get().touch()
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
        queryset of the new created content
    """
    artifact = Artifact.objects.get(sha256=artifact_sha256, pulp_domain=domain)
    metadata = get_project_metadata_from_artifact(filename, artifact)

    data = parse_project_metadata(vars(metadata))
    data['packagetype'] = metadata.packagetype
    data['version'] = metadata.version
    data['filename'] = filename
    data['sha256'] = artifact.sha256
    data['pulp_domain'] = domain
    data['_pulp_domain'] = domain

    @transaction.atomic()
    def create():
        content = PythonPackageContent.objects.create(**data)
        ContentArtifact.objects.create(
            artifact=artifact, content=content, relative_path=filename
        )
        return content

    new_content = create()
    resource = CreatedResource(content_object=new_content)
    resource.save()

    return PythonPackageContent.objects.filter(pk=new_content.pk)
