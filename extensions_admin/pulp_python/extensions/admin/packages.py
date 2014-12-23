"""
Commands related to searching for packages in a Python repository.
"""
from gettext import gettext as _

from pulp.client.commands import options, unit
from pulp.client.commands.criteria import DisplayUnitAssociationsCommand

from pulp_python.common import constants


DESC_COPY = _('copies packages from one repository to another')
DESC_SEARCH = _('search for packages in a repository')


class CopyPackagesCommand(unit.UnitCopyCommand):
    """
    Copies packages from one repository to another.
    """
    def __init__(self, context):
        """
        Initialize the command.

        :param context: The CLI context
        :type  context: pulp.client.extensions.core.ClientContext
        """
        super(CopyPackagesCommand, self).__init__(context, description=DESC_COPY,
                                                  type_id=constants.PACKAGE_TYPE_ID)

    @staticmethod
    def get_formatter_for_type(type_id):
        """
        Returns a method that can be used to format the unit key of a python package for display
        purposes.

        :param type_id: The type_id of the unit key to get a formatter for.
        :type  type_id: str
        :return:        A function that can format a Python package unit key for display.
        :rtype:         function
        """
        return lambda x: '%(name)s-%(version)s' % x


class ListPackagesCommand(DisplayUnitAssociationsCommand):
    """
    This command is used to search for existing Python packages in a repository.
    """
    def __init__(self, context):
        """
        Initialize the command.

        :param context: The CLI context
        :type  context: pulp.client.extensions.core.ClientContext
        """
        super(ListPackagesCommand, self).__init__(self.run, name='packages',
                                                  description=DESC_SEARCH)
        self.context = context

    def run(self, **kwargs):
        """
        Query the server for the packages, and render them for the user.

        :param kwargs: The CLI options passed by the user
        :type  kwargs: dict
        """
        # Retrieve the packages
        repo_id = kwargs.pop(options.OPTION_REPO_ID.keyword)
        kwargs['type_ids'] = [constants.PACKAGE_TYPE_ID]
        packages = self.context.server.repo_unit.search(repo_id, **kwargs).response_body

        order = []

        if not kwargs.get(self.ASSOCIATION_FLAG.keyword):
            packages = [m['metadata'] for m in packages]
            # Make sure the key info is at the top; the rest can be alpha
            order = ['name', 'version', 'author']

        self.context.prompt.render_document_list(packages, order=order)
