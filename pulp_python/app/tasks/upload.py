import pkginfo
import shutil
import tempfile
import time

from datetime import datetime, timezone
from django.db import transaction
from django.contrib.sessions.models import Session
from django.core.files.storage import default_storage as storage
from pulpcore.plugin.models import Artifact, CreatedResource, ContentArtifact

from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.utils import parse_project_metadata


DIST_EXTENSIONS = {
    ".whl": "bdist_wheel",
    ".exe": "bdist_wininst",
    ".egg": "bdist_egg",
    ".tar.bz2": "sdist",
    ".tar.gz": "sdist",
    ".zip": "sdist",
}

DIST_TYPES = {
    "bdist_wheel": pkginfo.Wheel,
    "bdist_wininst": pkginfo.Distribution,
    "bdist_egg": pkginfo.BDist,
    "sdist": pkginfo.SDist,
}


def upload(artifact_sha256, filename, repository_pk=None):
    """
    Uploads a Python Package to Pulp

    Args:
        artifact_sha256: the sha256 of the artifact in Pulp to create a package from
        filename: the full filename of the package to create
        repository_pk: the optional pk of the repository to add the content to
    """
    pre_check = PythonPackageContent.objects.filter(sha256=artifact_sha256)
    content_to_add = pre_check or create_content(artifact_sha256, filename)
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
    while True:
        with transaction.atomic():
            session_data = s_query.first().get_decoded()
            now = datetime.now(tz=timezone.utc)
            start_time = datetime.fromisoformat(session_data['start'])
            if now >= start_time:
                content_to_add = PythonPackageContent.objects.none()
                for artifact_sha256, filename in session_data['artifacts']:
                    pre_check = PythonPackageContent.objects.filter(sha256=artifact_sha256)
                    content = pre_check or create_content(artifact_sha256, filename)
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


def create_content(artifact_sha256, filename):
    """
    Creates PythonPackageContent from artifact.

    Args:
        artifact_sha256: validated artifact
        filename: file name
    Returns:
        queryset of the new created content
    """
    # iterate through extensions since splitext does not support things like .tar.gz
    extensions = list(DIST_EXTENSIONS.keys())
    pkg_type_index = [filename.endswith(ext) for ext in extensions].index(True)
    packagetype = DIST_EXTENSIONS[extensions[pkg_type_index]]
    # Copy file to a temp directory under the user provided filename, we do this
    # because pkginfo validates that the filename has a valid extension before
    # reading it
    artifact = Artifact.objects.get(sha256=artifact_sha256)
    artifact_file = storage.open(artifact.file.name)
    with tempfile.NamedTemporaryFile('wb', suffix=filename) as temp_file:
        shutil.copyfileobj(artifact_file, temp_file)
        temp_file.flush()
        metadata = DIST_TYPES[packagetype](temp_file.name)
        metadata.packagetype = packagetype

    data = parse_project_metadata(vars(metadata))
    data['packagetype'] = metadata.packagetype
    data['version'] = metadata.version
    data['filename'] = filename
    data['sha256'] = artifact.sha256

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
