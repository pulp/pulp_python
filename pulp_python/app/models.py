from logging import getLogger

from django.db import models

from pulpcore.plugin.models import Content, Importer, Model, Publisher


log = getLogger(__name__)


PACKAGE_TYPES = (("bdist_dmg", "bdist_dmg"), ("bdist_dumb", "bdist_dumb"),
                 ("bdist_egg", "bdist_egg"), ("bdist_msi", "bdist_msi"),
                 ("bdist_rpm", "bdist_rpm"), ("bdist_wheel", "bdist_wheel"),
                 ("bdist_wininst", "bdist_wininst"), ("sdist", "sdist"))


class Classifier(Model):
    """
    Custom tags for classifier

    Fields:

        name (models.TextField): The name of the classifier

    Relations:

        python_package_content (models.ForeignKey): The PythonPackageContent this classifier
        is associated with.

    """

    name = models.TextField()
    python_package_content = models.ForeignKey("PythonPackageContent", related_name="classifiers",
                                               related_query_name="classifier")


class PythonPackageContent(Content):
    """
    A Content Type representing Python's Distribution Package as
    defined in pep-0426 and pep-0345
    https://www.python.org/dev/peps/pep-0491/
    https://www.python.org/dev/peps/pep-0345/
    """

    TYPE = 'python'
    filename = models.TextField(unique=True, db_index=True, blank=False)
    packagetype = models.TextField(blank=False, choices=PACKAGE_TYPES)
    name = models.TextField(blank=False)
    version = models.TextField(blank=False)
    metadata_version = models.TextField(null=True)
    summary = models.TextField(null=True)
    description = models.TextField(null=True)
    keywords = models.TextField(null=True)
    home_page = models.TextField(null=True)
    download_url = models.TextField(null=True)
    author = models.TextField(null=True)
    author_email = models.TextField(null=True)
    maintainer = models.TextField(null=True)
    maintainer_email = models.TextField(null=True)
    license = models.TextField(null=True)
    requires_python = models.TextField(null=True)
    project_url = models.TextField(null=True)
    platform = models.TextField(null=True)
    supported_platform = models.TextField(null=True)
    requires_dist = models.TextField(default="[]", blank=False)
    provides_dist = models.TextField(default="[]", blank=False)
    obsoletes_dist = models.TextField(default="[]", blank=False)
    requires_external = models.TextField(default="[]", blank=False)

    class Meta:
        unique_together = (
            'filename',
        )


class PythonPublisher(Publisher):
    """
    A Publisher for PythonContent.

    Define any additional fields for your new publisher if needed.
    A ``publish`` method should be defined.
    It is responsible for publishing metadata and artifacts
    which belongs to a specific repository.
    """

    TYPE = 'python'

    def publish(self):
        """
        Publish the repository.
        """
        raise NotImplementedError


class PythonImporter(Importer):
    """
    An Importer for Python Content.

    Attributes:
        projects (list): A list of python projects to sync
    """

    TYPE = 'python'
    projects = models.TextField(null=True)
