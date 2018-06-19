import json


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

    package.update(parse_project_metadata(project))

    return package
