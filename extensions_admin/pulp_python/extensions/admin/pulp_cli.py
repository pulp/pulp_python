from gettext import gettext as _

from pulp.client.commands.repo import cudl, sync_publish, status
from pulp.client.extensions.decorator import priority

from pulp_python.common import constants
from pulp_python.extensions.admin.cudl import (
    CreatePythonRepositoryCommand, UpdatePythonRepositoryCommand, ListPythonRepositoriesCommand)
from pulp_python.extensions.admin import packages, upload


SECTION_ROOT = 'python'
DESC_ROOT = _('manage python repositories')

SECTION_REPO = 'repo'
DESC_REPO = _('repository lifecycle commands')

SECTION_PUBLISH = 'publish'
DESC_PUBLISH = _('publish a python repository')

SECTION_SYNC = 'sync'
DESC_SYNC = _('sync a python repository from an upstream repository')


@priority()
def initialize(context):
    """
    Create the python CLI section and add it to the root

    :param context: the CLI context.
    :type context:  pulp.client.extensions.core.ClientContext
    """
    root_section = context.cli.create_section(SECTION_ROOT, DESC_ROOT)
    _add_repo_section(context, root_section)


def _add_repo_section(context, parent_section):
    """
    add a repo section to the python section

    :param context:         The client context
    :type  context:         pulp.client.extensions.core.ClientContext
    :param parent_section:  section of the CLI to which the repo section
                            should be added
    :type  parent_section:  pulp.client.extensions.extensions.PulpCliSection
    """
    repo_section = parent_section.create_subsection(SECTION_REPO, DESC_REPO)

    repo_section.add_command(CreatePythonRepositoryCommand(context))
    repo_section.add_command(UpdatePythonRepositoryCommand(context))
    repo_section.add_command(cudl.DeleteRepositoryCommand(context))
    repo_section.add_command(ListPythonRepositoriesCommand(context))

    _add_publish_section(context, repo_section)
    _add_sync_section(context, repo_section)

    repo_section.add_command(upload.UploadPackageCommand(context))
    repo_section.add_command(packages.PackagesCommand(context))
    repo_section.add_command(packages.PackageRemoveCommand(context))


def _add_publish_section(context, parent_section):
    """
    add a publish section to the repo section

    :param context:        The client context
    :type  context:        pulp.client.extensions.core.ClientContext
    :param parent_section: section of the CLI to which the repo section should be added
    :type  parent_section: pulp.client.extensions.extensions.PulpCliSection
    """
    section = parent_section.create_subsection(SECTION_PUBLISH, DESC_PUBLISH)

    renderer = status.PublishStepStatusRenderer(context)
    section.add_command(
        sync_publish.RunPublishRepositoryCommand(context,
                                                 renderer,
                                                 constants.CLI_DISTRIBUTOR_ID))
    section.add_command(
        sync_publish.PublishStatusCommand(context, renderer))


def _add_sync_section(context, parent_section):
    """
    add a sync section

    :param context:        pulp context
    :type  context:        pulp.client.extensions.core.ClientContext
    :param parent_section: section of the CLI to which the upload section
                           should be added
    :type  parent_section: pulp.client.extensions.extensions.PulpCliSection
    :return:               populated section
    :rtype:                PulpCliSection
    """
    renderer = status.PublishStepStatusRenderer(context)

    sync_section = parent_section.create_subsection(SECTION_SYNC, DESC_SYNC)
    sync_section.add_command(sync_publish.RunSyncRepositoryCommand(context, renderer))
