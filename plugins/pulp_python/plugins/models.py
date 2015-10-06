from gettext import gettext as _
import hashlib
import re
import tarfile

from pulp_python.common import constants


DEFAULT_CHECKSUM_TYPE = 'sha512'


class Package(object):
    """
    This class represents a Python package.
    """

    TYPE = constants.PACKAGE_TYPE_ID
    # The full list of supported attributes. Attributes beginning with underscore are specific to
    # this module and are not found in PKG-INFO.
    _ATTRS = ('name', 'version', 'summary', 'home_page', 'author', 'author_email', 'license',
              'description', 'platform', '_filename', '_checksum', '_checksum_type',
              '_metadata_file')

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
        :rtype:              pulp.common.models.Package
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
            try:
                required_attrs = [attr for attr in cls._ATTRS if attr[0] != '_']
                attrs = dict()
                for attr in required_attrs:
                    attrs[attr] = re.search('^%s: (?P<field>.*?)\s*$' % cls._metadata_label(attr),
                                            metadata, flags=re.MULTILINE).group('field')
            except AttributeError:
                msg = _('The PKG-INFO file is missing required attributes. Please ensure that the '
                        'following attributes are all present: %(attrs)s')
                msg = msg % {
                    'attrs': ', '.join([cls._metadata_label(attr) for attr in required_attrs])}
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

    def init_unit(self, conduit):
        """
        Use the given conduit's init_unit() method to initialize this Unit and store the underlying
        Pulp unit as self._unit.

        :param conduit: A conduit with a suitable init_unit() to create a Pulp Unit.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        relative_path = self._filename
        unit_key = {'name': self.name, 'version': self.version}
        metadata = []
        for attr in self._ATTRS:
            if attr in unit_key:
                continue
            metadata.append((attr, getattr(self, attr)))
        metadata = dict(metadata)
        self._unit = conduit.init_unit(self.TYPE, unit_key, metadata, relative_path)

    def save_unit(self, conduit):
        """
        Use the given conduit's save_unit() method to save self._unit.

        :param conduit: A conduit with a suitable save_unit() to save self._unit.
        :type  conduit: pulp.plugins.conduits.mixins.AddUnitMixin
        """
        conduit.save_unit(self._unit)

    @property
    def storage_path(self):
        """
        Return the storage path for self._unit.

        :return: The Unit storage path.
        :rtype:  basestring
        """
        return self._unit.storage_path

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

    def __init__(self, name, version, summary, home_page, author, author_email, license,
                 description, platform, _filename, _checksum, _checksum_type, _metadata_file):
        """
        Initialize self with the given parameters as its attributes.

        :param name:           The name of the package.
        :type  name:           basestring
        :param version:        The package's version.
        :type  version:        basestring
        :param summary:        A paragraph summarizing the package.
        :type  summary:        basestring
        :param home_page:      A URL for the package's website.
        :type  home_page:      basestring
        :param author:         The author's name.
        :type  author:         basestring
        :param author_email:   The author's e-mail address.
        :type  author_email:   basestring
        :param license:        The package's license.
        :type  license:        basestring
        :param description:    A description of the package.
        :type  description:    basestring
        :param platform:       A list of platforms that the package is intended to be used on.
        :type  platform:       basestring
        :param _filename:      The package filename.
        :type  _filename:      basestring
        :param _checksum:      The checksum of the package.
        :type  _checksum:      basestring
        :param _checksum_type: The name of the algorithm used to calculate the checksum.
        :type  _checksum_type: basestring
        :param _metadata_file: The path of the metadata file in the package
        :type  _metadata_file: basestring
        """
        for attr in self._ATTRS:
            setattr(self, attr, locals()[attr])

        self._unit = None

    def __repr__(self):
        """
        Return a string representation of self.

        :return: A string representing self.
        :rtype:  basestring
        """
        return 'Python Package: %(name)s-%(version)s' % {'name': self.name, 'version': self.version}
