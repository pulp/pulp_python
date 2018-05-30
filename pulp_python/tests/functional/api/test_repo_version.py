import time
import unittest
from unittest import skip
from random import choice, randint, sample

from requests.exceptions import HTTPError

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp3.constants import REPO_PATH
from pulp_smash.tests.pulp3.utils import (gen_repo, get_auth, get_artifact_paths, get_content,
                                          get_added_content, get_removed_content, get_versions,
                                          sync, publish, delete_version)

from pulp_python.tests.functional.constants import (PYTHON_CONTENT_PATH, PYTHON_PYPI_URL,
                                                    PYTHON_REMOTE_PATH, PYTHON_PUBLISHER_PATH,
                                                    PYTHON_PACKAGE_COUNT)
from pulp_python.tests.functional.utils import gen_remote, gen_publisher, populate_pulp
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:E722


class AddRemoveContentTestCase(unittest.TestCase, utils.SmokeTest):
    """Add and remove content to a repository. Verify side-effects.

    A new repository version is automatically created each time content is
    added to or removed from a repository. Furthermore, it's possible to
    inspect any repository version and discover which content is present, which
    content was removed, and which content was added. This test case explores
    these features.

    This test targets the following issues:

    * `Pulp #3059 <https://pulp.plan.io/issues/3059>`_
    * `Pulp #3234 <https://pulp.plan.io/issues/3234>`_
    * `Pulp Smash #878 <https://github.com/PulpQE/pulp-smash/issues/878>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables."""
        cls.cfg = config.get_config()
        if not selectors.bug_is_fixed(3502, cls.cfg.pulp_version):
            raise unittest.SkipTest('https://pulp.plan.io/issues/3502')
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        cls.remote = {}
        cls.repo = {}
        cls.content = {}

    @classmethod
    def tearDownClass(cls):
        """Destroy resources created by test methods."""
        if cls.remote:
            cls.client.delete(cls.remote['_href'])
        if cls.repo:
            cls.client.delete(cls.repo['_href'])

    def test_01_create_repository(self):
        """Create a repository.

        Assert that:

        * The ``_versions_href`` API call is correct.
        * The ``_latest_version_href`` API call is correct.
        """
        self.repo.update(self.client.post(REPO_PATH, gen_repo()))

        repo_versions = self.client.get(self.repo['_versions_href'])
        self.assertEqual(len(repo_versions['results']), 0)

        self.assertIsNone(self.repo['_latest_version_href'])

    @selectors.skip_if(bool, 'repo', False)
    def test_02_sync_content(self):
        """Sync content into the repository.

        Assert that:

        * The ``_versions_href`` API call is correct.
        * The ``_latest_version_href`` API call is correct.
        * The ``_latest_version_href + content/`` API call is correct.
        * The ``_latest_version_href + added_content/`` API call is correct.
        * The ``_latest_version_href + removed_content/`` API call is correct.
        * The ``content_summary`` attribute is correct.
        """
        body = gen_remote(PYTHON_PYPI_URL)
        self.remote.update(self.client.post(PYTHON_REMOTE_PATH, body))
        sync(self.cfg, self.remote, self.repo)
        repo = self.client.get(self.repo['_href'])

        repo_versions = self.client.get(repo['_versions_href'])
        self.assertEqual(len(repo_versions['results']), 1)

        self.assertIsNotNone(repo['_latest_version_href'])

        content = get_content(repo)
        self.assertEqual(len(content['results']), PYTHON_PACKAGE_COUNT)

        added_content = get_added_content(repo)
        self.assertEqual(len(added_content['results']), PYTHON_PACKAGE_COUNT, added_content)

        removed_content = get_removed_content(repo)
        self.assertEqual(len(removed_content['results']), 0, removed_content)

        content_summary = self.get_content_summary(repo)
        self.assertEqual(content_summary, {'python': PYTHON_PACKAGE_COUNT})

    @skip("unknown reason for failure")
    @selectors.skip_if(bool, 'repo', False)
    def test_03_remove_content(self):
        """Remove content from the repository.

        Make roughly the same assertions as :meth:`test_02_sync_content`.
        """
        repo = self.client.get(self.repo['_href'])
        self.content.update(choice(get_content(repo)['results']))
        self.client.post(
            repo['_versions_href'],
            {'remove_content_units': [self.content['_href']]}
        )
        repo = self.client.get(self.repo['_href'])

        repo_versions = self.client.get(repo['_versions_href'])
        self.assertEqual(len(repo_versions['results']), 1)

        self.assertIsNotNone(repo['_latest_version_href'])

        content = get_content(repo)
        self.assertEqual(len(content['results']), PYTHON_PACKAGE_COUNT - 1)

        added_content = get_added_content(repo)
        self.assertEqual(len(added_content['results']), 0, added_content)

        removed_content = get_removed_content(repo)
        self.assertEqual(len(removed_content['results']), 1, removed_content)

        content_summary = self.get_content_summary(repo)
        self.assertEqual(content_summary, {'python': PYTHON_PACKAGE_COUNT - 1})

    @skip("unknown reason for failure")
    @selectors.skip_if(bool, 'repo', False)
    def test_04_add_content(self):
        """Add content to the repository.

        Make roughly the same assertions as :meth:`test_02_sync_content`.
        """
        repo = self.client.get(self.repo['_href'])
        self.client.post(
            repo['_versions_href'],
            {'add_content_units': [self.content['_href']]}
        )
        repo = self.client.get(self.repo['_href'])

        repo_versions = self.client.get(repo['_versions_href'])
        self.assertEqual(len(repo_versions['results']), PYTHON_PACKAGE_COUNT)

        self.assertIsNotNone(repo['_latest_version_href'])

        content = get_content(repo)
        self.assertEqual(len(content['results']), PYTHON_PACKAGE_COUNT)

        added_content = get_added_content(repo)
        self.assertEqual(len(added_content['results']), 1, added_content)

        removed_content = get_removed_content(repo)
        self.assertEqual(len(removed_content['results']), 0, removed_content)

        content_summary = self.get_content_summary(repo)
        self.assertEqual(content_summary, {'python': PYTHON_PACKAGE_COUNT})

    def get_content_summary(self, repo):
        """Get the ``content_summary`` for the given repository."""
        repo_versions = self.client.get(repo['_versions_href'])
        content_summaries = [
            repo_version['content_summary']
            for repo_version in repo_versions['results']
            if repo_version['_href'] == repo['_latest_version_href']
        ]
        self.assertEqual(len(content_summaries), 1, content_summaries)
        return content_summaries[0]


@skip("needs better fixtures")
class AddRemoveRepoVersionTestCase(unittest.TestCase, utils.SmokeTest):
    """Create and delete repository versions.

    This test targets the following issues:

    * `Pulp #3219 <https://pulp.plan.io/issues/3219>`_
    * `Pulp Smash #871 <https://github.com/PulpQE/pulp-smash/issues/871>`_
    """

    @classmethod
    def setUpClass(cls):
        """Add content to Pulp."""
        populate_pulp(cls.cfg, PYTHON_PYPI_URL)

        # We need at least three content units. Choosing a relatively low
        # number is useful, to limit how many repo versions are created, and
        # thus how long the test takes.
        cls.content = sample(cls.client.get(PYTHON_CONTENT_PATH)['results'], 10)

    def setUp(self):
        """Create a repository and give it nine new versions."""
        self.repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, self.repo['_href'])

        # Don't upload the last content unit. The test case might upload it to
        # create a new repo version within the test.
        for content in self.content[:-1]:
            self.client.post(
                self.repo['_versions_href'],
                {'add_content_units': [content['_href']]}
            )
        self.repo = self.client.get(self.repo['_href'])
        self.repo_versions = get_versions(self.repo)

    def test_delete_first_version(self):
        """Delete the first repository version."""
        delete_version(self.repo, self.repo_versions[0])
        with self.assertRaises(HTTPError):
            get_content(self.repo, self.repo_versions[0])
        for repo_version in self.repo_versions[1:]:
            artifact_paths = get_artifact_paths(self.repo, repo_version)
            self.assertIn(self.content[0]['artifact'], artifact_paths)

    def test_delete_last_version(self):
        """Delete the last repository version.

        Create a new repository version from the second-to-last repository
        version. Verify that the content unit from the old last repository
        version is not in the new last repository version.
        """
        # Delete the last repo version.
        delete_version(self.repo, self.repo_versions[-1])
        with self.assertRaises(HTTPError):
            get_content(self.repo, self.repo_versions[-1])

        # Make new repo version from new last repo version.
        self.client.post(
            self.repo['_versions_href'],
            {'add_content_units': [self.content[-1]['_href']]}
        )
        self.repo = self.client.get(self.repo['_href'])
        artifact_paths = get_artifact_paths(self.repo)
        self.assertNotIn(self.content[-2]['artifact'], artifact_paths)
        self.assertIn(self.content[-1]['artifact'], artifact_paths)

    def test_delete_middle_version(self):
        """Delete a middle version."""
        index = randint(1, len(self.repo_versions) - 2)
        delete_version(self.repo, self.repo_versions[index])
        with self.assertRaises(HTTPError):
            get_content(self.repo, self.repo_versions[index])
        for repo_version in self.repo_versions[index + 1:]:
            artifact_paths = get_artifact_paths(self.repo, repo_version)
            self.assertIn(self.content[index]['artifact'], artifact_paths)

    def test_delete_publication(self):
        """Delete a publication.

        Delete a repository version, and verify the associated publication is
        also deleted.
        """
        publisher = self.client.post(PYTHON_PUBLISHER_PATH, gen_publisher())
        self.addCleanup(self.client.delete, publisher['_href'])
        publication = publish(self.cfg, publisher, self.repo)
        delete_version(self.repo)
        with self.assertRaises(HTTPError):
            self.client.get(publication['_href'])


class ContentImmutableRepoVersionTestCase(unittest.TestCase):
    """Test whether the content present in a repo version is immutable.

    This test targets the following issue:

    * `Pulp Smash #953 <https://github.com/PulpQE/pulp-smash/issues/953>`_
    """

    def test_all(self):
        """Test whether the content present in a repo version is immutable.

        Do the following:

        1. Create a repository that has at least one repository version.
        2. Attempt to update the content of a repository version.
        3. Assert that an HTTP exception is raised.
        4. Assert that the repository version was not updated.
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        client.request_kwargs['auth'] = get_auth()
        repo = client.post(REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['_href'])
        body = gen_remote(PYTHON_PYPI_URL)
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['_href'])
        sync(cfg, remote, repo)
        latest_version_href = client.get(repo['_href'])['_latest_version_href']
        with self.assertRaises(HTTPError):
            client.post(latest_version_href)
        repo = client.get(repo['_href'])
        self.assertEqual(latest_version_href, repo['_latest_version_href'])


class FilterRepoVersionTestCase(unittest.TestCase):
    """Test whether repository versions can be filtered.

    These tests target the following issues:

    * `Pulp #3238 <https://pulp.plan.io/issues/3238>`_
    * `Pulp #3536 <https://pulp.plan.io/issues/3536>`_
    * `Pulp #3557 <https://pulp.plan.io/issues/3557>`_
    * `Pulp #3558 <https://pulp.plan.io/issues/3558>`_
    * `Pulp Smash #880 <https://github.com/PulpQE/pulp-smash/issues/880>`_
    """

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables.

        Add content to Pulp.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        populate_pulp(cls.cfg)
        cls.contents = cls.client.get(PYTHON_CONTENT_PATH)['results']

    def setUp(self):
        """Create a repository and give it new versions."""
        self.repo = self.client.post(REPO_PATH, gen_repo())
        self.addCleanup(self.client.delete, self.repo['_href'])
        for content in self.contents[:10]:  # slice is arbitrary upper bound
            self.client.post(
                self.repo['_versions_href'],
                {'add_content_units': [content['_href']]}
            )
            time.sleep(1)
        self.repo = self.client.get(self.repo['_href'])

    def test_filter_invalid_content(self):
        """Filter repository version by invalid content."""
        with self.assertRaises(HTTPError):
            self.filter_repo_version({'content': utils.uuid4()})

    def test_filter_valid_content(self):
        """Filter repository versions by valid content."""
        content = choice(self.contents)
        repo_versions = self.filter_repo_version({'content': content['_href']})['results']
        for repo_version in repo_versions:
            self.assertIn(
                self.client.get(content['_href']),
                get_content(self.repo, repo_version['_href'])['results']
            )

    def test_filter_invalid_date(self):
        """Filter repository version by invalid date."""
        criteria = utils.uuid4()
        version_filters = (
            {'created': criteria},
            {'created__gt': criteria, 'created__lt': criteria},
            {'created__gte': criteria, 'created__lte': criteria},
            {'created__range': ','.join((criteria, criteria))}
        )
        for params in version_filters:
            with self.subTest(params=params):
                page = self.filter_repo_version(params)
                self.assertEqual(len(page['results']), 0, page['results'])

    def test_filter_valid_date(self):
        """Filter repository version by a valid date."""
        dates = self.get_repo_versions_attr('created')
        version_filters = (
            ({'created': dates[0]}, 1),
            ({'created__gt': dates[0], 'created__lt': dates[-1]}, len(dates) - 2),
            ({'created__gte': dates[0], 'created__lte': dates[-1]}, len(dates)),
            ({'created__range': ','.join((dates[0], dates[1]))}, 2)
        )
        for params, num_results in version_filters:
            with self.subTest(params=params):
                results = self.filter_repo_version(params)['results']
                self.assertEqual(len(results), num_results, results)

    def test_filter_invalid_version(self):
        """Filter repository version by an invalid version number."""
        criteria = utils.uuid4()
        version_filters = (
            {'number': criteria},
            {'number__gt': criteria, 'number__lt': criteria},
            {'number__gte': criteria, 'number__lte': criteria},
            {'number__range': ','.join((criteria, criteria))}
        )
        for params in version_filters:
            with self.subTest(params=params):
                page = self.filter_repo_version(params)
                self.assertEqual(len(page['results']), 0, page['results'])

    def test_filter_valid_version(self):
        """Filter repository version by a valid version number."""
        numbers = self.get_repo_versions_attr('number')
        version_filters = (
            ({'number': numbers[0]}, 1),
            ({'number__gt': numbers[0], 'number__lt': numbers[-1]}, len(numbers) - 2),
            ({'number__gte': numbers[0], 'number__lte': numbers[-1]}, len(numbers)),
            ({'number__range': '{},{}'.format(numbers[0], numbers[1])}, 2)
        )
        for params, num_results in version_filters:
            with self.subTest(params=params):
                results = self.filter_repo_version(params)['results']
                self.assertEqual(len(results), num_results, results)

    def test_deleted_version_filter(self):
        """Delete a repository version and filter by its number."""
        numbers = self.get_repo_versions_attr('number')
        delete_version(self.repo)
        page = self.filter_repo_version({'number': numbers[-1]})
        self.assertEqual(len(page['results']), 0, page['results'])

    def filter_repo_version(self, params):
        """Filter repository version based on the given criteria."""
        return self.client.get(self.repo['_versions_href'], params=params)

    def get_repo_versions_attr(self, attr):
        """ Get an ``attr`` about each version of ``self.repo``.
        Return as sorted list.
        """
        attributes = [
            repo_version[attr] for repo_version in
            self.client.get(self.repo['_versions_href'])['results']
        ]
        attributes.sort()
        return attributes
