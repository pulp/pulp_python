import logging
import os
import tempfile
from gettext import gettext as _
from django.conf import settings
from django.db.utils import IntegrityError
from packaging.requirements import Requirement
from rest_framework import serializers
from pypi_attestations import AttestationError
from pydantic import TypeAdapter, ValidationError

from pulpcore.plugin import models as core_models
from pulpcore.plugin import serializers as core_serializers
from pulpcore.plugin.util import get_domain, get_prn, get_current_authenticated_user

from pulp_python.app import models as python_models
from pulp_python.app.provenance import (
    Attestation,
    Provenance,
    verify_provenance,
    AttestationBundle,
    AnyPublisher,
)
from pulp_python.app.utils import (
    DIST_EXTENSIONS,
    artifact_to_metadata_artifact,
    artifact_to_python_content_data,
    get_project_metadata_from_file,
    parse_project_metadata,
)


log = logging.getLogger(__name__)


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
    repository_version = core_serializers.RepositoryVersionRelatedField(
        required=False, help_text=_("RepositoryVersion to be served."), allow_null=True
    )
    base_url = serializers.SerializerMethodField(read_only=True)
    allow_uploads = serializers.BooleanField(
        default=True, help_text=_("Allow packages to be uploaded to this index.")
    )
    remote = core_serializers.DetailRelatedField(
        required=False,
        help_text=_("Remote that can be used to fetch content when using pull-through caching."),
        view_name_pattern=r"remotes(-.*/.*)?-detail",
        queryset=core_models.Remote.objects.all(),
        allow_null=True,
    )

    def get_base_url(self, obj):
        """Gets the base url."""
        if settings.DOMAIN_ENABLED:
            return f"{settings.PYPI_API_HOSTNAME}/pypi/{get_domain().name}/{obj.base_path}/"
        return f"{settings.PYPI_API_HOSTNAME}/pypi/{obj.base_path}/"

    class Meta:
        fields = core_serializers.DistributionSerializer.Meta.fields + (
            "publication",
            "repository_version",
            "allow_uploads",
            "remote",
        )
        model = python_models.PythonDistribution


class PythonSingleContentArtifactField(core_serializers.SingleContentArtifactField):
    """
    Custom field with overridden get_attribute method. Meant to be used only in
    PythonPackageContentSerializer to handle possible existence of metadata artifact.
    """

    def get_attribute(self, instance):
        # When content has multiple artifacts (wheel + metadata), return the main one
        if instance._artifacts.count() > 1:
            for ca in instance.contentartifact_set.all():
                if not ca.relative_path.endswith(".metadata"):
                    return ca.artifact

        return super().get_attribute(instance)


class PythonPackageContentSerializer(core_serializers.SingleArtifactContentUploadSerializer):
    """
    A Serializer for PythonPackageContent.
    """

    artifact = PythonSingleContentArtifactField(
        help_text=_("Artifact file representing the physical content"),
    )

    # Core metadata
    # Version 1.0
    author = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_(
            "Text containing the author's name. Contact information can also be added,"
            " separated with newlines."
        ),
    )
    author_email = serializers.CharField(
        required=False, allow_blank=True, help_text=_("The author's e-mail address. ")
    )
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("A longer description of the package that can run to several paragraphs."),
    )
    home_page = serializers.CharField(
        required=False, allow_blank=True, help_text=_("The URL for the package's home page.")
    )
    keywords = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_(
            "Additional keywords to be used to assist searching for the "
            "package in a larger catalog."
        ),
    )
    license = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("Text indicating the license covering the distribution"),
    )
    metadata_version = serializers.CharField(
        help_text=_("Version of the file format"),
        read_only=True,
    )
    name = serializers.CharField(
        help_text=_("The name of the python project."),
        read_only=True,
    )
    platform = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_(
            "A comma-separated list of platform specifications, "
            "summarizing the operating systems supported by the package."
        ),
    )
    summary = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("A one-line summary of what the package does."),
    )
    version = serializers.CharField(
        help_text=_("The packages version number."),
        read_only=True,
    )
    # Version 1.1
    classifiers = serializers.JSONField(
        required=False,
        default=list,
        help_text=_("A JSON list containing classification values for a Python package."),
    )
    download_url = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("Legacy field denoting the URL from which this package can be downloaded."),
    )
    supported_platform = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("Field to specify the OS and CPU for which the binary package was compiled. "),
    )
    # Version 1.2
    maintainer = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_(
            "The maintainer's name at a minimum; " "additional contact information may be provided."
        ),
    )
    maintainer_email = serializers.CharField(
        required=False, allow_blank=True, help_text=_("The maintainer's e-mail address.")
    )
    obsoletes_dist = serializers.JSONField(
        required=False,
        default=list,
        help_text=_(
            "A JSON list containing names of a distutils project's distribution which "
            "this distribution renders obsolete, meaning that the two projects should not "
            "be installed at the same time."
        ),
    )
    project_url = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("A browsable URL for the project and a label for it, separated by a comma."),
    )
    project_urls = serializers.JSONField(
        required=False,
        default=dict,
        help_text=_("A dictionary of labels and URLs for the project."),
    )
    provides_dist = serializers.JSONField(
        required=False,
        default=list,
        help_text=_(
            "A JSON list containing names of a Distutils project which is contained"
            " within this distribution."
        ),
    )
    requires_external = serializers.JSONField(
        required=False,
        default=list,
        help_text=_(
            "A JSON list containing some dependency in the system that the distribution "
            "is to be used."
        ),
    )
    requires_dist = serializers.JSONField(
        required=False,
        default=list,
        help_text=_(
            "A JSON list containing names of some other distutils project "
            "required by this distribution."
        ),
    )
    requires_python = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_(
            "The Python version(s) that the distribution is guaranteed to be compatible with."
        ),
    )
    # Version 2.1
    description_content_type = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_(
            "A string stating the markup syntax (if any) used in the distribution's"
            " description, so that tools can intelligently render the description."
        ),
    )
    provides_extras = serializers.JSONField(
        required=False,
        default=list,
        help_text=_("A JSON list containing names of optional features provided by the package."),
    )
    # Version 2.2
    dynamic = serializers.JSONField(
        required=False,
        default=list,
        help_text=_(
            "A JSON list containing names of other core metadata fields which are "
            "permitted to vary between sdist and bdist packages. Fields NOT marked "
            "dynamic MUST be the same between bdist and sdist."
        ),
    )
    # Version 2.4
    license_expression = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text=_("Text string that is a valid SPDX license expression."),
    )
    license_file = serializers.JSONField(
        required=False,
        default=list,
        help_text=_("A JSON list containing names of the paths to license-related files."),
    )
    # Release metadata
    filename = serializers.CharField(
        help_text=_(
            "The name of the distribution package, usually of the format:"
            " {distribution}-{version}(-{build tag})?-{python tag}-{abi tag}"
            "-{platform tag}.{packagetype}"
        ),
        read_only=True,
    )
    packagetype = serializers.CharField(
        help_text=_(
            "The type of the distribution package (e.g. sdist, bdist_wheel, bdist_egg, etc)"
        ),
        read_only=True,
    )
    python_version = serializers.CharField(
        help_text=_(
            "The tag that indicates which Python implementation or version the package requires."
        ),
        read_only=True,
    )
    size = serializers.IntegerField(
        help_text=_("The size of the package in bytes."),
        read_only=True,
    )
    sha256 = serializers.CharField(
        default="",
        help_text=_("The SHA256 digest of this package."),
    )
    metadata_sha256 = serializers.CharField(
        required=False,
        allow_null=True,
        help_text=_("The SHA256 digest of the package's METADATA file."),
    )
    # PEP740 Attestations/Provenance
    attestations = serializers.JSONField(
        required=False,
        help_text=_("A JSON list containing attestations for the package."),
        write_only=True,
    )
    provenance = serializers.SerializerMethodField(
        read_only=True, help_text=_("The created provenance object on upload.")
    )

    def get_provenance(self, obj):
        """Get the provenance for the package."""
        if provenance := getattr(obj, "provenance", None):
            return get_prn(provenance)
        return None

    def validate_attestations(self, value):
        """Validate the attestations, turn into Attestation objects."""
        try:
            if isinstance(value, str):
                attestations = TypeAdapter(list[Attestation]).validate_json(value)
            else:
                attestations = TypeAdapter(list[Attestation]).validate_python(value)
        except ValidationError as e:
            raise serializers.ValidationError(_("Invalid attestations: {}".format(e)))
        return attestations

    def handle_attestations(self, filename, sha256, attestations, offline=False):
        """Handle converting attestations to a Provenance object."""
        user = get_current_authenticated_user()
        publisher = AnyPublisher(kind="Pulp User", prn=get_prn(user))
        att_bundle = AttestationBundle(publisher=publisher, attestations=attestations)
        provenance = Provenance(attestation_bundles=[att_bundle])
        try:
            verify_provenance(filename, sha256, provenance, offline=offline)
        except AttestationError as e:
            raise serializers.ValidationError(
                {"attestations": _("Attestations failed verification: {}".format(e))}
            )
        return provenance.model_dump(mode="json")

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
            raise serializers.ValidationError(detail={"relative_path": _("This field is required")})

        artifact = data["artifact"]
        try:
            _data = artifact_to_python_content_data(filename, artifact, domain=get_domain())
        except ValueError:
            raise serializers.ValidationError(
                _(
                    "Extension on {} is not a valid python extension "
                    "(.whl, .exe, .egg, .tar.gz, .tar.bz2, .zip)"
                ).format(filename)
            )

        if data.get("sha256") and data["sha256"] != artifact.sha256:
            raise serializers.ValidationError(
                detail={
                    "sha256": _(
                        "The uploaded artifact's sha256 checksum does not match the one provided"
                    )
                }
            )

        data.update(_data)
        if attestations := data.pop("attestations", None):
            data["provenance"] = self.handle_attestations(filename, data["sha256"], attestations)

        # Create metadata artifact for wheel files
        if filename.endswith(".whl"):
            if metadata_artifact := artifact_to_metadata_artifact(filename, artifact):
                data["metadata_artifact"] = metadata_artifact
                data["metadata_sha256"] = metadata_artifact.sha256

        return data

    def get_artifacts(self, validated_data):
        artifacts = super().get_artifacts(validated_data)
        if metadata_artifact := validated_data.pop("metadata_artifact", None):
            relative_path = f"{validated_data['filename']}.metadata"
            artifacts[relative_path] = metadata_artifact
        return artifacts

    def retrieve(self, validated_data):
        content = python_models.PythonPackageContent.objects.filter(
            sha256=validated_data["sha256"], _pulp_domain=get_domain()
        )
        return content.first()

    def create(self, validated_data):
        """Create new PythonPackageContent object."""
        repository = validated_data.pop("repository", None)
        provenance = validated_data.pop("provenance", None)
        content = super().create(validated_data)
        if provenance:
            prov_sha256 = python_models.PackageProvenance.calculate_sha256(provenance)
            prov_model, _ = python_models.PackageProvenance.objects.get_or_create(
                sha256=prov_sha256,
                _pulp_domain=get_domain(),
                defaults={"package": content, "provenance": provenance},
            )
            if core_models.Task.current():
                core_models.CreatedResource.objects.create(content_object=prov_model)
            setattr(content, "provenance", prov_model)
        if repository:
            repository.cast()
            content_to_add = [content.pk, content.provenance.pk] if provenance else [content.pk]
            content_to_add = core_models.Content.objects.filter(pk__in=content_to_add)
            with repository.new_version() as new_version:
                new_version.add_content(content_to_add)
        return content

    class Meta:
        fields = core_serializers.SingleArtifactContentUploadSerializer.Meta.fields + (
            "artifact",
            "author",
            "author_email",
            "description",
            "home_page",
            "keywords",
            "license",
            "metadata_version",
            "name",
            "platform",
            "summary",
            "version",
            "classifiers",
            "download_url",
            "supported_platform",
            "maintainer",
            "maintainer_email",
            "obsoletes_dist",
            "project_url",
            "project_urls",
            "provides_dist",
            "requires_external",
            "requires_dist",
            "requires_python",
            "description_content_type",
            "provides_extras",
            "dynamic",
            "license_expression",
            "license_file",
            "filename",
            "packagetype",
            "python_version",
            "size",
            "sha256",
            "metadata_sha256",
            "attestations",
            "provenance",
        )
        model = python_models.PythonPackageContent


class PythonPackageContentUploadSerializer(PythonPackageContentSerializer):
    """
    A serializer for requests to synchronously upload Python packages.
    """

    def validate(self, data):
        """
        Validates an uploaded Python package file, extracts its metadata,
        and creates or retrieves an associated Artifact.

        Returns updated data with artifact and metadata details.
        """
        file = data.pop("file")
        filename = file.name

        for ext, packagetype in DIST_EXTENSIONS.items():
            if filename.endswith(ext):
                break
        else:
            raise serializers.ValidationError(
                _(
                    "Extension on {} is not a valid python extension "
                    "(.whl, .exe, .egg, .tar.gz, .tar.bz2, .zip)"
                ).format(filename)
            )

        # Replace the incorrect file name in the file path with the original file name
        original_filepath = file.file.name
        path_to_file, tmp_str = original_filepath.rsplit("/", maxsplit=1)
        tmp_str = tmp_str.split(".", maxsplit=1)[0]  # Remove e.g. ".upload.gz" suffix
        new_filepath = f"{path_to_file}/{tmp_str}{filename}"
        os.rename(original_filepath, new_filepath)

        metadata = get_project_metadata_from_file(new_filepath)
        artifact = core_models.Artifact.init_and_validate(new_filepath)
        try:
            artifact.save()
        except IntegrityError:
            artifact = core_models.Artifact.objects.get(
                sha256=artifact.sha256, pulp_domain=get_domain()
            )
            artifact.touch()
            log.info(f"Artifact for {file.name} already existed in database")

        data["artifact"] = artifact
        data["sha256"] = artifact.sha256
        data["relative_path"] = filename
        data["size"] = artifact.size
        data.update(parse_project_metadata(vars(metadata)))
        # Overwrite filename from metadata
        data["filename"] = filename
        if attestations := data.pop("attestations", None):
            data["provenance"] = self.handle_attestations(
                filename, data["sha256"], attestations, offline=True
            )
        # Create metadata artifact for wheel files
        if filename.endswith(".whl"):
            with tempfile.TemporaryDirectory(dir=settings.WORKING_DIRECTORY) as temp_dir:
                if metadata_artifact := artifact_to_metadata_artifact(
                    filename, artifact, tmp_dir=temp_dir
                ):
                    data["metadata_artifact"] = metadata_artifact
                    data["metadata_sha256"] = metadata_artifact.sha256

        return data

    class Meta(PythonPackageContentSerializer.Meta):
        # This API does not support uploading to a repository or using a custom relative_path
        fields = tuple(
            f
            for f in PythonPackageContentSerializer.Meta.fields
            if f not in ["repository", "relative_path"]
        )
        model = python_models.PythonPackageContent
        # Name used for the OpenAPI request object
        ref_name = "PythonPackageContentUpload"


class MinimalPythonPackageContentSerializer(PythonPackageContentSerializer):
    """
    A Serializer for PythonPackageContent.
    """

    class Meta:
        fields = core_serializers.SingleArtifactContentUploadSerializer.Meta.fields + (
            "filename",
            "packagetype",
            "name",
            "version",
            "sha256",
        )
        model = python_models.PythonPackageContent


class PackageProvenanceSerializer(core_serializers.NoArtifactContentUploadSerializer):
    """
    A Serializer for PackageProvenance.
    """

    package = core_serializers.DetailRelatedField(
        help_text=_("The package that the provenance is for."),
        view_name_pattern=r"content(-.*/.*)-detail",
        queryset=python_models.PythonPackageContent.objects.all(),
    )
    provenance = serializers.JSONField(read_only=True, default=dict)
    sha256 = serializers.CharField(read_only=True)
    verify = serializers.BooleanField(
        default=True,
        write_only=True,
        help_text=_("Verify each attestation in the provenance."),
    )

    def deferred_validate(self, data):
        """
        Validate that the provenance is valid and pointing to the correct package.
        """
        data = super().deferred_validate(data)
        try:
            provenance = Provenance.model_validate_json(data["file"].read())
            data["provenance"] = provenance.model_dump(mode="json")
        except ValidationError as e:
            raise serializers.ValidationError(
                _("The uploaded provenance is not valid: {}".format(e))
            )
        if data.pop("verify"):
            try:
                verify_provenance(data["package"].filename, data["package"].sha256, provenance)
            except AttestationError as e:
                raise serializers.ValidationError(_("Provenance verification failed: {}".format(e)))
        return data

    def retrieve(self, validated_data):
        sha256 = python_models.PackageProvenance.calculate_sha256(validated_data["provenance"])
        content = python_models.PackageProvenance.objects.filter(
            sha256=sha256, _pulp_domain=get_domain()
        ).first()
        return content

    class Meta:
        fields = core_serializers.NoArtifactContentUploadSerializer.Meta.fields + (
            "package",
            "provenance",
            "sha256",
            "verify",
        )
        model = python_models.PackageProvenance


class MultipleChoiceArrayField(serializers.MultipleChoiceField):
    """
    A wrapper to make sure this DRF serializer works properly with ArrayFields.
    """

    def to_internal_value(self, data):
        """Converts set to list."""
        return list(super().to_internal_value(data))

    def to_representation(self, value):
        """Converts set to list for JSON serialization."""
        result = super().to_representation(value)
        if isinstance(result, set):
            result = list(result)
        return result


class PythonRemoteSerializer(core_serializers.RemoteSerializer):
    """
    A Serializer for PythonRemote.
    """

    includes = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        help_text=_("A list containing project specifiers for Python packages to include."),
    )
    excludes = serializers.ListField(
        child=serializers.CharField(allow_blank=False),
        required=False,
        allow_empty=True,
        help_text=_("A list containing project specifiers for Python packages to exclude."),
    )
    prereleases = serializers.BooleanField(
        required=False, help_text=_("Whether or not to include pre-release packages in the sync.")
    )
    policy = serializers.ChoiceField(
        help_text=_(
            "The policy to use when downloading content. The possible values include: "
            "'immediate', 'on_demand', and 'streamed'. 'on_demand' is the default."
        ),
        choices=core_models.Remote.POLICY_CHOICES,
        default=core_models.Remote.ON_DEMAND,
    )
    package_types = MultipleChoiceArrayField(
        required=False,
        help_text=_(
            "The package types to sync for Python content. Leave blank to get every" "package type."
        ),
        choices=python_models.PACKAGE_TYPES,
        default=list,
    )
    keep_latest_packages = serializers.IntegerField(
        required=False,
        help_text=_(
            "The amount of latest versions of a package to keep on sync, includes"
            "pre-releases if synced. Default 0 keeps all versions."
        ),
        default=0,
    )
    exclude_platforms = MultipleChoiceArrayField(
        required=False,
        help_text=_(
            "List of platforms to exclude syncing Python packages for. Possible values"
            "include: windows, macos, freebsd, and linux."
        ),
        choices=python_models.PLATFORMS,
        default=list,
    )
    provenance = serializers.BooleanField(
        required=False,
        help_text=_("Whether to sync available provenances for Python packages."),
        default=False,
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
            "includes",
            "excludes",
            "prereleases",
            "package_types",
            "keep_latest_packages",
            "exclude_platforms",
            "provenance",
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
        help_text=_(
            "The policy to use when downloading content. The possible values include: "
            "'immediate', 'on_demand', and 'streamed'. 'on_demand' is the default."
        ),
        choices=core_models.Remote.POLICY_CHOICES,
        default=core_models.Remote.ON_DEMAND,
    )


class PythonPublicationSerializer(core_serializers.PublicationSerializer):
    """
    A Serializer for PythonPublication.
    """

    distributions = core_serializers.DetailRelatedField(
        help_text=_(
            "This publication is currently being hosted as configured by these distributions."
        ),
        source="distribution_set",
        view_name="pythondistributions-detail",
        many=True,
        read_only=True,
    )

    class Meta:
        fields = core_serializers.PublicationSerializer.Meta.fields + ("distributions",)
        model = python_models.PythonPublication
