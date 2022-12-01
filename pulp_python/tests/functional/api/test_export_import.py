"""
Tests PulpExporter and PulpExport functionality.

NOTE: assumes ALLOWED_EXPORT_PATHS setting contains "/tmp" - all tests will fail if this is not
the case.
"""
import pytest
import uuid

from pulp_python.tests.functional.constants import (
    PYTHON_XS_PROJECT_SPECIFIER, PYTHON_SM_PROJECT_SPECIFIER
)


@pytest.mark.parallel
def test_export_then_import(
    python_repo_factory,
    python_remote_factory,
    python_repo_api_client,
    python_repo_version_api_client,
    exporters_pulp_api_client,
    exporters_pulp_exports_api_client,
    importers_pulp_api_client,
    importers_pulp_imports_api_client,
    monitor_task,
    monitor_task_group,
    gen_object_with_cleanup,
):
    """Issue and evaluate a PulpExport (tests both Create and Read)."""
    # Prepare content
    remote_a = python_remote_factory(includes=PYTHON_XS_PROJECT_SPECIFIER, policy="immediate")
    remote_b = python_remote_factory(includes=PYTHON_SM_PROJECT_SPECIFIER, policy="immediate")
    repo_a = python_repo_factory()
    repo_b = python_repo_factory()
    sync_response_a = python_repo_api_client.sync(
        repo_a.pulp_href, {"remote": remote_a.pulp_href}
    )
    sync_response_b = python_repo_api_client.sync(
        repo_b.pulp_href, {"remote": remote_b.pulp_href}
    )
    monitor_task(sync_response_a.task)
    monitor_task(sync_response_b.task)

    repo_ver_a = python_repo_version_api_client.read(f"{repo_a.pulp_href}versions/1/")
    repo_ver_b = python_repo_version_api_client.read(f"{repo_b.pulp_href}versions/1/")

    # Prepare export
    exporter = gen_object_with_cleanup(
        exporters_pulp_api_client,
        {
            "name": str(uuid.uuid4()),
            "path": f"/tmp/{uuid.uuid4()}/",
            "repositories": [repo.pulp_href for repo in [repo_a, repo_b]],
        },
    )

    # Export
    task = exporters_pulp_exports_api_client.create(exporter.pulp_href, {}).task
    task = monitor_task(task)
    assert len(task.created_resources) == 1
    export = exporters_pulp_exports_api_client.read(task.created_resources[0])
    assert export is not None
    assert len(exporter.repositories) == len(export.exported_resources)
    assert export.output_file_info is not None
    for an_export_filename in export.output_file_info.keys():
        assert "//" not in an_export_filename
    export_filename = next(
        f for f in export.output_file_info.keys() if f.endswith("tar.gz") or f.endswith("tar")
    )

    # Prepare import
    repo_c = python_repo_factory()
    repo_d = python_repo_factory()
    repo_mapping = {repo_a.name: repo_c.name, repo_b.name: repo_d.name}
    importer = gen_object_with_cleanup(
        importers_pulp_api_client, {"name": str(uuid.uuid4()), "repo_mapping": repo_mapping}
    )

    # Import
    import_response = importers_pulp_imports_api_client.create(
        importer.pulp_href, {"path": export_filename}
    )
    monitor_task_group(import_response.task_group)
    repo_c = python_repo_api_client.read(repo_c.pulp_href)
    repo_d = python_repo_api_client.read(repo_d.pulp_href)
    assert repo_c.latest_version_href == f"{repo_c.pulp_href}versions/1/"
    assert repo_d.latest_version_href == f"{repo_d.pulp_href}versions/1/"
    repo_ver_c = python_repo_version_api_client.read(f"{repo_c.pulp_href}versions/1/")
    repo_ver_d = python_repo_version_api_client.read(f"{repo_d.pulp_href}versions/1/")
    assert (
        repo_ver_c.content_summary.added["python.python"]["count"]
        == repo_ver_a.content_summary.present["python.python"]["count"]
    )
    assert (
        repo_ver_d.content_summary.added["python.python"]["count"]
        == repo_ver_b.content_summary.present["python.python"]["count"]
    )

    # Import a second time
    import_response = importers_pulp_imports_api_client.create(
        importer.pulp_href, {"path": export_filename}
    )
    monitor_task_group(import_response.task_group)
    assert len(importers_pulp_imports_api_client.list(importer.pulp_href).results) == 2
    for repo in [repo_c, repo_d]:
        repo = python_repo_api_client.read(repo.pulp_href)
        # still only one version as pulp won't create a new version if nothing changed
        assert repo.latest_version_href == f"{repo.pulp_href}versions/1/"
