"""
Commands related to searching for packages in a Python repository.
"""
from gettext import gettext as _

from pulp.client.commands import options
from pulp.client.commands.criteria import DisplayUnitAssociationsCommand

from pulp_python.common import constants


DESC_SEARCH = _('search for packages in a repository')


class PackagesCommand(DisplayUnitAssociationsCommand):
    """
    This command is used to search for existing Python packages in a repository.
    """

    def __init__(self, context):
        """
        Initialize the command.

        :param context: The CLI context
        :type  context: pulp.client.extensions.core.ClientContext
        """
        super(PackagesCommand, self).__init__(self.run, name='packages',
                                              description=DESC_SEARCH)
        self.context = context
        self.prompt = context.prompt

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

        self.prompt.render_document_list(packages, order=order)
