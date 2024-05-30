import subprocess

from urllib.parse import urlsplit


def test_pip_consume_content(
    python_repo,
    python_content_factory,
    python_publication_factory,
    python_distribution_factory,
    shelf_reader_cleanup,
    delete_orphans_pre,
):
    """Verify whether content served by Pulp can be consumed through pip install."""
    python_content_factory(repository=python_repo)
    pub = python_publication_factory(repository=python_repo)
    distro = python_distribution_factory(publication=pub)

    cmd = [
        "pip",
        "install",
        "--no-deps",
        "--no-cache-dir",
        "--force-reinstall",
        "--trusted-host",
        urlsplit(distro.base_url).hostname,
        "-i",
        distro.base_url + "simple/",
        "shelf-reader",
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    stdout = subprocess.run(("pip", "list"), capture_output=True).stdout.decode("utf-8")
    assert stdout.find("shelf-reader") != -1
