import json
from collections import defaultdict
from django.conf import settings
from jinja2 import Template
from packaging.utils import canonicalize_name
from packaging.version import parse

PYPI_LAST_SERIAL = "X-PYPI-LAST-SERIAL"
"""TODO This serial constant is temporary until Python repositories implements serials"""
PYPI_SERIAL_CONSTANT = 1000000000

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
    package['project_url'] = project.get('project_url') or ""
    package['platform'] = project.get('platform') or ""
    package['supported_platform'] = project.get('supported_platform') or ""
    package['requires_dist'] = json.dumps(project.get('requires_dist', []))
    package['provides_dist'] = json.dumps(project.get('provides_dist', []))
    package['obsoletes_dist'] = json.dumps(project.get('obsoletes_dist', []))
    package['requires_external'] = json.dumps(project.get('requires_external', []))
    package['classifiers'] = json.dumps(project.get('classifiers', []))
    package['project_urls'] = json.dumps(project.get('project_urls', {}))
    package['description_content_type'] = project.get('description_content_type') or ""

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
    package['sha256'] = distribution.get('digests', {}).get('sha256') or ""
    package['python_version'] = distribution.get('python_version') or ""
    package['requires_python'] = distribution.get('requires_python') or ""

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


def json_to_dict(data):
    """
    Converts a JSON string into a Python dictionary.

    Args:
        data (string): JSON string

    Returns:
        dictionary: of JSON string

    """
    if isinstance(data, dict):
        return data

    return json.loads(data)


def python_content_to_info(content):
    """
    Takes in a PythonPackageContent instance and returns a dictionary of the Info fields
    """
    return {
        "name": content.name,
        "version": content.version,
        "summary": content.summary or "",
        "keywords": content.keywords or "",
        "description": content.description or "",
        "description_content_type": content.description_content_type or "",
        "bugtrack_url": None,  # These two are basically never used
        "docs_url": None,
        "downloads": {"last_day": -1, "last_month": -1, "last_week": -1},
        "download_url": content.download_url or "",
        "home_page": content.home_page or "",
        "author": content.author or "",
        "author_email": content.author_email or "",
        "maintainer": content.maintainer or "",
        "maintainer_email": content.maintainer_email or "",
        "license": content.license or "",
        "requires_python": content.requires_python or None,
        "package_url": content.project_url or "",  # These two are usually identical
        "project_url": content.project_url or "",  # They also usually point to PyPI
        "release_url": f"{content.project_url}{content.version}/" if content.project_url else "",
        "project_urls": json_to_dict(content.project_urls) or None,
        "platform": content.platform or "",
        "requires_dist": json_to_dict(content.requires_dist) or None,
        "classifiers": json_to_dict(content.classifiers) or None,
        "yanked": False,  # These are no longer used on PyPI, but are still present
        "yanked_reason": None,
    }


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


def write_simple_index(project_names, streamed=False):
    """Writes the simple index."""
    simple = Template(simple_index_template)
    context = {"projects": ((x, canonicalize_name(x)) for x in project_names)}
    return simple.stream(**context) if streamed else simple.render(**context)


def write_simple_detail(project_name, project_packages, streamed=False):
    """Writes the simple detail page of a package."""
    detail = Template(simple_detail_template)
    context = {"project_name": project_name, "project_packages": project_packages}
    return detail.stream(**context) if streamed else detail.render(**context)
