import os
from gettext import gettext as _
import pkginfo
import shutil
import tempfile

from pulpcore.plugin.models import Artifact, CreatedResource
from rest_framework import serializers

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


def one_shot_upload(artifact_pk, filename, repository_pk=None):
    """
    One shot upload for pulp_python

    Args:
        artifact_pk: validated artifact
        filename: file name
        repository_pk: optional repository to add Content to
    """
    # iterate through extensions since splitext does not support things like .tar.gz
    for ext, packagetype in DIST_EXTENSIONS.items():
        if filename.endswith(ext):
            # Copy file to a temp directory under the user provided filename, we do this
            # because pkginfo validates that the filename has a valid extension before
            # reading it
            with tempfile.TemporaryDirectory() as td:
                temp_path = os.path.join(td, filename)
                artifact = Artifact.objects.get(pk=artifact_pk)
                shutil.copy2(artifact.file.path, temp_path)
                metadata = DIST_TYPES[packagetype](temp_path)
                metadata.packagetype = packagetype
                break
    else:
        raise serializers.ValidationError(_(
            "Extension on {} is not a valid python extension "
            "(.whl, .exe, .egg, .tar.gz, .tar.bz2, .zip)").format(filename)
        )
    data = parse_project_metadata(vars(metadata))
    data['classifiers'] = [{'name': classifier} for classifier in metadata.classifiers]
    data['packagetype'] = metadata.packagetype
    data['version'] = metadata.version
    data['filename'] = filename
    data['_relative_path'] = filename

    new_content = PythonPackageContent.objects.create(
        filename=filename,
        packagetype=metadata.packagetype,
        name=data['classifiers'],
        version=data['version']
    )

    queryset = PythonPackageContent.objects.filter(pk=new_content.pk)

    if repository_pk:
        repository = PythonRepository.objects.get(pk=repository_pk)
        with repository.new_version() as new_version:
            new_version.add_content(queryset)

    resource = CreatedResource(content_object=new_content)
    resource.save()
