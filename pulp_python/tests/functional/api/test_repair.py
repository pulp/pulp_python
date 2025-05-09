import pytest
import subprocess
from urllib.parse import urljoin

from pulp_python.tests.functional.constants import (
    PYTHON_EGG_FILENAME,
    PYTHON_FIXTURES_URL,
)


@pytest.fixture
def create_content_direct(python_bindings):
    def _create(artifact_filename, filename, content_data):
        commands = (
            "from pulpcore.plugin.models import Artifact, ContentArtifact; "
            "from pulpcore.plugin.util import get_url; "
            "from pulp_python.app.models import PythonPackageContent; "
            f"a = Artifact.init_and_validate('{artifact_filename}'); "
            "a.save(); "
            f"c = PythonPackageContent(sha256=a.sha256, filename={filename!r}, **{content_data!r}); "  # noqa: E501
            "c.save(); "
            f"ca = ContentArtifact(artifact=a, content=c, relative_path={filename!r}); "
            "ca.save(); "
            "print(get_url(c))"
        )
        process = subprocess.run(["pulpcore-manager", "shell", "-c", commands], capture_output=True)

        assert process.returncode == 0
        content_href = process.stdout.decode().strip()
        return python_bindings.ContentPackagesApi.read(content_href)

    return _create


@pytest.fixture
def move_to_repository(python_bindings, monitor_task):
    def _move(repo_href, content_hrefs):
        body = {"add_content_units": content_hrefs}
        task = monitor_task(python_bindings.RepositoriesPythonApi.modify(repo_href, body).task)
        assert len(task.created_resources) == 1
        return python_bindings.RepositoriesPythonApi.read(repo_href)

    return _move


def test_metadata_repair_command(
    create_content_direct,
    python_file,
    python_repo,
    move_to_repository,
    python_bindings,
    delete_orphans_pre,
):
    """Test pulpcore-manager repair-python-metadata command."""
    data = {
        "name": "shelf-reader",
        # Wrong metadata
        "version": "0.2",
        "packagetype": "bdist",
        "requires_python": ">=3.8",
        "author": "ME",
    }
    content = create_content_direct(python_file, PYTHON_EGG_FILENAME, data)
    for field, wrong_value in data.items():
        if field == "python_version":
            continue
        assert getattr(content, field) == wrong_value

    move_to_repository(python_repo.pulp_href, [content.pulp_href])
    process = subprocess.run(
        ["pulpcore-manager", "repair-python-metadata", "--repositories", python_repo.pulp_href],
        capture_output=True
    )
    assert process.returncode == 0
    output = process.stdout.decode().strip()
    assert output == "1 packages processed, 1 package metadata repaired."

    content = python_bindings.ContentPackagesApi.read(content.pulp_href)
    assert content.version == "0.1"
    assert content.packagetype == "sdist"
    assert content.requires_python == ""  # technically null
    assert content.author == "Austin Macdonald"


def test_metadata_repair_endpoint(
    create_content_direct,
    download_python_file,
    monitor_task,
    move_to_repository,
    python_bindings,
    python_repo,
):
    """
    Test repairing of package metadata via `Repositories.repair_metadata` endpoint.
    """
    python_egg_filename = "scipy-1.1.0.tar.gz"
    python_egg_url = urljoin(
        urljoin(PYTHON_FIXTURES_URL, "packages/"), python_egg_filename
    )
    python_file = download_python_file(python_egg_filename, python_egg_url)

    data = {
        "name": "scipy",
        # Wrong metadata
        "author": "ME",
        "packagetype": "bdist",
        "requires_python": ">=3.8",
        "version": "0.2",
    }
    content = create_content_direct(python_file, python_egg_filename, data)
    for field, wrong_value in data.items():
        if field == "python_version":
            continue
        assert getattr(content, field) == wrong_value
    move_to_repository(python_repo.pulp_href, [content.pulp_href])

    response = python_bindings.RepositoriesPythonApi.repair_metadata(
        python_repo.pulp_href
    )
    monitor_task(response.task)

    content = python_bindings.ContentPackagesApi.read(content.pulp_href)
    assert content.version == "1.1.0"
    assert content.packagetype == "sdist"
    assert content.requires_python == ">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*"
    assert content.author == ""
