from gettext import gettext as _
import logging
import os

from django.core.files import File
from packaging.utils import canonicalize_name

from pulpcore.plugin import models

from pulp_python.app import models as python_models
from pulp_python.app.utils import write_simple_index, write_simple_detail


log = logging.getLogger(__name__)


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

    with python_models.PythonPublication.create(repository_version, pass_through=True) as pub:
        write_simple_api(pub)

    log.info(_('Publication: {pk} created').format(pk=pub.pk))
    return pub


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

    # write the root index, which lists all of the projects for which there is a package available
    index_path = '{simple_dir}index.html'.format(simple_dir=simple_dir)
    with open(index_path, 'w') as index:
        index.write(write_simple_index(project_names))

    index_metadata = models.PublishedMetadata.create_from_file(
        relative_path=index_path,
        publication=publication,
        file=File(open(index_path, 'rb'))
    )
    index_metadata.save()

    if len(project_names) == 0:
        return

    packages = python_models.PythonPackageContent.objects.filter(
        pk__in=publication.repository_version.content
    )
    releases = packages.order_by("name").values("name", "filename", "sha256")

    ind = 0
    current_name = project_names[ind]
    package_releases = []
    for release in releases.iterator():
        if release['name'] != current_name:
            write_project_page(
                name=canonicalize_name(current_name),
                simple_dir=simple_dir,
                package_releases=package_releases,
                publication=publication
            )
            package_releases = []
            ind += 1
            current_name = project_names[ind]
        relative_path = release['filename']
        path = f"../../{relative_path}"
        checksum = release['sha256']
        package_releases.append((relative_path, path, checksum))
    # Write the final project's page
    write_project_page(
        name=canonicalize_name(current_name),
        simple_dir=simple_dir,
        package_releases=package_releases,
        publication=publication
    )


def write_project_page(name, simple_dir, package_releases, publication):
    """Writes a project's simple page."""
    project_dir = f'{simple_dir}{name}/'
    os.mkdir(project_dir)
    metadata_relative_path = f'{project_dir}index.html'

    with open(metadata_relative_path, 'w') as simple_metadata:
        simple_metadata.write(write_simple_detail(name, package_releases))

    project_metadata = models.PublishedMetadata.create_from_file(
        relative_path=metadata_relative_path,
        publication=publication,
        file=File(open(metadata_relative_path, 'rb'))
    )
    project_metadata.save()  # change to bulk create when multi-table supported
