"""
This module contains tests for the pulp_python.extensions.admin.cudl module.
"""
import unittest

import mock
from pulp.common.constants import REPO_NOTE_TYPE_KEY
from pulp.common.plugins.importer_constants import KEY_FEED
from pulp.devel.unit.util import compare_dict

from pulp_python.common import constants
from pulp_python.extensions.admin import cudl


class TestCreatePythonRepositoryCommand(unittest.TestCase):
    @mock.patch('pulp_python.extensions.admin.cudl.CreateAndConfigureRepositoryCommand.__init__')
    @mock.patch('pulp_python.extensions.admin.cudl.ImporterConfigMixin.__init__')
    @mock.patch('pulp_python.extensions.admin.cudl.PythonRepositoryOptions.__init__')
    def test___init__(self, pro___init__, icm___init__, cacrc___init__):
        """
        Assert that __init__ works correctly.
        """
        context = mock.MagicMock()

        cprc = cudl.CreatePythonRepositoryCommand(context)

        cacrc___init__.assert_called_once_with(cprc, context)
        icm___init__.assert_called_once_with(cprc, **cudl.IMPORTER_CONFIGURATION_FLAGS)
        pro___init__.assert_called_once_with(cprc)

    def test_default_notes(self):
        # make sure this value is set and is correct
        self.assertEqual(cudl.CreatePythonRepositoryCommand.default_notes.get(REPO_NOTE_TYPE_KEY),
                         constants.REPO_NOTE_PYTHON)

    def test_importer_id(self):
        # this value is required to be set, so just make sure it's correct
        self.assertEqual(cudl.CreatePythonRepositoryCommand.IMPORTER_TYPE_ID,
                         constants.IMPORTER_TYPE_ID)


class TestPythonRespositoryOptions(unittest.TestCase):
    """
    Test the PythonRespositoryOptions mixin class.
    """
    class MixinTestClass(cudl.PythonRepositoryOptions):
        """
        PythonRepositoryOptions depends on self having add_option() and self.options_bundle,
        which it will only have if it is used as a mixin with
        CreateAndConfigureRepositoryCommand or ImporterConfigMixin. This test class simulates
        that use case so that __init__ can be used.
        """
        def __init__(self):
            self.options_bundle = mock.MagicMock()
            self.add_option = mock.MagicMock()

            super(TestPythonRespositoryOptions.MixinTestClass, self).__init__()

    def test___init__(self):
        """
        Assert correct behavior from the __init__() method.
        """
        pro = TestPythonRespositoryOptions.MixinTestClass()

        added_options = set([c[1][0] for c in pro.add_option.mock_calls])
        expected_options = set([cudl.OPT_AUTO_PUBLISH, cudl.OPT_PACKAGE_NAMES])
        self.assertEqual(added_options, expected_options)
        self.assertEqual(pro.options_bundle.opt_feed.description, cudl.DESC_FEED)

    def test_describe_distributors(self):
        command = TestPythonRespositoryOptions.MixinTestClass()
        # by default the value is set to None
        user_input = {
            'auto-publish': None
        }
        result = command._describe_distributors(user_input)
        target_result = {'distributor_id': constants.CLI_DISTRIBUTOR_ID,
                         'distributor_type_id': constants.DISTRIBUTOR_TYPE_ID,
                         'distributor_config': {},
                         'auto_publish': True}
        compare_dict(result[0], target_result)

    def test_describe_distributors_override_auto_publish(self):
        command = TestPythonRespositoryOptions.MixinTestClass()
        user_input = {
            'auto-publish': False
        }
        result = command._describe_distributors(user_input)
        self.assertEquals(result[0]["auto_publish"], False)

    @mock.patch('pulp_python.extensions.admin.cudl.PythonRepositoryOptions.parse_user_input',
                create=True)
    def test__parse_importer_config_no_input(self, parse_user_input):
        """
        Assert correct behavior from _parse_importer_config when there is no special user input to
        parse.
        """
        command = TestPythonRespositoryOptions.MixinTestClass()
        user_input = {}
        parse_user_input.return_value = {}

        result = command._parse_importer_config(user_input)

        parse_user_input.assert_called_once_with({})
        expected_result = {}
        compare_dict(result, expected_result)

    @mock.patch('pulp_python.extensions.admin.cudl.PythonRepositoryOptions.parse_user_input',
                create=True)
    def test__parse_importer_config_with_input(self, parse_user_input):
        """
        Assert correct behavior from _parse_importer_config when there is no special user input to
        parse.
        """
        command = TestPythonRespositoryOptions.MixinTestClass()
        user_input = {'some': 'input'}
        parse_user_input.return_value = {'some': 'input'}

        result = command._parse_importer_config(user_input)

        parse_user_input.assert_called_once_with(user_input)
        expected_result = {'some': 'input'}
        compare_dict(result, expected_result)

    @mock.patch('pulp_python.extensions.admin.cudl.PythonRepositoryOptions.parse_user_input',
                create=True)
    def test__parse_importer_config_with_package_names(self, parse_user_input):
        """
        Assert correct behavior from _parse_importer_config when there is no special user input to
        parse.
        """
        command = TestPythonRespositoryOptions.MixinTestClass()
        user_input = {'some': 'input', cudl.OPT_PACKAGE_NAMES.keyword: 'django,numpy,scipy'}
        parse_user_input.return_value = {'some': 'input'}

        result = command._parse_importer_config(user_input)

        parse_user_input.assert_called_once_with(user_input)
        expected_result = {constants.CONFIG_KEY_PACKAGE_NAMES: 'django,numpy,scipy',
                           'some': 'input'}
        compare_dict(result, expected_result)


class TestUpdatePythonRepositoryCommand(unittest.TestCase):

    def setUp(self):
        self.context = mock.Mock()
        self.context.config = {'output': {'poll_frequency_in_seconds': 3}}
        self.command = cudl.UpdatePythonRepositoryCommand(self.context)
        self.command.poll = mock.Mock()
        self.mock_repo_response = mock.Mock(response_body={})
        self.context.server.repo.repository.return_value = self.mock_repo_response

    @mock.patch('pulp_python.extensions.admin.cudl.ImporterConfigMixin.__init__')
    @mock.patch('pulp_python.extensions.admin.cudl.PythonRepositoryOptions.__init__')
    @mock.patch('pulp_python.extensions.admin.cudl.UpdateRepositoryCommand.__init__')
    def test___init__(self, urc___init__, pro___init__, icm___init__):
        """
        Assert that __init__ works correctly.
        """
        context = mock.MagicMock()

        cprc = cudl.UpdatePythonRepositoryCommand(context)

        urc___init__.assert_called_once_with(cprc, context)
        icm___init__.assert_called_once_with(cprc, **cudl.IMPORTER_CONFIGURATION_FLAGS)
        pro___init__.assert_called_once_with(cprc)

    def test_run_with_importer_config(self):
        user_input = {
            'repo-id': 'foo-repo',
            KEY_FEED: 'blah',
        }
        self.command.run(**user_input)

        expected_importer_config = {KEY_FEED: 'blah'}

        self.context.server.repo.update.assert_called_once_with('foo-repo', {},
                                                                expected_importer_config, None)

    def test_run_with_package_names(self):
        user_input = {'repo-id': 'foo-repo', KEY_FEED: 'blah',
                      cudl.OPT_PACKAGE_NAMES.keyword: 'django,numpy,scipy'}

        self.command.run(**user_input)

        expected_importer_config = {KEY_FEED: 'blah',
                                    constants.CONFIG_KEY_PACKAGE_NAMES: 'django,numpy,scipy'}

        self.context.server.repo.update.assert_called_once_with('foo-repo', {},
                                                                expected_importer_config, None)

    def test_repo_update_distributors(self):
        user_input = {
            'auto-publish': False,
            'repo-id': 'foo-repo'
        }

        self.command.run(**user_input)

        repo_config = {}
        dist_config = {constants.CLI_DISTRIBUTOR_ID: {'auto_publish': False}}
        self.context.server.repo.update.assert_called_once_with('foo-repo', repo_config,
                                                                None, dist_config)

    def test_repo_update_importer_remove_branches(self):
        user_input = {
            'repo-id': 'foo-repo'
        }
        self.command.run(**user_input)

        repo_config = {}
        importer_config = None
        self.context.server.repo.update.assert_called_once_with('foo-repo', repo_config,
                                                                importer_config, None)


class TestListPythonRepositoriesCommand(unittest.TestCase):
    def setUp(self):
        self.context = mock.Mock()
        self.context.config = {'output': {'poll_frequency_in_seconds': 3}}

    def test_get_all_repos(self):
        self.context.server.repo.repositories.return_value.response_body = 'foo'
        command = cudl.ListPythonRepositoriesCommand(self.context)
        result = command._all_repos({'bar': 'baz'})
        self.context.server.repo.repositories.assert_called_once_with({'bar': 'baz'})
        self.assertEquals('foo', result)

    def test_get_all_repos_caches_results(self):
        command = cudl.ListPythonRepositoriesCommand(self.context)
        command.all_repos_cache = 'foo'
        result = command._all_repos({'bar': 'baz'})
        self.assertFalse(self.context.server.repo.repositories.called)
        self.assertEquals('foo', result)

    def test_get_repositories(self):
        # Setup
        repos = [
            {
                'id': 'matching',
                'notes': {REPO_NOTE_TYPE_KEY: constants.REPO_NOTE_PYTHON, },
                'importers': [
                    {'config': {}}
                ],
                'distributors': [
                    {'id': constants.CLI_DISTRIBUTOR_ID}
                ]
            },
            {'id': 'non-rpm-repo',
             'notes': {}}
        ]
        self.context.server.repo.repositories.return_value.response_body = repos

        # Test
        command = cudl.ListPythonRepositoriesCommand(self.context)
        repos = command.get_repositories({})

        # Verify
        self.assertEqual(1, len(repos))
        self.assertEqual(repos[0]['id'], 'matching')

    def test_get_repositories_no_details(self):
        # Setup
        repos = [
            {
                'id': 'foo',
                'display_name': 'bar',
                'notes': {REPO_NOTE_TYPE_KEY: constants.REPO_NOTE_PYTHON, }
            }
        ]
        self.context.server.repo.repositories.return_value.response_body = repos

        # Test
        command = cudl.ListPythonRepositoriesCommand(self.context)
        repos = command.get_repositories({})

        # Verify
        self.assertEqual(1, len(repos))
        self.assertEqual(repos[0]['id'], 'foo')
        self.assertTrue('importers' not in repos[0])
        self.assertTrue('distributors' not in repos[0])

    def test_get_other_repositories(self):
        # Setup
        repos = [
            {
                'repo_id': 'matching',
                'notes': {REPO_NOTE_TYPE_KEY: constants.REPO_NOTE_PYTHON, },
                'distributors': [
                    {'id': constants.CLI_DISTRIBUTOR_ID}
                ]
            },
            {
                'repo_id': 'non-python-repo-1',
                'notes': {}
            }
        ]
        self.context.server.repo.repositories.return_value.response_body = repos

        # Test
        command = cudl.ListPythonRepositoriesCommand(self.context)
        repos = command.get_other_repositories({})

        # Verify
        self.assertEqual(1, len(repos))
        self.assertEqual(repos[0]['repo_id'], 'non-python-repo-1')
