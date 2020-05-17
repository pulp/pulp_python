from logging import getLogger

from django.contrib.postgres.fields import JSONField
from django.db import models

from pulpcore.plugin.models import (
    Content,
    Publication,
    PublicationDistribution,
    Remote,
    Repository
)

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


class ProjectSpecifier(models.Model):
    """
    A specifier of a python project.

    Example:

        digests: ["sha256:0000"] will only match the distributions that has the exact hash
        name: "projectname" without specifiers will match every distribution in the project.
        version_specifier: "==1.0.0" will match all distributions matching version
        version_specifier: "~=1.0.0" will match all major version 1 distributions
        version_specifier: "==1.0.0" digests: ["sha256:0000"] will only match the distributions
            with the hash and with version 1.0.0
        version_specifier: ">=0.9,<1.0" will match all versions matching 0.9.*

    Fields:

        name (models.TextField): The name of a python project
        version_specifier (models.TextField):  Used to filter the versions of a project to sync
        exclude (models.BooleanField): Whether the specified projects should excluded or included

    Relations:

        remote (models.ForeignKey): The remote this project specifier is associated with
        include (models.BooleanField): Used to blacklist/whitelist projects to sync
    """

    name = models.TextField()
    version_specifier = models.TextField(default="")
    exclude = models.BooleanField(default=False)

    remote = models.ForeignKey(
        "PythonRemote",
        related_name="projects",
        related_query_name="projectspecifier",
        on_delete=models.CASCADE
    )

    class Meta:
        unique_together = ('name', 'version_specifier', 'exclude', 'remote')


class PythonDistribution(PublicationDistribution):
    """
    Distribution for 'Python' Content.
    """

    TYPE = 'python'

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

    @property
    def includes(self):
        """
        Specify include list.
        """
        return ProjectSpecifier.objects.filter(remote=self, exclude=False)

    @property
    def excludes(self):
        """
        Specify exclude list.
        """
        return ProjectSpecifier.objects.filter(remote=self, exclude=True)

    class Meta:
        default_related_name = "%(app_label)s_%(model_name)s"
