"""
This module contains tests for the pulp_python.extensions.admin.packages module.
"""
import unittest

from pulp.client.commands import options
import mock

from pulp_python.common import constants
from pulp_python.extensions.admin import packages


class TestPackagesCommand(unittest.TestCase):
    """
    This class contains tests for the PackagesCommand class.
    """
    @mock.patch('pulp_python.extensions.admin.packages.DisplayUnitAssociationsCommand.__init__')
    def test___init__(self, super___init__):
        """
        Assert correct behavior from __init__().
        """
        context = mock.MagicMock()

        c = packages.PackagesCommand(context)

        super___init__.assert_called_once_with(c.run, name='packages',
                                               description=packages.DESC_SEARCH)
        self.assertEqual(c.context, context)
        self.assertEqual(c.prompt, context.prompt)

    def test_run_with_details(self):
        """
        Test the run() method with the details flag.
        """
        _packages = ['package_1', 'package_2']

        def search(_repo_id, **_kwargs):
            """
            Fakes the server search.
            """
            self.assertEqual(_repo_id, 'some_repo')
            self.assertEqual(
                _kwargs,
                {'type_ids': [constants.PACKAGE_TYPE_ID], c.ASSOCIATION_FLAG.keyword: True})

            response = mock.MagicMock()
            response.response_body = _packages
            return response

        context = mock.MagicMock()
        context.server.repo_unit.search.side_effect = search
        c = packages.PackagesCommand(context)
        kwargs = {options.OPTION_REPO_ID.keyword: 'some_repo', c.ASSOCIATION_FLAG.keyword: True}

        c.run(**kwargs)

        c.prompt.render_document_list.assert_called_once_with(_packages, order=[])

    def test_run_without_details(self):
        """
        Test the run() method without the details flag.
        """
        _packages = [{'metadata': 'package_1'}, {'metadata': 'package_2'}]

        def search(_repo_id, **_kwargs):
            """
            Fakes the server search.
            """
            self.assertEqual(_repo_id, 'some_repo')
            self.assertEqual(
                _kwargs,
                {'type_ids': [constants.PACKAGE_TYPE_ID]})

            response = mock.MagicMock()
            response.response_body = _packages
            return response

        context = mock.MagicMock()
        context.server.repo_unit.search.side_effect = search
        c = packages.PackagesCommand(context)
        kwargs = {options.OPTION_REPO_ID.keyword: 'some_repo'}

        c.run(**kwargs)

        c.prompt.render_document_list.assert_called_once_with(['package_1', 'package_2'],
                                                              order=['name', 'version', 'author'])


class TestPackageRemoveCommand(unittest.TestCase):
    """
    This class contains tests for the PackageRemoveCommand class.
    """
    @mock.patch('pulp_python.extensions.admin.packages.UnitRemoveCommand.__init__')
    def test___init__(self, super___init__):
        """
        Assert correct behavior from __init__().
        """
        context = mock.MagicMock()

        c = packages.PackageRemoveCommand(context)

        super___init__.assert_called_once_with(c, context, name='remove',
                                               description=packages.DESC_REMOVE,
                                               type_id=constants.PACKAGE_TYPE_ID)

    def test_get_formatter_for_type(self):
        """
        Assert correct behavior from get_formatter_for_type().
        """
        context = mock.MagicMock()
        command = packages.PackageRemoveCommand(context)

        formatter = command.get_formatter_for_type(constants.PACKAGE_TYPE_ID)
        self.assertEquals('test-name-test-version', formatter({'name': 'test-name',
                                                               'version': 'test-version'}))

    def test_get_formatter_for_type_raises_value_error(self):
        """
        Assert wrong type_id for get_formatter_for_type() raises ValueError.
        """
        self.assertRaises(ValueError, packages.PackageRemoveCommand.get_formatter_for_type,
                          'foo-type')
