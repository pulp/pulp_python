import pytest


@pytest.mark.parallel
def test_autopublish_sync(
    python_bindings, python_repo_factory, python_remote_factory, monitor_task
):
    """Assert that syncing the repository triggers auto-publish."""
    remote = python_remote_factory()
    repo = python_repo_factory(remote=remote, autopublish=True)

    # Sync repository
    task = monitor_task(python_bindings.RepositoriesPythonApi.sync(repo.pulp_href, {}).task)
    assert len(task.created_resources) == 2
    results = python_bindings.PublicationsPypiApi.list(repository=repo.pulp_href)
    assert results.count == 1
    assert results.results[0].pulp_href in task.created_resources

    # Sync the repository again. Since there should be no new repository version, there
    # should be no new publications
    task = monitor_task(python_bindings.RepositoriesPythonApi.sync(repo.pulp_href, {}).task)
    assert len(task.created_resources) == 0
    results = python_bindings.PublicationsPypiApi.list(repository=repo.pulp_href)
    assert results.count == 1


@pytest.mark.parallel
def test_autopublish_modify(
    python_bindings, python_repo_factory, python_content_factory, monitor_task
):
    """Assert that modifying the repository triggers auto-publish."""
    repo = python_repo_factory(autopublish=True)
    content = python_content_factory()

    # Modify the repository by adding a content unit
    body = {"add_content_units": [content.pulp_href]}
    task = monitor_task(python_bindings.RepositoriesPythonApi.modify(repo.pulp_href, body).task)
    assert len(task.created_resources) == 2
    results = python_bindings.PublicationsPypiApi.list(repository=repo.pulp_href)
    assert results.count == 1
    assert results.results[0].pulp_href in task.created_resources
