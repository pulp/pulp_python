from logging import getLogger

from aiohttp.web import json_response
from django.contrib.postgres.fields import JSONField
from django.db import models

from pulpcore.plugin.models import (
    Content,
    Publication,
    PublicationDistribution,
    Remote,
    Repository
)

from pathlib import PurePath
from .utils import python_content_to_json, PYPI_LAST_SERIAL, PYPI_SERIAL_CONSTANT

log = getLogger(__name__)


PACKAGE_TYPES = (
    ("bdist_dmg", "bdist_dmg"),
    ("bdist_dumb", "bdist_dumb"),
    ("bdist_egg", "bdist_egg"),
    ("bdist_msi", "bdist_msi"),
    ("bdist_rpm", "bdist_rpm"),
    ("bdist_wheel", "bdist_wheel"),
    ("bdist_wininst", "bdist_wininst"),
    ("sdist", "sdist"),
)


class PythonDistribution(PublicationDistribution):
    """
    Distribution for 'Python' Content.
    """

    TYPE = 'python'

    def content_handler(self, path):
        """
        Handler to serve extra, non-Artifact content for this Distribution

        Args:
            path (str): The path being requested
        Returns:
            None if there is no content to be served at path. Otherwise a
            aiohttp.web_response.Response with the content.
        """
        path = PurePath(path)
        name = None
        version = None
        if path.match("pypi/*/*/json"):
            version = path.parts[2]
            name = path.parts[1]
        elif path.match("pypi/*/json"):
            name = path.parts[1]
        if name:
            package_content = PythonPackageContent.objects.filter(
                pk__in=self.publication.repository_version.content,
                name__iexact=name
            )
            # TODO Change this value to the Repo's serial value when implemented
            headers = {PYPI_LAST_SERIAL: str(PYPI_SERIAL_CONSTANT)}
            json_body = python_content_to_json(self.base_path, package_content, version=version)
            if json_body:
                return json_response(json_body, headers=headers)

        return None

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class PythonPackageContent(Content):
    """
    A Content Type representing Python's Distribution Package.

    As defined in pep-0426 and pep-0345.

    https://www.python.org/dev/peps/pep-0491/
    https://www.python.org/dev/peps/pep-0345/
    """

    TYPE = 'python'
    # Required metadata
    filename = models.TextField(unique=True, db_index=True)
    packagetype = models.TextField(choices=PACKAGE_TYPES)
    name = models.TextField()
    version = models.TextField()
    # Optional metadata
    python_version = models.TextField()
    metadata_version = models.TextField()
    summary = models.TextField()
    description = models.TextField()
    keywords = models.TextField()
    home_page = models.TextField()
    download_url = models.TextField()
    author = models.TextField()
    author_email = models.TextField()
    maintainer = models.TextField()
    maintainer_email = models.TextField()
    license = models.TextField()
    requires_python = models.TextField()
    project_url = models.TextField()
    platform = models.TextField()
    supported_platform = models.TextField()
    requires_dist = JSONField(default=list)
    provides_dist = JSONField(default=list)
    obsoletes_dist = JSONField(default=list)
    requires_external = JSONField(default=list)
    classifiers = JSONField(default=list)

    def __str__(self):
        """
        Provide more useful repr information.

        Overrides Content.str to provide the distribution version and type at
        the end.

        e.g. <PythonPackageContent: shelf-reader [version] (whl)>

        """
        return '<{obj_name}: {name} [{version}] ({type})>'.format(
            obj_name=self._meta.object_name,
            name=self.name,
            version=self.version,
            type=self.packagetype
        )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ('filename',)


class PythonRepository(Repository):
    """
    Repository for "python" content.
    """

    TYPE = "python"
    CONTENT_TYPES = [PythonPackageContent]

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class PythonPublication(Publication):
    """
    A Publication for PythonContent.
    """

    TYPE = 'python'

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"


class PythonRemote(Remote):
    """
    A Remote for Python Content.

    Fields:

        prereleases (models.BooleanField): Whether to sync pre-release versions of packages.
    """

    TYPE = 'python'
    prereleases = models.BooleanField(default=False)
    includes = JSONField(default=list)
    excludes = JSONField(default=list)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
