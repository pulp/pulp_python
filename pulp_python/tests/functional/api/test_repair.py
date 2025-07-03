import pytest
import subprocess
from urllib.parse import urljoin

from pulp_python.tests.functional.constants import (
    PYTHON_EGG_FILENAME,
    PYTHON_FIXTURES_URL,
)


@pytest.fixture
def create_content_direct(python_bindings):
    def _create(artifact_filename, content_data):
        commands = (
            "from pulpcore.plugin.models import Artifact, ContentArtifact; "
            "from pulpcore.plugin.util import get_url; "
            "from pulp_python.app.models import PythonPackageContent; "
            f"a = Artifact.init_and_validate('{artifact_filename}'); "
            "a.save(); "
            f"c = PythonPackageContent(sha256=a.sha256, **{content_data!r}); "
            "c.save(); "
            f"ca = ContentArtifact(artifact=a, content=c, relative_path=c.filename); "
            "ca.save(); "
            "print(get_url(c))"
        )
        process = subprocess.run(["pulpcore-manager", "shell", "-c", commands], capture_output=True)

        assert process.returncode == 0
        content_href = process.stdout.decode().strip()
        return python_bindings.ContentPackagesApi.read(content_href)

    return _create


@pytest.fixture
def create_content_remote(python_bindings):
    def _create(content, remote, remote_2=None):
        commands = (
            "from pulpcore.plugin.models import ContentArtifact, RemoteArtifact; "
            "from pulpcore.plugin.util import extract_pk, get_url; "
            "from pulp_python.app.models import PythonPackageContent, PythonRemote; "
            f"c = PythonPackageContent(**{content!r}); "
            "c.save(); "
            f"ca = ContentArtifact(content=c, relative_path=c.filename); "
            "ca.save(); "
            f"r = PythonRemote.objects.get(pk=extract_pk({remote.pulp_href!r})); "
            f"ra = RemoteArtifact(content_artifact=ca, remote=r, sha256=c.sha256); "
            "ra.save(); "
        )
        if remote_2:
            commands += (
                f"r2 = PythonRemote.objects.get(pk=extract_pk({remote_2.pulp_href!r})); "
                f"ra2 = RemoteArtifact(content_artifact=ca, remote=r2, sha256=c.sha256); "
                "ra2.save(); "
            )
        commands += "print(get_url(c))"
        process = subprocess.run(
            ["pulpcore-manager", "shell", "-c", commands], capture_output=True
        )

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
        "filename": PYTHON_EGG_FILENAME,
        # Wrong metadata
        "version": "0.2",
        "packagetype": "bdist",
        "requires_python": ">=3.8",
        "author": "ME",
    }
    content = create_content_direct(python_file, data)
    for field, wrong_value in data.items():
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
    create_content_remote,
    delete_orphans_pre,
    download_python_file,
    monitor_task,
    move_to_repository,
    python_bindings,
    python_remote_factory,
    python_repo_factory,
):
    """
    Test repairing of package metadata via `Repositories.repair_metadata` endpoint.
    """
    # 1. Setup tested data
    # Shared data
    python_remote = python_remote_factory()
    python_remote_bad = python_remote_factory(url="https://fixtures.pulpproject.org/")
    python_repo = python_repo_factory(remote=python_remote)

    # Immediate content
    scipy_egg_filename = "scipy-1.1.0-cp27-none-win32.whl"
    scipy_egg_url = urljoin(
        urljoin(PYTHON_FIXTURES_URL, "packages/"), scipy_egg_filename
    )
    scipy_file = download_python_file(scipy_egg_filename, scipy_egg_url)
    scipy_data_0 = {
        "filename": scipy_egg_filename,
        "name": "scipy",
        "version": "1.1.0",
        # Wrong metadata
        "author": "ME",
        "packagetype": "bdist",
        "requires_python": ">=3.8",
    }

    # On-demand content
    celery_data = {
        "filename": "celery-2.4.1.tar.gz",
        "name": "celery",
        "version": "2.4.1",
        "sha256": "c77652ca179d14473975822dbfb1b5dab950c88c171ef6bc2257ddb9066e6790",
        # Wrong metadata
        "author": "ME",
        "packagetype": "bdist",
        "requires_python": ">=3.8",
    }

    scipy_data_1 = {
        "filename": "scipy-1.1.0.tar.gz",
        "name": "scipy",
        "version": "1.1.0",
        "sha256": "878352408424dffaa695ffedf2f9f92844e116686923ed9aa8626fc30d32cfd1",
        # Wrong metadata
        "author": "ME",
        "packagetype": "bdist",
        "requires_python": ">=3.8",
    }

    scipy_data_2 = scipy_data_1.copy()
    scipy_data_2["filename"] = "scipy-1.1.0-cp36-none-win32.whl"
    scipy_data_2["sha256"] = (
        "0e9bb7efe5f051ea7212555b290e784b82f21ffd0f655405ac4f87e288b730b3"
    )

    # 2. Create content
    celery_content = create_content_remote(celery_data, python_remote)
    scipy_content_0 = create_content_direct(scipy_file, scipy_data_0)
    scipy_content_1 = create_content_remote(
        scipy_data_1, python_remote, python_remote_bad
    )
    scipy_content_2 = create_content_remote(scipy_data_2, python_remote_bad)

    content_hrefs = {}
    for data, content in [
        (celery_data, celery_content),
        (scipy_data_0, scipy_content_0),
        (scipy_data_1, scipy_content_1),
        (scipy_data_2, scipy_content_2),
    ]:
        for field, test_value in data.items():
            assert getattr(content, field) == test_value
        content_hrefs[data["filename"]] = content.pulp_href
    move_to_repository(python_repo.pulp_href, list(content_hrefs.values()))

    # 3. Repair metadata
    response = python_bindings.RepositoriesPythonApi.repair_metadata(
        python_repo.pulp_href
    )
    monitor_task(response.task)

    # 4. Check new metadata
    new_metadata = [
        # repaired
        ("celery-2.4.1.tar.gz", "Ask Solem", "sdist", ""),
        (
            "scipy-1.1.0-cp27-none-win32.whl",
            "",
            "bdist_wheel",
            ">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*",
        ),
        ("scipy-1.1.0.tar.gz", "", "sdist", ">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*"),
        # not repaired
        ("scipy-1.1.0-cp36-none-win32.whl", "ME", "bdist", ">=3.8"),
    ]
    for filename, author, packagetype, requires_python in new_metadata:
        new_content = python_bindings.ContentPackagesApi.read(content_hrefs[filename])
        assert new_content.author == author
        assert new_content.packagetype == packagetype
        assert new_content.requires_python == requires_python
