from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content, Model, Publisher, Remote

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


class Classifier(Model):
    """
    Custom tags for classifier.

    Fields:

        name (models.TextField): The name of the classifier

    Relations:

        python_package_content (models.ForeignKey): The PythonPackageContent this classifier
        is associated with.
    """

    name = models.TextField()
    python_package_content = models.ForeignKey(
        "PythonPackageContent",
        related_name="classifiers",
        related_query_name="classifier",
        on_delete=models.CASCADE
    )


class DistributionDigest(Model):
    """
    A model of digests on an individual distribution.
    """

    type = models.TextField()
    digest = models.TextField()
    project_specifier = models.ForeignKey(
        "ProjectSpecifier",
        related_name="digests",
        related_query_name="distributiondigest",
        on_delete=models.CASCADE
    )


class ProjectSpecifier(Model):
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
        remote (models.ForeignKey): The remote this project specifier is associated with
    """

    name = models.TextField()
    version_specifier = models.TextField(blank=True, default="")
    remote = models.ForeignKey(
        "PythonRemote",
        related_name="projects",
        related_query_name="projectspecifier",
        on_delete=models.CASCADE
    )


class PythonPackageContent(Content):
    """
    A Content Type representing Python's Distribution Package.

    As defined in pep-0426 and pep-0345.

    https://www.python.org/dev/peps/pep-0491/
    https://www.python.org/dev/peps/pep-0345/
    """

    TYPE = 'python'
    # Required metadata
    filename = models.TextField(unique=True, db_index=True, blank=False)
    packagetype = models.TextField(blank=False, choices=PACKAGE_TYPES)
    name = models.TextField(blank=False)
    version = models.TextField(blank=False)
    # Optional metadata
    metadata_version = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    description = models.TextField(blank=True)
    keywords = models.TextField(blank=True)
    home_page = models.TextField(blank=True)
    download_url = models.TextField(blank=True)
    author = models.TextField(blank=True)
    author_email = models.TextField(blank=True)
    maintainer = models.TextField(blank=True)
    maintainer_email = models.TextField(blank=True)
    license = models.TextField(blank=True)
    requires_python = models.TextField(blank=True)
    project_url = models.TextField(blank=True)
    platform = models.TextField(blank=True)
    supported_platform = models.TextField(blank=True)
    requires_dist = models.TextField(default="[]", blank=False)
    provides_dist = models.TextField(default="[]", blank=False)
    obsoletes_dist = models.TextField(default="[]", blank=False)
    requires_external = models.TextField(default="[]", blank=False)

    @property
    def artifact(self):
        """
        Return the artifact id (there is only one for this content type).
        """
        return self.artifacts.get().pk

    class Meta:
        unique_together = ('filename',)

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


class PythonPublisher(Publisher):
    """
    A Publisher for PythonContent.
    """

    TYPE = 'python'


class PythonRemote(Remote):
    """
    A Remote for Python Content.
    """

    TYPE = 'python'
