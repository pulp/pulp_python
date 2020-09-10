import json
from collections import defaultdict
from django.conf import settings
from packaging.version import parse

PYPI_LAST_SERIAL = "X-PYPI-LAST-SERIAL"
"""TODO This serial constant is temporary until Python repositories implements serials"""
PYPI_SERIAL_CONSTANT = 1000000000


def parse_project_metadata(project):
    """
    Create a dictionary of python project metadata.

    Args:
        project (dict): Metadata relevant to the entire Python project

    Returns:
        dictionary: of python project metadata

    """
    package = {}
    package['name'] = project.get('name') or ""
    package['metadata_version'] = project.get('metadata_version') or ""
    package['summary'] = project.get('summary') or ""
    package['description'] = project.get('description') or ""
    package['keywords'] = project.get('keywords') or ""
    package['home_page'] = project.get('home_page') or ""
    package['download_url'] = project.get('download_url') or ""
    package['author'] = project.get('author') or ""
    package['author_email'] = project.get('author_email') or ""
    package['maintainer'] = project.get('maintainer') or ""
    package['maintainer_email'] = project.get('maintainer_email') or ""
    package['license'] = project.get('license') or ""
    package['requires_python'] = project.get('requires_python') or ""
    package['project_url'] = project.get('project_url') or ""
    package['platform'] = project.get('platform') or ""
    package['supported_platform'] = project.get('supported_platform') or ""
    package['requires_dist'] = json.dumps(project.get('requires_dist', []))
    package['provides_dist'] = json.dumps(project.get('provides_dist', []))
    package['obsoletes_dist'] = json.dumps(project.get('obsoletes_dist', []))
    package['requires_external'] = json.dumps(project.get('requires_external', []))
    package['classifiers'] = json.dumps(project.get('classifiers', []))

    return package


def parse_metadata(project, version, distribution):
    """
    Extract metadata from a distribution.

    Create a dictionary of metadata needed to create a PythonContentUnit from
    the project, version, and distribution metadata.

    Args:
        project (dict): Metadata relevant to the entire Python project
        version (string): Version of distribution
        distribution (dict): Metadata of a single Python distribution

    Returns:
        dictionary: of useful python metadata

    """
    package = {}

    package['filename'] = distribution.get('filename') or ""
    package['packagetype'] = distribution.get('packagetype') or ""
    package['version'] = version
    package['url'] = distribution.get('url') or ""
    package['sha256_digest'] = distribution.get('digests', {}).get('sha256') or ""
    package['python_version'] = distribution.get('python_version') or ""

    package.update(parse_project_metadata(project))

    return package


def python_content_to_json(base_path, content_query, version=None):
    """
    Converts a QuerySet of PythonPackageContent into the PyPi JSON format
    https://www.python.org/dev/peps/pep-0566/
    JSON metadata has:
        info: Dict
        last_serial: int
        releases: Dict
        urls: Dict

    Returns None if version is specified but not found within content_query
    """
    full_metadata = {"last_serial": 0}  # For now the serial field isn't supported by Pulp
    latest_content = latest_content_version(content_query, version)
    if not latest_content:
        return None
    full_metadata.update({"info": python_content_to_info(latest_content[0])})
    full_metadata.update({"releases": python_content_to_releases(content_query, base_path)})
    full_metadata.update({"urls": python_content_to_urls(latest_content, base_path)})
    return full_metadata


def latest_content_version(content_query, version):
    """
    Walks through the content QuerySet and finds the instances that is the latest version.
    If 'version' is specified, the function instead tries to find content instances
    with that version and will return an empty list if nothing is found
    """
    latest_version = version
    latest_content = []
    for content in content_query:
        if version and parse(version) == parse(content.version):
            latest_content.append(content)
        elif not latest_version or parse(content.version) > parse(latest_version):
            latest_content = [content]
            latest_version = content.version
        elif parse(content.version) == parse(latest_version):
            latest_content.append(content)

    return latest_content


def python_content_to_info(latest_content):
    """
    Takes in a PythonPackageContent instance and returns a dictionary of the Info fields
    """
    return {
        "name": latest_content.name,
        "version": latest_content.version,
        "summary": latest_content.summary or None,
        "description": latest_content.description or None,
        "keywords": latest_content.keywords or None,
        "home_page": latest_content.home_page or None,
        "downloads": {"last_day": -1, "last_month": -1, "last_week": -1},
        "download_url": latest_content.download_url or None,
        "author": latest_content.author or None,
        "author_email": latest_content.author_email or None,
        "maintainer": latest_content.maintainer or None,
        "maintainer_email": latest_content.maintainer_email or None,
        "license": latest_content.license or None,
        "requires_python": latest_content.requires_python or None,
        "project_url": latest_content.project_url or None,
        "platform": latest_content.platform or None,
        "requires_dist": json.loads(latest_content.requires_dist) or None,
        "classifiers": json.loads(latest_content.classifiers) or None,
    }
    # fields missing: bugtrack_url, description_content_type, docs_url, package_url,
    # project_urls {Download, Homepage}, release_url, yanked, yanked_reason


def python_content_to_releases(content_query, base_path):
    """
    Takes a QuerySet of PythonPackageContent and returns a dictionary of releases
    with each key being a version and value being a list of content for that version of the package
    """
    releases = defaultdict(lambda: [])
    for content in content_query:
        releases[content.version].append(python_content_to_download_info(content, base_path))
    return releases


def python_content_to_urls(contents, base_path):
    """
    Takes the latest content in contents and returns a list of download information
    """
    return [python_content_to_download_info(content, base_path) for content in contents]


def python_content_to_download_info(content, base_path):
    """
    Takes in a PythonPackageContent and base path of the distribution to create a dictionary of
    download information for that content. This dictionary is used by Releases and Urls.
    """
    def find_artifact():
        _art = content_artifact.artifact
        if not _art:
            from pulpcore.plugin import models
            _art = models.RemoteArtifact.objects.filter(content_artifact=content_artifact).first()
        return _art

    content_artifact = content.contentartifact_set.first()
    artifact = find_artifact()
    origin = settings.CONTENT_ORIGIN.strip("/")
    prefix = settings.CONTENT_PATH_PREFIX.strip("/")
    base_path = base_path.strip("/")
    url = "/".join((origin, prefix, base_path, content.filename))
    return {
        "comment_text": "",
        "digests": {"md5": artifact.md5, "sha256": artifact.sha256},
        "downloads": -1,
        "filename": content.filename,
        "has_sig": False,
        "md5_digest": artifact.md5,
        "packagetype": content.packagetype,
        "python_version": content.python_version,
        "requires_python": content.requires_python or None,
        "size": artifact.size,
        "upload_time": str(artifact.pulp_created),
        "upload_time_iso_8601": str(artifact.pulp_created.isoformat()),
        "url": url,
        "yanked": False,
        "yanked_reason": None
    }
