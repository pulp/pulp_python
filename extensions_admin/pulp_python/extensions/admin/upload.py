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
        :return:         pulp_python.common.constants.PACKAGE_TYPE_ID
        :rtype:          basestring
        """
        return constants.PACKAGE_TYPE_ID

    def generate_unit_key(self, filename, *args, **kwargs):
        """
        Generates the unit key for a Python unit, which is the filename.

        Unfortunately, what is passed in as "filename" here is actually a relative path to the
        file, not just the filename. I have chosen to leave the argument named as it is because
        this function is implementing behavior defined in core, and the variable name is set there.

        :param filename: path to the file which is being uploaded
        :type  filename: basestring
        :param args:     Unused
        :type  args:     list
        :param kwargs:   Unused
        :type  kwargs:   dict
        :return:         An empty dictionary
        :rtype:          dict
        """
        return {"filename": filename.split('/')[-1]}
