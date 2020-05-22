from gettext import gettext as _
import logging
import os

from packaging.utils import canonicalize_name
from django.core.files import File
from django.template import Context, Template

from pulpcore.plugin import models
from pulpcore.plugin.tasking import WorkingDirectory

from pulp_python.app import models as python_models


log = logging.getLogger(__name__)

simple_index_template = """<!DOCTYPE html>
<html>
  <head>
    <title>Simple Index</title>
    <meta name="api-version" value="2" />
  </head>
  <body>
    {% for name, canonical_name in projects %}
    <a href="{{ canonical_name }}/">{{ name }}</a><br/>
    {% endfor %}
  </body>
</html>
"""


simple_detail_template = """<!DOCTYPE html>
<html>
<head>
  <title>Links for {{ project_name }}</title>
  <meta name="api-version" value="2" />
</head>
<body>
    <h1>Links for {{ project_name }}</h1>
    {% for name, path, sha256 in project_packages %}
    <a href="{{ path }}#sha256={{ sha256 }}" rel="internal">{{ name }}</a><br/>
    {% endfor %}
</body>
</html>
"""


def publish(repository_version_pk):
    """
    Create a Publication based on a RepositoryVersion.

    Args:
        repository_version_pk (str): Create a Publication from this RepositoryVersion.

    """
    repository_version = models.RepositoryVersion.objects.get(pk=repository_version_pk)

    log.info(_('Publishing: repository={repo}, version={version}').format(
        repo=repository_version.repository.name,
        version=repository_version.number,
    ))

    with WorkingDirectory():
        with python_models.PythonPublication.create(repository_version) as publication:
            write_simple_api(publication)

    log.info(_('Publication: {pk} created').format(pk=publication.pk))


def write_simple_api(publication):
    """
    Write metadata for the simple API.

    Writes metadata mimicking the simple api of PyPI for all python packages
    in the repository version.

    https://wiki.python.org/moin/PyPISimple

    Args:
        publication (pulpcore.plugin.models.Publication): A publication to generate metadata for

    """
    simple_dir = 'simple/'
    os.mkdir(simple_dir)
    project_names = (
        python_models.PythonPackageContent.objects.filter(
            pk__in=publication.repository_version.content
        )
        .order_by('name')
        .values_list('name', flat=True)
        .distinct()
    )

    index_names = [(name, canonicalize_name(name)) for name in project_names]

    # write the root index, which lists all of the projects for which there is a package available
    index_path = '{simple_dir}index.html'.format(simple_dir=simple_dir)
    with open(index_path, 'w') as index:
        context = Context({'projects': index_names})
        template = Template(simple_index_template)
        index.write(template.render(context))

    index_metadata = models.PublishedMetadata.create_from_file(
        relative_path=index_path,
        publication=publication,
        file=File(open(index_path, 'rb'))
    )
    index_metadata.save()

    for (name, canonical_name) in index_names:
        project_dir = '{simple_dir}{name}/'.format(simple_dir=simple_dir, name=canonical_name)
        os.mkdir(project_dir)

        packages = python_models.PythonPackageContent.objects.filter(name=name)

        package_detail_data = []

        for package in packages:
            artifact_set = package.contentartifact_set.all()
            for content_artifact in artifact_set:
                published_artifact = models.PublishedArtifact(
                    relative_path=content_artifact.relative_path,
                    publication=publication,
                    content_artifact=content_artifact
                )
                published_artifact.save()

                checksum = content_artifact.artifact.sha256
                path = "../../{}".format(package.filename)
                package_detail_data.append((package.filename, path, checksum))

        metadata_relative_path = '{project_dir}index.html'.format(project_dir=project_dir)

        with open(metadata_relative_path, 'w') as simple_metadata:
            context = Context({
                'project_name': name,
                'project_packages': package_detail_data
            })
            template = Template(simple_detail_template)
            simple_metadata.write(template.render(context))

        project_metadata = models.PublishedMetadata.create_from_file(
            relative_path=metadata_relative_path,
            publication=publication,
            file=File(open(metadata_relative_path, 'rb'))
        )
        project_metadata.save()
