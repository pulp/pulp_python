from gettext import gettext as _
import os
import shutil
import tempfile

from packaging.requirements import Requirement
from rest_framework import serializers

from pulpcore.plugin import models as core_models
from pulpcore.plugin import serializers as core_serializers

from pulp_python.app import models as python_models
from pulp_python.app.tasks.upload import DIST_EXTENSIONS, DIST_TYPES
from pulp_python.app.utils import parse_project_metadata


class PythonRepositorySerializer(core_serializers.RepositorySerializer):
    """
    Serializer for Python Repositories.
    """

    class Meta:
        fields = core_serializers.RepositorySerializer.Meta.fields
        model = python_models.PythonRepository


class PythonDistributionSerializer(core_serializers.PublicationDistributionSerializer):
    """
    Serializer for Pulp distributions for the Python type.

    """

    class Meta:
        fields = core_serializers.PublicationDistributionSerializer.Meta.fields
        model = python_models.PythonDistribution


class PythonPackageContentSerializer(core_serializers.SingleArtifactContentUploadSerializer):
    """
    A Serializer for PythonPackageContent.
    """

    filename = serializers.CharField(
        help_text=_('The name of the distribution package, usually of the format:'
                    ' {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}'
                    '-{platform tag}.{packagetype}'),
        read_only=True,
    )
    packagetype = serializers.CharField(
        help_text=_('The type of the distribution package '
                    '(e.g. sdist, bdist_wheel, bdist_egg, etc)'),
        read_only=True,
    )
    name = serializers.CharField(
        help_text=_('The name of the python project.'),
        read_only=True,
    )
    version = serializers.CharField(
        help_text=_('The packages version number.'),
        read_only=True,
    )
    metadata_version = serializers.CharField(
        help_text=_('Version of the file format'),
        read_only=True,
    )
    summary = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('A one-line summary of what the package does.')
    )
    description = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('A longer description of the package that can run to several paragraphs.')
    )
    keywords = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('Additional keywords to be used to assist searching for the '
                    'package in a larger catalog.')
    )
    home_page = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('The URL for the package\'s home page.')
    )
    download_url = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('Legacy field denoting the URL from which this package can be downloaded.')
    )
    author = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('Text containing the author\'s name. Contact information can also be added,'
                    ' separated with newlines.')
    )
    author_email = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('The author\'s e-mail address. ')
    )
    maintainer = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('The maintainer\'s name at a minimum; '
                    'additional contact information may be provided.')
    )
    maintainer_email = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('The maintainer\'s e-mail address.')
    )
    license = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('Text indicating the license covering the distribution')
    )
    requires_python = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('The Python version(s) that the distribution is guaranteed to be '
                    'compatible with.')
    )
    project_url = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('A browsable URL for the project and a label for it, separated by a comma.')
    )
    platform = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('A comma-separated list of platform specifications, '
                    'summarizing the operating systems supported by the package.')
    )
    supported_platform = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('Field to specify the OS and CPU for which the binary package was compiled. ')
    )
    requires_dist = serializers.JSONField(
        required=False, default=list,
        help_text=_('A JSON list containing names of some other distutils project '
                    'required by this distribution.')
    )
    provides_dist = serializers.JSONField(
        required=False, default=list,
        help_text=_('A JSON list containing names of a Distutils project which is contained'
                    ' within this distribution.')
    )
    obsoletes_dist = serializers.JSONField(
        required=False, default=list,
        help_text=_('A JSON list containing names of a distutils project\'s distribution which '
                    'this distribution renders obsolete, meaning that the two projects should not '
                    'be installed at the same time.')
    )
    requires_external = serializers.JSONField(
        required=False, default=list,
        help_text=_('A JSON list containing some dependency in the system that the distribution '
                    'is to be used.')
    )
    classifiers = serializers.JSONField(
        required=False, default=list,
        help_text=_('A JSON list containing classification values for a Python package.')
    )

    def deferred_validate(self, data):
        """
        Validate the python package data.

        Args:
            data (dict): Data to be validated

        Returns:
            dict: Data that has been validated

        """
        data = super().deferred_validate(data)

        try:
            filename = data["relative_path"]
        except KeyError:
            raise serializers.ValidationError(detail={"relative_path": _('This field is required')})

        if python_models.PythonPackageContent.objects.filter(filename=filename):
            raise serializers.ValidationError(detail={
                "relative_path": _('This field must be unique')
            })

        # iterate through extensions since splitext does not support things like .tar.gz
        for ext, packagetype in DIST_EXTENSIONS.items():
            if filename.endswith(ext):
                # Copy file to a temp directory under the user provided filename, we do this
                # because pkginfo validates that the filename has a valid extension before
                # reading it
                with tempfile.TemporaryDirectory() as td:
                    temp_path = os.path.join(td, filename)
                    artifact = data["artifact"]
                    shutil.copy2(artifact.file.path, temp_path)
                    metadata = DIST_TYPES[packagetype](temp_path)
                    metadata.packagetype = packagetype
                    break
        else:
            raise serializers.ValidationError(_(
                "Extension on {} is not a valid python extension "
                "(.whl, .exe, .egg, .tar.gz, .tar.bz2, .zip)").format(filename)
            )
        _data = parse_project_metadata(vars(metadata))
        _data['packagetype'] = metadata.packagetype
        _data['version'] = metadata.version
        _data['filename'] = filename

        data.update(_data)

        new_content = python_models.PythonPackageContent.objects.filter(
            filename=data['filename'],
            packagetype=data['packagetype'],
            name=data['name'],
            version=data['version']
        )

        if new_content.exists():
            raise serializers.ValidationError(
                _(
                    "There is already a python package with relative path '{path}'."
                ).format(path=data["relative_path"])
            )

        return data

    class Meta:
        fields = core_serializers.SingleArtifactContentUploadSerializer.Meta.fields + (
            'filename', 'packagetype', 'name', 'version', 'metadata_version', 'summary',
            'description', 'keywords', 'home_page', 'download_url', 'author', 'author_email',
            'maintainer', 'maintainer_email', 'license', 'requires_python', 'project_url',
            'platform', 'supported_platform', 'requires_dist', 'provides_dist',
            'obsoletes_dist', 'requires_external', 'classifiers'
        )
        model = python_models.PythonPackageContent


class MinimalPythonPackageContentSerializer(PythonPackageContentSerializer):
    """
    A Serializer for PythonPackageContent.
    """

    class Meta:
        fields = core_serializers.SingleArtifactContentUploadSerializer.Meta.fields + (
            'filename', 'packagetype', 'name', 'version',
        )
        model = python_models.PythonPackageContent


class PythonRemoteSerializer(core_serializers.RemoteSerializer):
    """
    A Serializer for PythonRemote.
    """

    includes = serializers.JSONField(
        required=False,
        default=list,
        help_text=_(
            "A JSON list containing project specifiers for Python packages to include."
        ),
    )
    excludes = serializers.JSONField(
        required=False,
        default=list,
        help_text=_(
            "A JSON list containing project specifiers for Python packages to exclude."
        ),

    )
    prereleases = serializers.BooleanField(
        required=False,
        help_text=_('Whether or not to include pre-release packages in the sync.')
    )
    policy = serializers.ChoiceField(
        help_text=_("The policy to use when downloading content. The possible values include: "
                    "'immediate', 'on_demand', and 'cache_only'. 'immediate' is the default."),
        choices=core_models.Remote.POLICY_CHOICES,
        default=core_models.Remote.ON_DEMAND
    )

    def validate_includes(self, value):
        """Validates the includes"""
        for pkg in value:
            try:
                Requirement(pkg)
            except ValueError as ve:
                raise serializers.ValidationError(
                    _("includes specifier {} is invalid. {}".format(pkg, ve))
                )
        return value

    def validate_excludes(self, value):
        """Validates the excludes"""
        for pkg in value:
            try:
                Requirement(pkg)
            except ValueError as ve:
                raise serializers.ValidationError(
                    _("excludes specifier {} is invalid. {}".format(pkg, ve))
                )
        return value

    class Meta:
        fields = core_serializers.RemoteSerializer.Meta.fields + (
            "includes", "excludes", "prereleases"
        )
        model = python_models.PythonRemote


class PythonBanderRemoteSerializer(serializers.Serializer):
    """
    A Serializer for the initial step of creating a Python Remote from a Bandersnatch config file
    """

    config = serializers.FileField(
        help_text=_("A Bandersnatch config that may be used to construct a Python Remote."),
        required=True,
        write_only=True,
    )
    name = serializers.CharField(
        help_text=_("A unique name for this remote"),
        required=True,
    )

    policy = serializers.ChoiceField(
        help_text=_("The policy to use when downloading content. The possible values include: "
                    "'immediate', 'on_demand', and 'cache_only'. 'immediate' is the default."),
        choices=core_models.Remote.POLICY_CHOICES,
        default=core_models.Remote.ON_DEMAND
    )


class PythonPublicationSerializer(core_serializers.PublicationSerializer):
    """
    A Serializer for PythonPublication.
    """

    distributions = core_serializers.DetailRelatedField(
        help_text=_('This publication is currently being hosted as configured by these '
                    'distributions.'),
        source="python_pythondistribution",
        view_name="filedistributions-detail",
        many=True,
        read_only=True,
    )

    class Meta:
        fields = core_serializers.PublicationSerializer.Meta.fields + ('distributions',)
        model = python_models.PythonPublication
