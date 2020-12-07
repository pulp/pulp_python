# coding=utf-8
"""Tests that CRUD python remotes."""
from random import choice
import unittest

from pulp_smash import utils

from pulp_smash.pulp3.bindings import monitor_task
from pulp_smash.pulp3.constants import ON_DEMAND_DOWNLOAD_POLICIES

from pulp_python.tests.functional.utils import (
    gen_python_client,
    gen_python_remote,
    skip_if,
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401

from pulpcore.client.pulp_python import RemotesPythonApi
from pulpcore.client.pulp_python.exceptions import ApiException

from pulp_python.tests.functional.constants import (
    BANDERSNATCH_CONF,
    DEFAULT_BANDER_REMOTE_BODY,
    PYTHON_INVALID_SPECIFIER_NO_NAME,
    PYTHON_INVALID_SPECIFIER_BAD_VERSION,
    PYTHON_VALID_SPECIFIER_NO_VERSION,
)
from tempfile import NamedTemporaryFile


class CRUDRemotesTestCase(unittest.TestCase):
    """CRUD remotes."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.remote_api = RemotesPythonApi(gen_python_client())

    def test_01_create_remote(self):
        """Create a remote."""
        body = _gen_verbose_remote()
        type(self).remote = self.remote_api.create(body)
        for key in ("username", "password"):
            del body[key]
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote.to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_02_create_same_name(self):
        """Try to create a second remote with an identical name.

        See: `Pulp Smash #1055
        <https://github.com/pulp/pulp-smash/issues/1055>`_.
        """
        body = gen_python_remote()
        body["name"] = self.remote.name
        with self.assertRaises(ApiException):
            self.remote_api.create(body)

    @skip_if(bool, "remote", False)
    def test_02_read_remote(self):
        """Read a remote by its href."""
        remote = self.remote_api.read(self.remote.pulp_href)
        for key, val in self.remote.to_dict().items():
            with self.subTest(key=key):
                self.assertEqual(remote.to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_02_read_remotes(self):
        """Read a remote by its name."""
        page = self.remote_api.list(name=self.remote.name)
        self.assertEqual(len(page.results), 1)
        for key, val in self.remote.to_dict().items():
            with self.subTest(key=key):
                self.assertEqual(page.results[0].to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_03_partially_update(self):
        """Update a remote using HTTP PATCH."""
        body = _gen_verbose_remote()
        response = self.remote_api.partial_update(self.remote.pulp_href, body)
        monitor_task(response.task)
        for key in ("username", "password"):
            del body[key]
        type(self).remote = self.remote_api.read(self.remote.pulp_href)
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote.to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_04_fully_update(self):
        """Update a remote using HTTP PUT."""
        body = _gen_verbose_remote()
        response = self.remote_api.update(self.remote.pulp_href, body)
        monitor_task(response.task)
        for key in ("username", "password"):
            del body[key]
        type(self).remote = self.remote_api.read(self.remote.pulp_href)
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote.to_dict()[key], val, key)

    @skip_if(bool, "remote", False)
    def test_05_delete(self):
        """Delete a remote."""
        response = self.remote_api.delete(self.remote.pulp_href)
        monitor_task(response.task)
        with self.assertRaises(ApiException):
            self.remote_api.read(self.remote.pulp_href)


class CreateRemoteFromBandersnatchConfig(unittest.TestCase):
    """
    Verify whether it's possible to create a remote from a Bandersnatch config

    This test targets the following issues:

    * `Pulp #6929 <https://pulp.plan.io/issues/6929>`_
    * `Pulp #7331 <https://pulp.plan.io/issues/7331>`_
    """

    def test_01_creation(self):
        """Create a remote from Bandersnatch config."""
        remote_api = RemotesPythonApi(gen_python_client())
        with NamedTemporaryFile() as config:
            config.write(BANDERSNATCH_CONF)
            config.seek(0)
            name = utils.uuid4()
            remote = remote_api.from_bandersnatch(config.name, name)
            self.addCleanup(remote_api.delete, remote.pulp_href)
            expected = _gen_expected_remote_body(name)
            for key, val in expected.items():
                with self.subTest(key=key):
                    self.assertEqual(remote.to_dict()[key], val, key)

    def test_02_ondemand(self):
        """Create a remote from Bandersnatch config w/ policy remote"""
        remote_api = RemotesPythonApi(gen_python_client())
        with NamedTemporaryFile() as config:
            config.write(BANDERSNATCH_CONF)
            config.seek(0)
            name = utils.uuid4()
            policy = "on_demand"
            remote = remote_api.from_bandersnatch(config.name, name, policy=policy)
            self.addCleanup(remote_api.delete, remote.pulp_href)
            expected = _gen_expected_remote_body(name, policy=policy)
            for key, val in expected.items():
                with self.subTest(key=key):
                    self.assertEqual(remote.to_dict()[key], val, key)


class CreateRemoteNoURLTestCase(unittest.TestCase):
    """Verify whether is possible to create a remote without a URL."""

    def test_all(self):
        """Verify whether is possible to create a remote without a URL.

        This test targets the following issues:

        * `Pulp #3395 <https://pulp.plan.io/issues/3395>`_
        * `Pulp Smash #984 <https://github.com/pulp/pulp-smash/issues/984>`_
        """
        body = gen_python_remote()
        del body["url"]
        with self.assertRaises(ApiException):
            RemotesPythonApi(gen_python_client()).create(body)


class RemoteDownloadPolicyTestCase(unittest.TestCase):
    """Verify download policy behavior for valid and invalid values.

    In Pulp 3, there are are different download policies.

    This test targets the following testing scenarios:

    1. Creating a remote without a download policy.
       Verify the creation is successful and immediate it is policy applied.
    2. Change the remote policy from default.
       Verify the change is successful.
    3. Attempt to change the remote policy to an invalid string.
       Verify an ApiException is given for the invalid policy as well
       as the policy remaining unchanged.

    For more information on the remote policies, see the Pulp3
    API on an installed server:

    * /pulp/api/v3/docs/#operation`

    This test targets the following issues:

    * `Pulp #4420 <https://pulp.plan.io/issues/4420>`_
    * `Pulp #3763 <https://pulp.plan.io/issues/3763>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.remote_api = RemotesPythonApi(gen_python_client())
        cls.remote = {}
        cls.policies = ON_DEMAND_DOWNLOAD_POLICIES
        cls.body = _gen_verbose_remote()

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        results = cls.remote_api.list().to_dict()["results"]
        for result in results:
            cls.remote_api.delete(result["pulp_href"])

    def test_01_no_defined_policy(self):
        """Verify the default policy `on_demand`.

        When no policy is defined, the default policy of `on_demand`
        is applied.
        """
        del self.body["policy"]
        self.remote.update(self.remote_api.create(self.body).to_dict())
        self.assertEqual(self.remote["policy"], "on_demand", self.remote)

    @skip_if(len, "policies", 1)
    def test_02_change_policy(self):
        """Verify ability to change policy to value other than the default.

        Update the remote policy to a valid value other than `on_demand`
        and verify the new set value.
        """
        changed_policy = choice([item for item in self.policies if item != "on_demand"])
        response = self.remote_api.partial_update(
            self.remote["pulp_href"], {"policy": changed_policy}
        )
        monitor_task(response.task)
        self.remote.update(self.remote_api.read(self.remote["pulp_href"]).to_dict())
        self.assertEqual(self.remote["policy"], changed_policy, self.remote)

    @skip_if(bool, "remote", False)
    def test_03_invalid_policy(self):
        """Verify an invalid policy does not update the remote policy.

        Get the current remote policy.
        Attempt to update the remote policy to an invalid value.
        Verify the policy remains the same.
        """
        remote = self.remote_api.read(self.remote["pulp_href"]).to_dict()
        with self.assertRaises(ApiException):
            self.remote_api.partial_update(
                self.remote["pulp_href"], {"policy": utils.uuid4()}
            )
        self.remote.update(self.remote_api.read(self.remote["pulp_href"]).to_dict())
        self.assertEqual(remote["policy"], self.remote["policy"], self.remote)


class CreateRemoteWithInvalidProjectSpecifiersTestCase(unittest.TestCase):
    """
    Test that creating a remote with an invalid project specifier fails.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.remote_api = RemotesPythonApi(gen_python_client())

    def test_includes_with_no_name(self):
        """
        Test an include specifier without a "name" field.
        """
        body = gen_python_remote(includes=PYTHON_INVALID_SPECIFIER_NO_NAME)
        with self.assertRaises(ApiException):
            self.remote_api.create(body)

    def test_includes_with_bad_version(self):
        """
        Test an include specifier with an invalid "version_specifier" field value.
        """
        body = gen_python_remote(includes=PYTHON_INVALID_SPECIFIER_BAD_VERSION)
        with self.assertRaises(ApiException):
            self.remote_api.create(body)

    def test_excludes_with_no_name(self):
        """
        Test an exclude specifier without a "name" field.
        """
        body = gen_python_remote(excludes=PYTHON_INVALID_SPECIFIER_NO_NAME)
        with self.assertRaises(ApiException):
            self.remote_api.create(body)

    def test_excludes_with_bad_version(self):
        """
        Test an exclude specifier with an invalid "version_specifier" field value.
        """
        body = gen_python_remote(excludes=PYTHON_INVALID_SPECIFIER_BAD_VERSION)
        with self.assertRaises(ApiException):
            self.remote_api.create(body)


class CreateRemoteWithNoVersionTestCase(unittest.TestCase):
    """
    Test that creating a remote with no "version_specifier" on the project specifier works.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.remote_api = RemotesPythonApi(gen_python_client())

    def test_includes_with_no_version(self):
        """
        Test an include specifier without a "version_specifier" field.
        """
        body = gen_python_remote(includes=PYTHON_VALID_SPECIFIER_NO_VERSION)
        remote = self.remote_api.create(body).to_dict()
        self.addCleanup(self.remote_api.delete, remote["pulp_href"])

        self.assertEqual(remote["includes"][0], PYTHON_VALID_SPECIFIER_NO_VERSION[0])

    def test_excludes_with_no_version(self):
        """
        Test an exclude specifier without a "version_specifier" field.
        """
        body = gen_python_remote(excludes=PYTHON_VALID_SPECIFIER_NO_VERSION)
        remote = self.remote_api.create(body).to_dict()
        self.addCleanup(self.remote_api.delete, remote["pulp_href"])

        self.assertEqual(remote["includes"][0], PYTHON_VALID_SPECIFIER_NO_VERSION[0])
        self.assertEqual(remote["excludes"][0], PYTHON_VALID_SPECIFIER_NO_VERSION[0])


class UpdateRemoteWithInvalidProjectSpecifiersTestCase(unittest.TestCase):
    """
    Test that updating a remote with an invalid project specifier fails non-destructively.
    """

    @classmethod
    def setUpClass(cls):
        """
        Create class-wide variables.
        """
        cls.remote_api = RemotesPythonApi(gen_python_client())
        cls.remote = cls.remote_api.create(gen_python_remote())
        cls._original_remote = cls.remote

    @classmethod
    def tearDownClass(cls):
        """
        Clean class-wide variable.
        """
        cls.remote_api.delete(cls.remote.pulp_href)

    def test_includes_with_no_name(self):
        """
        Test an include specifier without a "name" field.
        """
        body = {"includes": PYTHON_INVALID_SPECIFIER_NO_NAME}
        with self.assertRaises(ApiException):
            self.remote_api.partial_update(self.remote.pulp_href, body)

    def test_includes_with_bad_version(self):
        """
        Test an include specifier with an invalid "version_specifier" field value.
        """
        body = {"includes": PYTHON_INVALID_SPECIFIER_BAD_VERSION}
        with self.assertRaises(ApiException):
            self.remote_api.partial_update(self.remote.pulp_href, body)

    def test_excludes_with_no_name(self):
        """
        Test an exclude specifier without a "name" field.
        """
        body = {"excludes": PYTHON_INVALID_SPECIFIER_NO_NAME}
        with self.assertRaises(ApiException):
            self.remote_api.partial_update(self.remote.pulp_href, body)

    def test_excludes_with_bad_version(self):
        """
        Test an exclude specifier with an invalid "version_specifier" field value.
        """
        body = {"excludes": PYTHON_INVALID_SPECIFIER_BAD_VERSION}
        with self.assertRaises(ApiException):
            self.remote_api.partial_update(self.remote.pulp_href, body)


def _gen_verbose_remote():
    """Return a semi-random dict for use in defining a remote.

    For most tests, it"s desirable to create remotes with as few attributes
    as possible, so that the tests can specifically target and attempt to break
    specific features. This module specifically targets remotes, so it makes
    sense to provide as many attributes as possible.

    Note that 'username' and 'password' are write-only attributes.
    """
    attrs = gen_python_remote()
    attrs.update(
        {
            "password": utils.uuid4(),
            "username": utils.uuid4(),
            "policy": choice(ON_DEMAND_DOWNLOAD_POLICIES),
        }
    )
    return attrs


def _gen_expected_remote_body(name, **kwargs):
    """Generates a remote body based on names and dictionary in kwargs"""
    # The defaults found in bandersnatch_conf
    body = DEFAULT_BANDER_REMOTE_BODY
    body["name"] = name
    # overwrite the defaults if specified in kwargs
    body.update(kwargs)
    return body
