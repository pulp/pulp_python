from pulp.client.commands.repo import upload

from pulp_python.common import constants


class UploadPackageCommand(upload.UploadCommand):
    """
    The command used to upload Python packages.
    """
    def determine_type_id(self, filename, **kwargs):
        """
        Return pulp_python.common.constants.PACKAGE_TYPE_ID.

        :param filename: Unused
        :type  filename: basestring
        :param kwargs:   Unused
        :type  kwargs:   dict
        :returns:        pulp_python.common.constants.PACKAGE_TYPE_ID
        :rtype:          basestring
        """
        return constants.PACKAGE_TYPE_ID

    def generate_unit_key(self, *args, **kwargs):
        """
        We don't need to generate the unit key client-side, but the superclass requires us to define
        this method. It returns the empty dictionary.

        :param args:   Unused
        :type  args:   list
        :param kwargs: Unused
        :type  kwargs: dict
        :returns:      An empty dictionary
        :rtype:        dict
        """
        return {}
