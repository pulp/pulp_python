from gettext import gettext as _
import shutil

from pulp.plugins.importer import Importer

from pulp_python.common import constants
from pulp_python.plugins import models


def entry_point():
    """
    Entry point that pulp platform uses to load the importer

    :return: 2-tuple of the importer class and its config
    :rtype:  tuple
    """
    return PythonImporter, {}


class PythonImporter(Importer):
    """
    This class is used to import Python modules into Pulp.
    """

    @classmethod
    def metadata(cls):
        """
        Used by Pulp to classify the capabilities of this importer. The
        following keys must be present in the returned dictionary:

        * id           - Programmatic way to refer to this importer. Must be unique
                         across all importers. Only letters and underscores are valid.
        * display_name - User-friendly identification of the importer.
        * types        - List of all content type IDs that may be imported using this
                         importer.

        :return: keys and values listed above
        :rtype:  dict
        """
        return {
            'id': constants.IMPORTER_TYPE_ID,
            'display_name': _('Python Importer'),
            'types': [constants.PACKAGE_TYPE_ID]
        }

    def upload_unit(self, repo, type_id, unit_key, metadata, file_path, conduit, config):
        """
        Handles a user request to upload a unit into a repository. This call
        should use the data provided to add the unit as if it were synchronized
        from an external source. This includes:

        * Initializing the unit through the conduit which populates the final
          destination of the unit.
        * Moving the unit from the provided temporary location into the unit's
          final destination.
        * Saving the unit in Pulp, which both adds the unit to Pulp's database and
          associates it to the repository.

        This call may be invoked for either units that do not already exist as
        well as re-uploading an existing unit.

        The metadata parameter is variable in its usage. In some cases, the
        unit may be almost exclusively metadata driven in which case the contents
        of this parameter will be used directly as the unit's metadata. In others,
        it may function to remove the importer's need to derive the unit's metadata
        from the uploaded unit file. In still others, it may be extraneous
        user-specified information that should be merged in with any derived
        unit metadata.

        Depending on the unit type, it is possible that this call will create
        multiple units within Pulp. It is also possible that this call will
        create one or more relationships between existing units.

        :param repo:      metadata describing the repository
        :type  repo:      pulp.plugins.model.Repository
        :param type_id:   type of unit being uploaded
        :type  type_id:   str
        :param unit_key:  identifier for the unit, specified by the user
        :type  unit_key:  dict
        :param metadata:  any user-specified metadata for the unit
        :type  metadata:  dict
        :param file_path: path on the Pulp server's filesystem to the temporary location of the
                          uploaded file; may be None in the event that a unit is comprised entirely
                          of metadata and has no bits associated
        :type  file_path: str
        :param conduit:   provides access to relevant Pulp functionality
        :type  conduit:   pulp.plugins.conduits.unit_add.UnitAddConduit
        :param config:    plugin configuration for the repository
        :type  config:    pulp.plugins.config.PluginCallConfiguration
        :return:          A dictionary describing the success or failure of the upload. It must
                          contain the following keys:
                            'success_flag': bool. Indicates whether the upload was successful
                            'summary':      json-serializable object, providing summary
                            'details':      json-serializable object, providing details
        :rtype:           dict
        """
        package = models.Package.from_archive(file_path)
        package.init_unit(conduit)

        shutil.move(file_path, package.storage_path)

        package.save_unit(conduit)

        return {'success_flag': True, 'summary': {}, 'details': {}}

    def validate_config(self, repo, config):
        """
        We don't have a config yet, so it's always valid

        :param repo:   metadata describing the repository
        :type  repo:   pulp.plugins.model.Repository
        :param config: plugin configuration for the repository
        :type  config: pulp.plugins.config.PluginCallConfiguration
        :return:       This always returns (True, '')
        :rtype:        tuple
        """
        return True, ''
