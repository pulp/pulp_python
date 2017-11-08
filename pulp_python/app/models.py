from gettext import gettext as _
from logging import getLogger

from django.db import models

from pulpcore.plugin.models import (Artifact, Content, ContentArtifact, RemoteArtifact, Importer,
                                    ProgressBar, Publisher, RepositoryContent, PublishedArtifact,
                                    PublishedMetadata)
from pulpcore.plugin.tasking import Task


log = getLogger(__name__)


class PythonContent(Content):
    """
    The "python" content type.

    Define fields you need for your new content type and
    specify uniqueness constraint to identify unit of this type.

    For example::

        field1 = models.TextField()
        field2 = models.IntegerField()
        field3 = models.CharField()

        class Meta:
            unique_together = (field1, field2)
    """

    TYPE = 'python'


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
    An Importer for PythonContent.

    Define any additional fields for your new importer if needed.
    A ``sync`` method should be defined.
    It is responsible for parsing metadata of the content,
    downloading of the content and saving it to Pulp.
    """

    TYPE = 'python'

    def sync(self):
        """
        Synchronize the repository with the remote repository.
        """
        raise NotImplementedError
