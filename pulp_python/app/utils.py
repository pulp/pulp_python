import pkginfo
import re
import shutil
import tempfile
import json
from collections import defaultdict
from django.conf import settings
from jinja2 import Template
from packaging.utils import canonicalize_name
from packaging.requirements import Requirement
from packaging.version import parse, InvalidVersion
from pulpcore.plugin.models import Remote


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

DIST_EXTENSIONS = {
    ".whl": "bdist_wheel",
    ".exe": "bdist_wininst",
    ".egg": "bdist_egg",
    ".tar.bz2": "sdist",
    ".tar.gz": "sdist",
    ".zip": "sdist",
}

DIST_REGEXES = {
    # regex from https://github.com/pypa/pip/blob/18.0/src/pip/_internal/wheel.py#L569
    ".whl": re.compile(
        r"""^(?P<name>.+?)-(?P<version>.*?)
        ((-(?P<build>\d[^-]*?))?-(?P<pyver>.+?)-(?P<abi>.+?)-(?P<plat>.+?)
        \.whl|\.dist-info)$""",
        re.VERBOSE
    ),
    # regex based on https://setuptools.pypa.io/en/latest/deprecated/python_eggs.html#filename-embedded-metadata  # noqa: E501
    ".egg": re.compile(r"^(?P<name>.+?)-(?P<version>.*?)(-(?P<pyver>.+?(-(?P<plat>.+?))?))?\.egg|\.egg-info$"),  # noqa: E501
    # regex based on https://github.com/python/cpython/blob/v3.7.0/Lib/distutils/command/bdist_wininst.py#L292  # noqa: E501
    ".exe": re.compile(r"^(?P<name>.+?)-(?P<version>.*?)\.(?P<plat>.+?)(-(?P<pyver>.+?))?\.exe$"),
}

DIST_TYPES = {
    "bdist_wheel": pkginfo.Wheel,
    "bdist_wininst": pkginfo.Distribution,
    "bdist_egg": pkginfo.BDist,
    "sdist": pkginfo.SDist,
}


def parse_project_metadata(project):
    """
    Create a dictionary of python project metadata.

    Args:
        project (dict): Metadata relevant to the entire Python project

    Returns:
        dictionary: of python project metadata

    """
    return {
        # Core metadata
        # Version 1.0
        'author': project.get('author') or "",
        'author_email': project.get('author_email') or "",
        'description': project.get('description') or "",
        'home_page': project.get('home_page') or "",
        'keywords': project.get('keywords') or "",
        'license': project.get('license') or "",
        'metadata_version': project.get('metadata_version') or "",
        'name': project.get('name') or "",
        'platform': project.get('platform') or "",
        'summary': project.get('summary') or "",
        'version': project.get('version') or "",
        # Version 1.1
        'classifiers': json.dumps(project.get('classifiers', [])),
        'download_url': project.get('download_url') or "",
        'supported_platform': project.get('supported_platform') or "",
        # Version 1.2
        'maintainer': project.get('maintainer') or "",
        'maintainer_email': project.get('maintainer_email') or "",
        'obsoletes_dist': json.dumps(project.get('obsoletes_dist', [])),
        'project_url': project.get('project_url') or "",
        'project_urls': json.dumps(project.get('project_urls', {})),
        'provides_dist': json.dumps(project.get('provides_dist', [])),
        'requires_external': json.dumps(project.get('requires_external', [])),
        'requires_dist': json.dumps(project.get('requires_dist', [])),
        'requires_python': project.get('requires_python') or "",
        # Version 2.1
        'description_content_type': project.get('description_content_type') or "",
        'provides_extras': json.dumps(project.get('provides_extras', [])),
        # Version 2.2
        'dynamic': json.dumps(project.get('dynamic', [])),
        # Version 2.4
        'license_expression': project.get('license_expression') or "",
        'license_file': json.dumps(project.get('license_file', [])),
        # Release metadata
        'packagetype': project.get('packagetype') or "",
        'python_version': project.get('python_version') or "",
    }


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
    package = parse_project_metadata(project)

    package['filename'] = distribution.get('filename') or ""
    package['packagetype'] = distribution.get('packagetype') or ""
    package['version'] = version
    package['url'] = distribution.get('url') or ""
    package['sha256'] = distribution.get('digests', {}).get('sha256') or ""
    package['python_version'] = distribution.get('python_version') or package.get('python_version')
    package['requires_python'] = distribution.get('requires_python') or package.get('requires_python')  # noqa: E501

    return package


def get_project_metadata_from_artifact(filename, artifact):
    """
    Gets the metadata of a Python Package.

    Raises ValueError if filename has an unsupported extension
    """
    extensions = list(DIST_EXTENSIONS.keys())
    # Iterate through extensions since splitext does not support things like .tar.gz
    # If no supported extension is found, ValueError is raised here
    pkg_type_index = [filename.endswith(ext) for ext in extensions].index(True)
    packagetype = DIST_EXTENSIONS[extensions[pkg_type_index]]
    # Copy file to a temp directory under the user provided filename, we do this
    # because pkginfo validates that the filename has a valid extension before
    # reading it
    with tempfile.NamedTemporaryFile('wb', dir=".", suffix=filename) as temp_file:
        shutil.copyfileobj(artifact.file, temp_file)
        temp_file.flush()
        metadata = DIST_TYPES[packagetype](temp_file.name)
        metadata.packagetype = packagetype
        if packagetype == "sdist":
            metadata.python_version = "source"
        else:
            pyver = ""
            regex = DIST_REGEXES[extensions[pkg_type_index]]
            if bdist_name := regex.match(filename):
                pyver = bdist_name.group("pyver") or ""
            metadata.python_version = pyver
        return metadata


def artifact_to_python_content_data(filename, artifact, domain=None):
    """
    Takes the artifact/filename and returns the metadata needed to create a PythonPackageContent.
    """
    metadata = get_project_metadata_from_artifact(filename, artifact)
    data = parse_project_metadata(vars(metadata))
    data['sha256'] = artifact.sha256
    data['filename'] = filename
    data['pulp_domain'] = domain or artifact.pulp_domain
    data['_pulp_domain'] = data['pulp_domain']
    return data


def fetch_json_release_metadata(name: str, version: str, remotes: set[Remote]) -> dict:
    """
    Fetches metadata for a specific release from PyPI's JSON API. A release can contain
    multiple distributions. See https://docs.pypi.org/api/json/#get-a-release for more details.
    All remotes should have the same URL.

    Returns:
        Dict containing "info", "last_serial", "urls", and "vulnerabilities" keys.
    Raises:
        Exception if fetching from all remote URLs fails.
    """
    remote = next(iter(remotes))
    url = remote.get_remote_artifact_url(f"pypi/{name}/{version}/json")

    result = None
    for remote in remotes:
        downloader = remote.get_downloader(url=url, max_retries=1)
        try:
            result = downloader.fetch()
            break
        except Exception:
            continue

    if result:
        with open(result.path, "r") as file:
            json_data = json.load(file)
        return json_data
    else:
        raise Exception(f"Failed to fetch {url} from any remote.")


def python_content_to_json(base_path, content_query, version=None, domain=None):
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
    full_metadata.update({"releases": python_content_to_releases(content_query, base_path, domain)})
    full_metadata.update({"urls": python_content_to_urls(latest_content, base_path, domain)})
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
        # New core metadata (Version 2.1, 2.2, 2.4)
        "provides_extras": json_to_dict(content.provides_extras) or None,
        "dynamic": json_to_dict(content.dynamic) or None,
        "license_expression": content.license_expression or "",
        "license_file": json_to_dict(content.license_file) or None,
    }


def python_content_to_releases(content_query, base_path, domain=None):
    """
    Takes a QuerySet of PythonPackageContent and returns a dictionary of releases
    with each key being a version and value being a list of content for that version of the package
    """
    releases = defaultdict(lambda: [])
    for content in content_query:
        releases[content.version].append(
            python_content_to_download_info(content, base_path, domain)
        )
    return releases


def python_content_to_urls(contents, base_path, domain=None):
    """
    Takes the latest content in contents and returns a list of download information
    """
    return [python_content_to_download_info(content, base_path, domain) for content in contents]


def python_content_to_download_info(content, base_path, domain=None):
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
    origin = settings.CONTENT_ORIGIN or settings.PYPI_API_HOSTNAME or ""
    origin = origin.strip("/")
    prefix = settings.CONTENT_PATH_PREFIX.strip("/")
    base_path = base_path.strip("/")
    components = [origin, prefix, base_path, content.filename]
    if domain:
        components.insert(2, domain.name)
    url = "/".join(components)
    md5 = artifact.md5 if artifact and artifact.md5 else ""
    size = artifact.size if artifact and artifact.size else 0
    return {
        "comment_text": "",
        "digests": {"md5": md5, "sha256": content.sha256},
        "downloads": -1,
        "filename": content.filename,
        "has_sig": False,
        "md5_digest": md5,
        "packagetype": content.packagetype,
        "python_version": content.python_version,
        "requires_python": content.requires_python or None,
        "size": size,
        "upload_time": str(content.pulp_created),
        "upload_time_iso_8601": str(content.pulp_created.isoformat()),
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


class PackageIncludeFilter:
    """A special class to help filter Package's based on a remote's include/exclude"""

    def __init__(self, remote):
        self.remote = remote.cast()
        self._filter_includes = self._parse_packages(self.remote.includes)
        self._filter_excludes = self._parse_packages(self.remote.excludes)

    def _parse_packages(self, packages):
        config = defaultdict(lambda: defaultdict(list))
        for value in packages:
            requirement = Requirement(value)
            requirement.name = canonicalize_name(requirement.name)
            if requirement.specifier:
                requirement.specifier.prereleases = True
                config["range"][requirement.name].append(requirement)
            else:
                config["full"][requirement.name].append(requirement)
        return config

    def filter_project(self, project_name):
        """Return true/false if project_name would be allowed through remote's filters."""
        project_name = canonicalize_name(project_name)
        include_full = self._filter_includes.get("full", {})
        include_range = self._filter_includes.get("range", {})
        include = set(include_range.keys()).union(include_full.keys())
        if include and project_name not in include:
            return False

        exclude_full = self._filter_excludes.get("full", {})
        if project_name in exclude_full:
            return False

        return True

    def filter_release(self, project_name, version):
        """Returns true/false if release would be allowed through remote's filters."""
        project_name = canonicalize_name(project_name)
        if not self.filter_project(project_name):
            return False

        try:
            version = parse(version)
        except InvalidVersion:
            return False

        include_range = self._filter_includes.get("range", {})
        if project_name in include_range:
            for req in include_range[project_name]:
                if version in req.specifier:
                    break
            else:
                return False

        exclude_range = self._filter_excludes.get("range", {})
        if project_name in exclude_range:
            for req in exclude_range[project_name]:
                if version in req.specifier:
                    return False

        return True


_remote_filters = {}


def get_remote_package_filter(remote):
    if date_filter_tuple := _remote_filters.get(remote.pulp_id):
        last_update, rfilter = date_filter_tuple
        if last_update == remote.pulp_last_updated:
            return rfilter

    rfilter = PackageIncludeFilter(remote)
    _remote_filters[remote.pulp_id] = (remote.pulp_last_updated, rfilter)
    return rfilter
