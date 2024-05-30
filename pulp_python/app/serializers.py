from gettext import gettext as _
from django.conf import settings
from packaging.requirements import Requirement
from rest_framework import serializers

from pulpcore.plugin import models as core_models
from pulpcore.plugin import serializers as core_serializers
from pulpcore.plugin.util import get_domain

from pulp_python.app import models as python_models
from pulp_python.app.utils import get_project_metadata_from_artifact, parse_project_metadata


class PythonRepositorySerializer(core_serializers.RepositorySerializer):
    """
    Serializer for Python Repositories.
    """

    autopublish = serializers.BooleanField(
        help_text=_(
            "Whether to automatically create publications for new repository versions, "
            "and update any distributions pointing to this repository."
        ),
        default=False,
        required=False,
    )

    class Meta:
        fields = core_serializers.RepositorySerializer.Meta.fields + ("autopublish",)
        model = python_models.PythonRepository


class PythonDistributionSerializer(core_serializers.DistributionSerializer):
    """
    Serializer for Pulp distributions for the Python type.
    """

    publication = core_serializers.DetailRelatedField(
        required=False,
        help_text=_("Publication to be served"),
        view_name_pattern=r"publications(-.*/.*)?-detail",
        queryset=core_models.Publication.objects.exclude(complete=False),
        allow_null=True,
    )
    base_url = serializers.SerializerMethodField(read_only=True)
    allow_uploads = serializers.BooleanField(
        default=True,
        help_text=_("Allow packages to be uploaded to this index.")
    )
    remote = core_serializers.DetailRelatedField(
        required=False,
        help_text=_('Remote that can be used to fetch content when using pull-through caching.'),
        view_name_pattern=r"remotes(-.*/.*)?-detail",
        queryset=core_models.Remote.objects.all(),
        allow_null=True
    )

    def get_base_url(self, obj):
        """Gets the base url."""
        if settings.DOMAIN_ENABLED:
            return f"{settings.PYPI_API_HOSTNAME}/pypi/{get_domain().name}/{obj.base_path}/"
        return f"{settings.PYPI_API_HOSTNAME}/pypi/{obj.base_path}/"

    class Meta:
        fields = core_serializers.DistributionSerializer.Meta.fields + (
            'publication', "allow_uploads", "remote"
        )
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
    sha256 = serializers.CharField(
        default='',
        help_text=_('The SHA256 digest of this package.'),
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
    description_content_type = serializers.CharField(
        required=False, allow_blank=True,
        help_text=_('A string stating the markup syntax (if any) used in the distribution’s'
                    ' description, so that tools can intelligently render the description.')
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
    project_urls = serializers.JSONField(
        required=False, default=dict,
        help_text=_('A dictionary of labels and URLs for the project.')
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

        artifact = data["artifact"]
        try:
            metadata = get_project_metadata_from_artifact(filename, artifact)
        except ValueError:
            raise serializers.ValidationError(_(
                "Extension on {} is not a valid python extension "
                "(.whl, .exe, .egg, .tar.gz, .tar.bz2, .zip)").format(filename)
            )

        if data.get("sha256") and data["sha256"] != artifact.sha256:
            raise serializers.ValidationError(
                detail={"sha256": _(
                    "The uploaded artifact's sha256 checksum does not match the one provided"
                )}
            )

        _data = parse_project_metadata(vars(metadata))
        _data['packagetype'] = metadata.packagetype
        _data['version'] = metadata.version
        _data['filename'] = filename
        _data['sha256'] = artifact.sha256
        data["pulp_domain_id"] = artifact.pulp_domain_id
        data["_pulp_domain_id"] = artifact.pulp_domain_id

        data.update(_data)

        return data

    def retrieve(self, validated_data):
        content = python_models.PythonPackageContent.objects.filter(
            sha256=validated_data["sha256"], _pulp_domain=get_domain()
        )
        return content.first()

    class Meta:
        fields = core_serializers.SingleArtifactContentUploadSerializer.Meta.fields + (
            'filename', 'packagetype', 'name', 'version', 'sha256', 'metadata_version', 'summary',
            'description', 'description_content_type', 'keywords', 'home_page', 'download_url',
            'author', 'author_email', 'maintainer', 'maintainer_email', 'license',
            'requires_python', 'project_url', 'project_urls', 'platform', 'supported_platform',
            'requires_dist', 'provides_dist', 'obsoletes_dist', 'requires_external', 'classifiers'
        )
        model = python_models.PythonPackageContent


class MinimalPythonPackageContentSerializer(PythonPackageContentSerializer):
    """
    A Serializer for PythonPackageContent.
    """

    class Meta:
        fields = core_serializers.SingleArtifactContentUploadSerializer.Meta.fields + (
            'filename', 'packagetype', 'name', 'version', 'sha256',
        )
        model = python_models.PythonPackageContent


class MultipleChoiceArrayField(serializers.MultipleChoiceField):
    """
    A wrapper to make sure this DRF serializer works properly with ArrayFields.
    """

    def to_internal_value(self, data):
        """Converts set to list."""
        return list(super().to_internal_value(data))


class PythonRemoteSerializer(core_serializers.RemoteSerializer):
    """
    A Serializer for PythonRemote.
    """

    includes = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        help_text=_(
            "A list containing project specifiers for Python packages to include."
        ),
    )
    excludes = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        help_text=_(
            "A list containing project specifiers for Python packages to exclude."
        ),
    )
    prereleases = serializers.BooleanField(
        required=False,
        help_text=_('Whether or not to include pre-release packages in the sync.')
    )
    policy = serializers.ChoiceField(
        help_text=_("The policy to use when downloading content. The possible values include: "
                    "'immediate', 'on_demand', and 'streamed'. 'on_demand' is the default."),
        choices=core_models.Remote.POLICY_CHOICES,
        default=core_models.Remote.ON_DEMAND
    )
    package_types = MultipleChoiceArrayField(
        required=False,
        help_text=_("The package types to sync for Python content. Leave blank to get every"
                    "package type."),
        choices=python_models.PACKAGE_TYPES,
        default=list
    )
    keep_latest_packages = serializers.IntegerField(
        required=False,
        help_text=_("The amount of latest versions of a package to keep on sync, includes"
                    "pre-releases if synced. Default 0 keeps all versions."),
        default=0
    )
    exclude_platforms = MultipleChoiceArrayField(
        required=False,
        help_text=_("List of platforms to exclude syncing Python packages for. Possible values"
                    "include: windows, macos, freebsd, and linux."),
        choices=python_models.PLATFORMS,
        default=list
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
            "includes", "excludes", "prereleases", "package_types", "keep_latest_packages",
            "exclude_platforms",
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
                    "'immediate', 'on_demand', and 'streamed'. 'on_demand' is the default."),
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
        source="distribution_set",
        view_name="pythondistributions-detail",
        many=True,
        read_only=True,
    )

    class Meta:
        fields = core_serializers.PublicationSerializer.Meta.fields + ('distributions',)
        model = python_models.PythonPublication
