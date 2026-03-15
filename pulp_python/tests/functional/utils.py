import requests

from urllib.parse import urljoin
from lxml import html


def _validate_metadata_sha_digest(link, filename, metadata_sha_digests):
    """
    Validate data-dist-info-metadata and data-core-metadata attributes for a release link.
    """
    expected_metadata_sha = metadata_sha_digests.get(filename)
    expected_attr = f"sha256={expected_metadata_sha}" if expected_metadata_sha else None

    msgs = ""
    for attr_name in ["data-dist-info-metadata", "data-core-metadata"]:
        attr_value = link.get(attr_name)
        if attr_value != expected_attr:
            if expected_attr:
                msgs += (
                    f"\nFile {filename} has incorrect {attr_name}: "
                    f"expected '{expected_attr}', got '{attr_value}'"
                )
            else:
                msgs += f"\nFile {filename} should not have {attr_name} but has '{attr_value}'"
    return msgs


def _validate_requires_python(link, filename, requires_python, page_content):
    """
    Validate data-requires-python attribute for a release link.
    """
    expected_requires_python = requires_python.get(filename) if requires_python else None
    attr_value = link.get("data-requires-python")

    msgs = ""
    if attr_value != expected_requires_python:
        if expected_requires_python:
            msgs += (
                f"\nFile {filename} has incorrect data-requires-python: "
                f"expected '{expected_requires_python}', got '{attr_value}'"
            )
        else:
            msgs += f"\nFile {filename} should not have data-requires-python but has '{attr_value}'"

    # Check HTML escaping
    if expected_requires_python and any(char in expected_requires_python for char in [">", "<"]):
        escaped_value = expected_requires_python.replace(">", "&gt;").replace("<", "&lt;")
        escaped_attr = f'data-requires-python="{escaped_value}"'
        if escaped_attr not in page_content:
            msgs += f"\nFile {filename} has unescaped < or > in data-requires-python attribute"

    return msgs


def ensure_simple(
    simple_url, packages, sha_digests=None, metadata_sha_digests=None, requires_python=None
):
    """
    Tests that the simple api at `url` matches the packages supplied.
    `packages`: dictionary of form {package_name: [release_filenames]}
    First check `/simple/index.html` has each package name, no more, no less
    Second check `/simple/package_name/index.html` for each package exists
    Third check each package's index has all their releases listed, no more, no less
    Returns tuple (`proper`: bool, `error_msg`: str)
    *Technically, if there was a bug, other packages' indexes could be posted, but not present
    in the simple index and thus be accessible from the distribution, but if one can't see it
    how would one know that it's there?*
    """

    def explore_links(page_url, page_name, links_found):
        msgs = ""
        legit_found_links = []
        page_content = requests.get(page_url).text
        page = html.fromstring(page_content)
        page_links = page.xpath("/html/body/a")
        for link in page_links:
            if link.text in links_found:
                if links_found[link.text]:
                    msgs += f"\nDuplicate {page_name} name {link.text}"
                links_found[link.text] = True
                if link.get("href"):
                    legit_found_links.append(link.get("href"))
                    # Check metadata SHA digest if provided
                    if metadata_sha_digests and page_name == "release":
                        msgs += _validate_metadata_sha_digest(link, link.text, metadata_sha_digests)
                    # Check requires-python if provided
                    if requires_python and page_name == "release":
                        msgs += _validate_requires_python(
                            link, link.text, requires_python, page_content
                        )
                else:
                    msgs += f"\nFound {page_name} link without href {link.text}"
            else:
                msgs += f"\nFound extra {page_name} link {link.text}"
        return legit_found_links, msgs

    packages_found = {name: False for name in packages.keys()}
    releases_found = {name: False for releases in packages.values() for name in releases}
    found_release_links, msgs = explore_links(simple_url, "simple", packages_found)
    dl_links = []
    for rel_link in found_release_links:
        new_links, new_msgs = explore_links(
            urljoin(simple_url, rel_link), "release", releases_found
        )
        dl_links += new_links
        msgs += new_msgs
    for dl_link in dl_links:
        package_link, _, sha = dl_link.partition("#sha256=")
        if len(sha) != 64:
            msgs += f"\nRelease download link has bad sha256 {dl_link}"
        if sha_digests:
            package = package_link.split("/")[-1]
            if sha_digests[package] != sha:
                msgs += f"\nRelease has bad sha256 attached to it {package}"
    msgs += "".join(
        map(
            lambda x: f"\nSimple link not found for {x}",
            [name for name, val in packages_found.items() if not val],
        )
    )
    msgs += "".join(
        map(
            lambda x: f"\nReleases link not found for {x}",
            [name for name, val in releases_found.items() if not val],
        )
    )
    return len(msgs) == 0, msgs


def ensure_metadata(pulp_content_url, distro_base_path, filename, name, version):
    """
    Tests that metadata is accessible for a given wheel package filename.
    """
    relative_path = f"{distro_base_path}/{filename}.metadata"
    metadata_url = urljoin(pulp_content_url, relative_path)
    metadata_response = requests.get(metadata_url)
    assert metadata_response.status_code == 200
    assert len(metadata_response.content) > 0
    assert f"Name: {name}" in metadata_response.text
    assert f"Version: {version}" in metadata_response.text
