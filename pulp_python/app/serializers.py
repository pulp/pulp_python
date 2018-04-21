from gettext import gettext as _

from rest_framework import serializers
from pulpcore.plugin import serializers as platform

from pulp_python.app import models as python_models


class ClassifierSerializer(serializers.ModelSerializer):
    """
    A serializer for Python Classifiers
    """

    name = serializers.CharField(
        help_text=_("A string giving a single classification value for a Python package.")
    )

    class Meta:
        model = python_models.Classifier
        fields = ('name',)


class PythonPackageContentSerializer(platform.ContentSerializer):
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
        help_text=_('A list of additional keywords to be used to assist searching for the '
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
    classifiers = ClassifierSerializer(
        required=False,
        many=True
    )

    def create(self, validated_data):
        """
        Creates a PythonPackageContent

        Overriding default create() to write the classifiers nested field
        :param validated_data:
        :return:
        """
        classifiers = validated_data.pop('classifiers')
        PythonPackageContent = python_models.PythonPackageContent.objects.create(**validated_data)
        for classifier in classifiers:
            python_models.Classifier.objects.create(python_package_content=PythonPackageContent,
                                                    **classifier)
        return PythonPackageContent

    class Meta:
        fields = platform.ContentSerializer.Meta.fields + (
            'filename', 'packagetype', 'name', 'version', 'metadata_version', 'summary',
            'description', 'keywords', 'home_page', 'download_url', 'author', 'author_email',
            'maintainer', 'maintainer_email', 'license', 'requires_python', 'project_url',
            'platform', 'supported_platform', 'requires_dist', 'provides_dist',
            'obsoletes_dist', 'requires_external', 'classifiers'
        )
        model = python_models.PythonPackageContent


class PythonRemoteSerializer(platform.RemoteSerializer):
    """
    A Serializer for PythonRemote.
    """

    projects = serializers.JSONField(
        required=True,
        help_text=_('A JSON list of project names to sync.')
    )

    class Meta:
        fields = platform.RemoteSerializer.Meta.fields + ('projects',)
        model = python_models.PythonRemote


class PythonPublisherSerializer(platform.PublisherSerializer):
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
        fields = platform.PublisherSerializer.Meta.fields
        model = python_models.PythonPublisher
