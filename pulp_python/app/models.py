from logging import getLogger

from aiohttp.web import json_response
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ObjectDoesNotExist
from django.db import models
from django.conf import settings
from pulpcore.plugin.models import (
    AutoAddObjPermsMixin,
    Content,
    Publication,
    Distribution,
    Remote,
    Repository,
)
from pulpcore.plugin.responses import ArtifactResponse

from pathlib import PurePath
from .utils import (
    artifact_to_python_content_data,
    canonicalize_name,
    python_content_to_json,
    PYPI_LAST_SERIAL,
    PYPI_SERIAL_CONSTANT,
)
from pulpcore.plugin.repo_version_utils import remove_duplicates, validate_repo_version
from pulpcore.plugin.util import get_domain_pk, get_domain

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

PLATFORMS = (
    ("windows", "windows"),
    ("macos", "macos"),
    ("freebsd", "freebsd"),
    ("linux", "linux"),
)


class PythonDistribution(Distribution, AutoAddObjPermsMixin):
    """
    Distribution for 'Python' Content.
    """

    TYPE = "python"

    allow_uploads = models.BooleanField(default=True)

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
        domain = get_domain()
        if path.match("pypi/*/*/json"):
            version = path.parts[2]
            name = path.parts[1]
        elif path.match("pypi/*/json"):
            name = path.parts[1]
        elif len(path.parts) and path.parts[0] == "simple":
            # Temporary fix for PublishedMetadata not being properly served from remote storage
            # https://github.com/pulp/pulp_python/issues/413
            if domain.storage_class != "pulpcore.app.models.storage.FileSystem":
                if self.publication or self.repository:
                    try:
                        publication = self.publication or Publication.objects.filter(
                            repository_version=self.repository.latest_version()
                        ).latest("pulp_created")
                    except ObjectDoesNotExist:
                        return None
                    if len(path.parts) == 2:
                        path = PurePath(f"simple/{canonicalize_name(path.parts[1])}")
                    rel_path = f"{path}/index.html"
                    try:
                        ca = (
                            publication.published_artifact.select_related(
                                "content_artifact",
                                "content_artifact__artifact",
                            )
                            .get(relative_path=rel_path)
                            .content_artifact
                        )
                    except ObjectDoesNotExist:
                        return None
                    headers = {"Content-Type": "text/html"}
                    return ArtifactResponse(ca.artifact, headers=headers)

        if name:
            normalized = canonicalize_name(name)
            package_content = PythonPackageContent.objects.filter(
                pk__in=self.publication.repository_version.content, name__normalize=normalized
            )
            # TODO Change this value to the Repo's serial value when implemented
            headers = {PYPI_LAST_SERIAL: str(PYPI_SERIAL_CONSTANT)}
            if not settings.DOMAIN_ENABLED:
                domain = None
            json_body = python_content_to_json(
                self.base_path, package_content, version=version, domain=domain
            )
            if json_body:
                return json_response(json_body, headers=headers)

        return None

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("manage_roles_pythondistribution", "Can manage roles on python distributions"),
        ]


class NormalizeName(models.Transform):
    """A transform field to normalize package names according to PEP426."""

    function = "REGEXP_REPLACE"
    template = "LOWER(%(function)s(%(expressions)s, '(\.|_|-)', '-', 'ig'))"  # noqa:W605
    lookup_name = "normalize"


class PythonPackageContent(Content):
    """
    A Content Type representing Python's Distribution Package.

    Core Metadata:
        https://packaging.python.org/en/latest/specifications/core-metadata/

    Release metadata (JSON API):
        https://docs.pypi.org/api/json/

    File Formats:
        https://packaging.python.org/en/latest/specifications/source-distribution-format/
        https://packaging.python.org/en/latest/specifications/binary-distribution-format/
    """
    # Core metadata
    # Version 1.0
    author = models.TextField()
    author_email = models.TextField()
    description = models.TextField()
    home_page = models.TextField()  # Deprecated in favour of Project-URL
    keywords = models.TextField()
    license = models.TextField()  # Deprecated in favour of License-Expression
    metadata_version = models.TextField()
    name = models.TextField()
    platform = models.TextField()
    summary = models.TextField()
    version = models.TextField()
    # Version 1.1
    classifiers = models.JSONField(default=list)
    download_url = models.TextField()  # Deprecated in favour of Project-URL
    supported_platform = models.TextField()
    # Version 1.2
    maintainer = models.TextField()
    maintainer_email = models.TextField()
    obsoletes_dist = models.JSONField(default=list)
    project_url = models.TextField()
    project_urls = models.JSONField(default=dict)
    provides_dist = models.JSONField(default=list)
    requires_external = models.JSONField(default=list)
    requires_dist = models.JSONField(default=list)
    requires_python = models.TextField()
    # Version 2.1
    description_content_type = models.TextField()
    provides_extras = models.JSONField(default=list)
    # Version 2.2
    dynamic = models.JSONField(default=list)
    # Version 2.4
    license_expression = models.TextField()
    license_file = models.JSONField(default=list)

    # Release metadata
    filename = models.TextField(db_index=True)
    packagetype = models.TextField(choices=PACKAGE_TYPES)
    python_version = models.TextField()
    sha256 = models.CharField(db_index=True, max_length=64)

    # From pulpcore
    PROTECTED_FROM_RECLAIM = False
    TYPE = "python"
    _pulp_domain = models.ForeignKey(
        "core.Domain", default=get_domain_pk, on_delete=models.PROTECT
    )
    name.register_lookup(NormalizeName)
    repo_key_fields = ("filename",)

    @staticmethod
    def init_from_artifact_and_relative_path(artifact, relative_path):
        """Used when downloading package from pull-through cache."""
        path = PurePath(relative_path)
        data = artifact_to_python_content_data(path.name, artifact, domain=get_domain())
        return PythonPackageContent(**data)

    def __str__(self):
        """
        Provide more useful repr information.

        Overrides Content.str to provide the distribution version and type at
        the end.

        e.g. <PythonPackageContent: shelf-reader [version] (whl)>

        """
        return "<{obj_name}: {name} [{version}] ({type})>".format(
            obj_name=self._meta.object_name,
            name=self.name,
            version=self.version,
            type=self.packagetype,
        )

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        unique_together = ("sha256", "_pulp_domain")


class PythonPublication(Publication, AutoAddObjPermsMixin):
    """
    A Publication for PythonContent.
    """

    TYPE = "python"

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("manage_roles_pythonpublication", "Can manage roles on python publications"),
        ]


class PythonRemote(Remote, AutoAddObjPermsMixin):
    """
    A Remote for Python Content.

    Fields:

        prereleases (models.BooleanField): Whether to sync pre-release versions of packages.
    """

    TYPE = "python"
    DEFAULT_DOWNLOAD_CONCURRENCY = 10
    prereleases = models.BooleanField(default=False)
    includes = models.JSONField(default=list)
    excludes = models.JSONField(default=list)
    package_types = ArrayField(
        models.CharField(max_length=15, blank=True), choices=PACKAGE_TYPES, default=list
    )
    keep_latest_packages = models.IntegerField(default=0)
    exclude_platforms = ArrayField(
        models.CharField(max_length=10, blank=True), choices=PLATFORMS, default=list
    )

    def get_remote_artifact_url(self, relative_path=None, request=None):
        """Get url for remote_artifact"""
        if request and (url := request.query.get("redirect")):
            # This is a special case for pull-through caching
            return url
        return super().get_remote_artifact_url(relative_path, request=request)

    def get_remote_artifact_content_type(self, relative_path=None):
        """Return PythonPackageContent."""
        return PythonPackageContent

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("manage_roles_pythonremote", "Can manage roles on python remotes"),
        ]


class PythonRepository(Repository, AutoAddObjPermsMixin):
    """
    Repository for "python" content.
    """

    TYPE = "python"
    CONTENT_TYPES = [PythonPackageContent]
    REMOTE_TYPES = [PythonRemote]
    PULL_THROUGH_SUPPORTED = True

    autopublish = models.BooleanField(default=False)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
        permissions = [
            ("sync_pythonrepository", "Can start a sync task"),
            ("modify_pythonrepository", "Can modify content of the repository"),
            ("manage_roles_pythonrepository", "Can manage roles on python repositories"),
            ("repair_pythonrepository", "Can repair repository versions"),
        ]

    def on_new_version(self, version):
        """
        Called when new repository versions are created.

        Args:
            version: The new repository version
        """
        super().on_new_version(version)

        # avoid circular import issues
        from pulp_python.app import tasks

        if self.autopublish:
            tasks.publish(repository_version_pk=version.pk)

    def finalize_new_version(self, new_version):
        """
        Remove duplicate packages that have the same filename.
        """
        remove_duplicates(new_version)
        validate_repo_version(new_version)
