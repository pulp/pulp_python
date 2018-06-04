from gettext import gettext as _

from django.db import transaction
from packaging import specifiers
from rest_framework import serializers

from pulpcore.plugin import models as core_models
from pulpcore.plugin import serializers as core_serializers

from pulp_python.app import models as python_models


class ClassifierSerializer(serializers.ModelSerializer):
    """
    A serializer for Python Classifiers.
    """

    name = serializers.CharField(
        help_text=_("A string giving a single classification value for a Python package.")
    )

    class Meta:
        model = python_models.Classifier
        fields = ('name',)


class DistributionDigestSerializer(serializers.ModelSerializer):
    """
    A serializer for the Distribution Digest in a Project Specifier.
    """

    type = serializers.CharField(
        help_text=_("A type of digest: i.e. sha256, md5")
    )
    digest = serializers.CharField(
        help_text=_("The digest of the distribution")
    )

    class Meta:
        model = python_models.DistributionDigest
        fields = ('type', 'digest')


class ProjectSpecifierSerializer(serializers.ModelSerializer):
    """
    A serializer for Python project specifiers.
    """

    name = serializers.CharField(
        help_text=_("A python project name.")
    )
    version_specifier = serializers.CharField(
        help_text=_(
            "A version specifier, accepts standard python versions syntax:"
            " >=, <=, ==, ~=, >, <, ! can be used in conjunction with other specifiers i.e."
            " >1,<=3,!=3.0.2. Note that the specifiers treat pre-released versions as < released"
            " versions, so 3.0.0a1 < 3.0.0. Not setting the version_specifier will sync all the "
            "pre-released and released versions."),
        required=False,
        allow_blank=True
    )
    digests = DistributionDigestSerializer(
        required=False,
        many=True
    )

    def validate_version_specifier(self, value):
        """
        Check that the Version Specifier is valid.
        """
        try:
            specifiers.SpecifierSet(value)
        except specifiers.InvalidSpecifier as err:
            raise serializers.ValidationError(err)
        return value

    class Meta:
        model = python_models.ProjectSpecifier
        fields = ('name', 'version_specifier', 'digests')


class PythonPackageContentSerializer(core_serializers.ContentSerializer):
    """
    A Serializer for PythonPackageContent.
    """

    filename = serializers.CharField(
        help_text=_('The name of the distribution package, usually of the format:'
                    ' {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}'
                    '-{platform tag}.{packagetype}')
    )
    packagetype = serializers.CharField(
        help_text=_('The type of the distribution package '
                    '(e.g. sdist, bdist_wheel, bdist_egg, etc)')
    )
    name = serializers.CharField(
        help_text=_('The name of the python project.')
    )
    version = serializers.CharField(
        help_text=_('The packages version number.')
    )
    metadata_version = serializers.CharField(
        help_text=_('Version of the file format')
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
    requires_dist = serializers.CharField(
        required=False, default="[]",
        help_text=_('A JSON list containing names of some other distutils project '
                    'required by this distribution.')
    )
    provides_dist = serializers.CharField(
        required=False, default="[]",
        help_text=_('A JSON list containing names of a Distutils project which is contained'
                    ' within this distribution.')
    )
    obsoletes_dist = serializers.CharField(
        required=False, default="[]",
        help_text=_('A JSON list containing names of a distutils project\'s distribution which '
                    'this distribution renders obsolete, meaning that the two projects should not '
                    'be installed at the same time.')
    )
    requires_external = serializers.CharField(
        required=False, default="[]",
        help_text=_('A JSON list containing some dependency in the system that the distribution '
                    'is to be used.')
    )
    classifiers = ClassifierSerializer(
        required=False,
        many=True
    )

    artifact = serializers.HyperlinkedRelatedField(
        view_name='artifacts-detail',
        help_text="Artifact file representing the physical content",
        queryset=core_models.Artifact.objects.all()
    )

    def create(self, validated_data):
        """
        Create a PythonPackageContent.

        Overriding default create() to write the classifiers nested field

        Args:
            validated_data (dict): Data used to create the PythonPackageContent

        Returns:
            models.PythonPackageContent: The created PythonPackageContent

        """
        classifiers = validated_data.pop('classifiers')
        artifact = validated_data.pop('artifact')

        PythonPackageContent = python_models.PythonPackageContent.objects.create(**validated_data)
        for classifier in classifiers:
            python_models.Classifier.objects.create(python_package_content=PythonPackageContent,
                                                    **classifier)
        ca = core_models.ContentArtifact(artifact=artifact,
                                         content=PythonPackageContent,
                                         relative_path=validated_data['filename'])
        ca.save()

        return PythonPackageContent

    class Meta:
        fields = (
            '_href', 'created', 'type',
            'filename', 'packagetype', 'name', 'version', 'metadata_version', 'summary',
            'description', 'keywords', 'home_page', 'download_url', 'author', 'author_email',
            'maintainer', 'maintainer_email', 'license', 'requires_python', 'project_url',
            'platform', 'supported_platform', 'requires_dist', 'provides_dist',
            'obsoletes_dist', 'requires_external', 'classifiers', 'artifact'
        )
        model = python_models.PythonPackageContent


class PythonRemoteSerializer(core_serializers.RemoteSerializer):
    """
    A Serializer for PythonRemote.
    """

    projects = ProjectSpecifierSerializer(
        required=False,
        many=True
    )

    class Meta:
        fields = core_serializers.RemoteSerializer.Meta.fields + ('projects',)
        model = python_models.PythonRemote

    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Update a PythonRemote.

        Overriding default update() to write the projects nested field

        Args:
            instance (models.PythonRemote): instance of the python remote to update
            validated_data (dict): of validated data to update

        Returns:
            models.PythonRemote: the updated PythonRemote

        """
        projects = validated_data.pop('projects', [])

        python_remote = python_models.PythonRemote.objects.get(pk=instance.pk)

        # Remove all project specifier related by foreign key to the remote if it is not a
        # partial update or if new projects list has been passed
        if not self.partial or projects:
            python_models.ProjectSpecifier.objects.filter(remote=python_remote).delete()

        for project in projects:
            digests = project.pop('digests', [])
            specifier = python_models.ProjectSpecifier.objects.create(remote=python_remote,
                                                                      **project)
            for digest in digests:
                python_models.DistributionDigest.objects.create(project_specifier=specifier,
                                                                **digest)

        return super().update(instance, validated_data)

    @transaction.atomic
    def create(self, validated_data):
        """
        Create a PythonRemote.

        Overriding default create() to write the projects nested field, and the nested digest field

        Args:
            validated_data (dict): data used to create the remote

        Returns:
            models.PythonRemote: the created PythonRemote

        """
        projects = validated_data.pop('projects', [])

        python_remote = python_models.PythonRemote.objects.create(**validated_data)
        for project in projects:
            digests = project.pop('digests', None)
            specifier = python_models.ProjectSpecifier.objects.create(remote=python_remote,
                                                                      **project)
            if digests:
                for digest in digests:
                    python_models.DistributionDigest.objects.create(project_specifier=specifier,
                                                                    **digest)

        return python_remote


class PythonPublisherSerializer(core_serializers.PublisherSerializer):
    """
    A Serializer for PythonPublisher.

    Add any new fields if defined on PythonPublisher.
    Similar to the example above, in PythonContentSerializer.
    Additional validators can be added to the parent validators list

    For example::

    class Meta:
        validators = platform.PublisherSerializer.Meta.validators + [myValidator1, myValidator2]
    """

    class Meta:
        fields = core_serializers.PublisherSerializer.Meta.fields
        model = python_models.PythonPublisher
