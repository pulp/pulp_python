import hashlib

from mongoengine import StringField
from pulp.server.db.model import FileContentUnit
from twine.package import PackageFile  # noqa

from pulp_python.common import constants


DEFAULT_CHECKSUM_TYPE = 'sha512'
PACKAGE_ATTRS = ('author', 'name', 'packagetype', 'summary', 'url', 'version')


class Package(FileContentUnit):
    """
    This class represents a Python package.

    Packages stored on PyPI have significantly more metadata associated with them, but we have
    chosen to keep this model minimal. Below is an explanation for why this was done.

    There are some overloaded terms that should be briefly discussed. We will be using the
    semantics of PEP 426. https://www.python.org/dev/peps/pep-0426/#id14

    Package - An individual, installable python package. A package is defined by the project,
              target architecture, and Python version. Note that there may not be a target
              architecture in the case of architecture agnostic packages. A Python version is also
              optional if there are no requirements for a specific runtime version. There are 3
              packaging formats: sdist, whl, and zip.
    Release - A snapshot of the project. A particular release of the project will all share the
              same version number, but there may be multiple packages for a given release for
              different architectures, python versions, and package types.
    Project - The entire group of packages of all releases.

    The way that PyPI stores the metadata on their end leaves this model open to potential
    inaccuracies. Many packages of the same project share a significant amount of metadata,
    including mutable fields. In the situation where a mutable field changes between releases, only
    the latest version is present in the metadata accessible over the API. This is could be
    particularly problematic for a field like "license". For this reason, most of these fields have
    been left out of this model. The only fields that are included here are necessary for sync
    (name, version, filename) or are useful for disambiguation between similarly named projects
    (author, summary). By keeping the scope of the metadata as small as is reasonable, we have less
    complexity and reduced risk of innacuracy.

    :ivar author: primary author of the package
    :type author: basestring
    :ivar filename: name of the file containing the package and metadata
    :type filename: basestring
    :ivar md5_digest: md5 checksum provided by PyPI to ensure we got the correct bits
    :type md5_digest: basestring
    :ivar name: name of the project, ex. scipy
    :type name: basestring
    :ivar packagetype: format of python package, ex bdist_wheel, sdist
    :type packagetype: basestring
    :ivar url: url that is the source of bits for this package
    :type url: basestring
    :ivar version: Contains the distribution's version number. This field must be in the format
                   specified in PEP 386.
    :type version: basestring
    :ivar summary: one line summary of what the package does
    :type summary: basestring
    """

    author = StringField()
    filename = StringField(required=True)
    md5_digest = StringField()
    name = StringField(required=True)
    packagetype = StringField()
    summary = StringField()
    url = StringField()
    version = StringField(required=True)

    _checksum = StringField()
    _checksum_type = StringField(default=DEFAULT_CHECKSUM_TYPE)

    # For backward compatibility
    _ns = StringField(default='units_python_package')
    _content_type_id = StringField(required=True, default=constants.PACKAGE_TYPE_ID)

    unit_key_fields = ('filename',)

    meta = {
        'allow_inheritance': False,
        'collection': 'units_python_package',
        'indexes': [{'fields': ['-filename'], 'unique': True}],
    }

    @classmethod
    def from_json(cls, package_data, release, project_data):
        """
        Create and return (but do not save) an instance of a single python package object from the
        metadata available from PyPI JSON.

        :param package_data: metadata specific to a file
        :type  package_data: dict
        :param release: version number
        :type  release: basestring
        :param project_data: metadata that applies to all versions
        :type  project_data: dict
        :return: instance of a package
        :rtype:  pulp_python.plugins.models.Package
        """
        package_attrs = {}
        package_attrs['filename'] = package_data['filename']
        package_attrs['url'] = package_data['url']
        package_attrs['name'] = project_data['name']
        package_attrs['packagetype'] = package_data['packagetype']
        package_attrs['md5_digest'] = package_attrs['_checksum'] = package_data['md5_digest']
        package_attrs['_checksum_type'] = "md5"
        package_attrs['version'] = release
        package_attrs['author'] = project_data['author']
        package_attrs['summary'] = project_data['summary']
        return cls(**package_attrs)

    @classmethod
    def from_archive(cls, path):
        """
        Create and return (but do not save) an instance of a python package object from the package
        itself.

        Twine is smart enough to crack open a tarball, zip, or wheel and parse the metadata that is
        contained in the package.

        :param path: path to the package
        :type  path: basestring
        :return: instance of a package
        :rtype:  pulp_python.plugins.models.Package
        """
        meta_dict = PackageFile.from_filename(path, comment='').metadata_dictionary()
        filtered_dict = {}
        # Use only a subset of the attributes in the metadata to keep package minimal.
        for key, value in meta_dict.iteritems():
            if key in PACKAGE_ATTRS:
                filtered_dict[key] = value
        filtered_dict['filename'] = path.split('/')[-1]
        return cls(**filtered_dict)

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

    def __repr__(self):
        """
        :return: A string representing self.
        :rtype:  basestring
        """
        return 'Package(name={0}, version={1})'.format(self.name, self.version)
