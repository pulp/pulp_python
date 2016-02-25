from gettext import gettext as _
import hashlib
import re
import tarfile

from mongoengine import StringField
from pulp.server.db.model import FileContentUnit

from pulp_python.common import constants


DEFAULT_CHECKSUM_TYPE = 'sha512'


# These are required to be in the PKG-INFO file.
REQUIRED_ATTRS = ('name', 'version', 'summary', 'home_page', 'author', 'author_email', 'license',
                  'description', 'platform')


class Package(FileContentUnit):
    """
    This class represents a Python package.
    """

    # unit key
    name = StringField(required=True)
    version = StringField(required=True)

    author = StringField()
    author_email = StringField()
    description = StringField()
    home_page = StringField()
    license = StringField()
    platform = StringField()
    summary = StringField()

    _checksum = StringField()
    _checksum_type = StringField(default=DEFAULT_CHECKSUM_TYPE)
    _filename = StringField()
    _metadata_file = StringField()

    # For backward compatibility
    _ns = StringField(default='units_python_package')
    _content_type_id = StringField(required=True, default=constants.PACKAGE_TYPE_ID)

    unit_key_fields = ('name', 'version')

    meta = {
        'allow_inheritance': False,
        'collection': 'units_python_package',
        'indexes': [],
    }

    @classmethod
    def from_archive(cls, archive_path):
        """
        Instantiate a Package using the metadata found inside the Python package found at
        archive_path. This tarball should be the build result of running setup.py sdist on the
        package, and should contain a PKG-INFO file. This method will read the PKG-INFO to determine
        the package's metadata and unit key.

        :param archive_path: A filesystem path to the Python source distribution that this Package
                             will represent.
        :type  archive_path: basestring
        :return:             An instance of Package that represents the package found at
                             archive_path.
        :rtype:              pulp_python.plugins.models.Package
        :raises:             ValueError if archive_path does not point to a valid Python tarball
                             created with setup.py sdist.
        :raises:             IOError if the archive_path does not exist.
        """
        try:
            compression_type = cls._compression_type(archive_path)
            checksum = cls.checksum(archive_path)
            package_archive = tarfile.open(archive_path)
            metadata_file = None
            for member in package_archive.getmembers():
                if re.match('.*/PKG-INFO$|^PKG-INFO$', member.name):
                    # find the metadata file with the shortest path
                    if metadata_file:
                        if len(member.name) < len(metadata_file.name):
                            metadata_file = member
                    else:
                        metadata_file = member
            if not metadata_file:
                msg = _('The archive at %(path)s does not contain a PKG-INFO file.')
                msg = msg % {'path': archive_path}
                raise ValueError(msg)

            metadata_file_name = metadata_file.name
            metadata_file = package_archive.extractfile(metadata_file)
            metadata = metadata_file.read()

            # Build a list of tuples of all the attributes found in the metadata. Ignore attributes
            # with a leading underscore, as they are not part of the metadata.
            attrs = dict()
            try:
                for attr in REQUIRED_ATTRS:
                    attrs[attr] = re.search('^%s: (?P<field>.*?)\s*$' % cls._metadata_label(attr),
                                            metadata, flags=re.MULTILINE).group('field')
            except AttributeError:
                msg = _('The PKG-INFO file is missing required attributes. Please ensure that the '
                        'following attributes are all present: %(attrs)s')
                msg = msg % {
                    'attrs': ', '.join([cls._metadata_label(attr) for attr in REQUIRED_ATTRS])}
                raise ValueError(msg)

            # Add the filename, checksum, and checksum_type to the attrs
            attrs['_filename'] = '%s-%s.tar%s' % (attrs['name'], attrs['version'], compression_type)
            attrs['_checksum'] = checksum
            attrs['_checksum_type'] = DEFAULT_CHECKSUM_TYPE
            attrs['_metadata_file'] = metadata_file_name
            package = cls(**attrs)
            return package
        finally:
            if 'package_archive' in locals():
                package_archive.close()

    @staticmethod
    def checksum(path, algorithm=DEFAULT_CHECKSUM_TYPE):
        """
        Return the checksum of the given path using the given algorithm.

        :param path:      A path to a file
        :type  path:      basestring
        :param algorithm: The hashlib algorithm you wish to use
        :type  algorithm: basestring
        :return:          The file's checksum
        :rtype:           basestring
        """
        chunk_size = 32 * 1024 * 1024
        hasher = getattr(hashlib, algorithm)()
        with open(path) as file_handle:
            bits = file_handle.read(chunk_size)
            while bits:
                hasher.update(bits)
                bits = file_handle.read(chunk_size)
        return hasher.hexdigest()

    @staticmethod
    def _compression_type(path):
        """
        Return the type of compression used in the file at path. Can be '', '.bz2', '.gz', or
        '.zip'. '' is returned if the file at path matches none of the magic signatures. This
        algorithm is based on http://stackoverflow.com/a/13044946.

        :param path: The path to the file you wish to test for compression type.
        :type  path: basestring
        :return:     File extension used to represent the compression type found at path.
        :rtype:      basestring
        """
        magic_dict = {
            "\x1f\x8b\x08": ".gz",
            "\x42\x5a\x68": ".bz2",
            "\x50\x4b\x03\x04": ".zip"
        }
        # We need to read the first four bytes of the file to compare
        with open(path) as the_file:
            header = the_file.read(4)
        for magic, filetype in magic_dict.items():
            if header.startswith(magic):
                return filetype
        return ''

    @staticmethod
    def _metadata_label(attribute):
        """
        Return the label in the PKG-INFO file that corresponds to the given attribute.

        :param attribute: The attribute on a Package for which you wish to know the PKG-INFO label
        :type  attribute: basestring
        :return:          The label in the PKG-INFO file that can be used to get the field
        :rtype:           basestring
        """
        label = attribute[0].upper() + attribute[1:]
        return label.replace('_', '-')

    def __repr__(self):
        """
        :return: A string representing self.
        :rtype:  basestring
        """
        return 'Package(name={0}, version={1})'.format(self.name, self.version)
