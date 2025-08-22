import pytest
from pulp_python.tests.functional.constants import (
    PYTHON_EGG_FILENAME,
    PYTHON_EGG_URL,
    PYTHON_WHEEL_FILENAME,
    PYTHON_WHEEL_URL,
)


@pytest.mark.parametrize(
    "pkg_filename, pkg_url",
    [(PYTHON_WHEEL_FILENAME, PYTHON_WHEEL_URL), (PYTHON_EGG_FILENAME, PYTHON_EGG_URL)],
)
def test_synchronous_package_upload(
    delete_orphans_pre, download_python_file, gen_user, python_bindings, pkg_filename, pkg_url
):
    """
    Test synchronously uploading a Python package with labels.
    """
    python_file = download_python_file(pkg_filename, pkg_url)

    # Upload a unit with labels
    with gen_user(model_roles=["python.python_package_uploader"]):
        labels = {"key_1": "value_1"}
        content_body = {"file": python_file, "pulp_labels": labels}
        package = python_bindings.ContentPackagesApi.upload(**content_body)
        assert package.pulp_labels == labels
        assert package.name == "shelf-reader"
        assert package.filename == pkg_filename

    # Check that uploading the same unit again with different (or same) labels has no effect
    with gen_user(model_roles=["python.python_package_uploader"]):
        labels_2 = {"key_2": "value_2"}
        content_body_2 = {"file": python_file, "pulp_labels": labels_2}
        duplicate_package = python_bindings.ContentPackagesApi.upload(**content_body_2)
        assert duplicate_package.pulp_href == package.pulp_href
        assert duplicate_package.pulp_labels == package.pulp_labels
        assert duplicate_package.pulp_labels != labels_2

    # Check that the upload fails if the user does not have the required permissions
    with gen_user(model_roles=[]):
        with pytest.raises(python_bindings.ApiException) as ctx:
            python_bindings.ContentPackagesApi.upload(**content_body)
        assert ctx.value.status == 403
