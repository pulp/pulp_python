# Generated manually on 2025-12-15 14:00 for creating missing metadata artifacts

from django.db import migrations

BATCH_SIZE = 1000


def pulp_hashlib_new(name, *args, **kwargs):
    """
    Copied and updated (to comply with migrations) from pulpcore.
    """
    import hashlib as the_real_hashlib
    from django.conf import settings

    if name not in settings.ALLOWED_CONTENT_CHECKSUMS:
        return None

    return the_real_hashlib.new(name, *args, **kwargs)


def init_and_validate(file, artifact_model, expected_digests):
    """
    Copied and updated (to comply with migrations) from pulpcore.
    """
    from django.conf import settings

    digest_fields = []
    for alg in ("sha512", "sha384", "sha256", "sha224", "sha1", "md5"):
        if alg in settings.ALLOWED_CONTENT_CHECKSUMS:
            digest_fields.append(alg)

    if isinstance(file, str):
        with open(file, "rb") as f:
            hashers = {
                n: hasher for n in digest_fields if (hasher := pulp_hashlib_new(n)) is not None
            }
            if not hashers:
                return None

            size = 0
            while True:
                chunk = f.read(1048576)  # 1 megabyte
                if not chunk:
                    break
                for algorithm in hashers.values():
                    algorithm.update(chunk)
                size = size + len(chunk)
    else:
        size = file.size
        hashers = file.hashers

    mismatched_sha256 = None
    for algorithm, expected_digest in expected_digests.items():
        if algorithm not in hashers:
            return None
        actual_digest = hashers[algorithm].hexdigest()
        if expected_digest != actual_digest:
            # Store the actual value for later fixing if it differs from the package value
            mismatched_sha256 = actual_digest

    attributes = {"size": size, "file": file}
    for algorithm in digest_fields:
        attributes[algorithm] = hashers[algorithm].hexdigest()

    return artifact_model(**attributes), mismatched_sha256


def extract_wheel_metadata(filename):
    """
    Extract the metadata file content from a wheel file.
    Return the raw metadata content as bytes or None if metadata cannot be extracted.
    """
    import zipfile

    try:
        with zipfile.ZipFile(filename, "r") as f:
            for file_path in f.namelist():
                if file_path.endswith(".dist-info/METADATA"):
                    return f.read(file_path)
    except (zipfile.BadZipFile, KeyError, OSError):
        pass
    return None


def artifact_to_metadata_artifact(filename, artifact, md_digests, tmp_dir, artifact_model):
    """
    Create artifact for metadata from the provided wheel artifact.
    Return (artifact, mismatched_sha256) on success, None on any failure.
    """
    import shutil
    import tempfile

    with tempfile.NamedTemporaryFile("wb", dir=tmp_dir, suffix=filename, delete=False) as temp_file:
        temp_wheel_path = temp_file.name
        artifact.file.seek(0)
        shutil.copyfileobj(artifact.file, temp_file)
        temp_file.flush()

    metadata_content = extract_wheel_metadata(temp_wheel_path)
    if not metadata_content:
        return None

    with tempfile.NamedTemporaryFile(
        "wb", dir=tmp_dir, suffix=".metadata", delete=False
    ) as temp_md:
        temp_metadata_path = temp_md.name
        temp_md.write(metadata_content)
        temp_md.flush()

    return init_and_validate(temp_metadata_path, artifact_model, md_digests)


def create_missing_metadata_artifacts(apps, schema_editor):
    """
    Create metadata artifacts for PythonPackageContent instances that have metadata_sha256
    but are missing the corresponding metadata artifact.
    """
    import tempfile
    from django.conf import settings
    from django.db import models

    PythonPackageContent = apps.get_model("python", "PythonPackageContent")
    ContentArtifact = apps.get_model("core", "ContentArtifact")
    Artifact = apps.get_model("core", "Artifact")

    packages = (
        PythonPackageContent.objects.filter(
            metadata_sha256__isnull=False,
            filename__endswith=".whl",
            contentartifact__artifact__isnull=False,
            contentartifact__relative_path=models.F("filename"),
        )
        .exclude(metadata_sha256="")
        .prefetch_related("_artifacts")
        .only("filename", "metadata_sha256")
    )
    artifact_batch = []
    contentartifact_batch = []
    packages_batch = []

    with tempfile.TemporaryDirectory(dir=settings.WORKING_DIRECTORY) as temp_dir:
        for package in packages:
            # Get the main artifact for package
            main_artifact = package._artifacts.get()

            filename = package.filename
            metadata_digests = {"sha256": package.metadata_sha256}
            result = artifact_to_metadata_artifact(
                filename, main_artifact, metadata_digests, temp_dir, Artifact
            )
            if result is None:
                # Unset metadata_sha256 when extraction or validation fails
                package.metadata_sha256 = None
                packages_batch.append(package)
                continue
            metadata_artifact, mismatched_sha256 = result
            if mismatched_sha256:
                # Fix the package if its metadata_sha256 differs from the actual value
                package.metadata_sha256 = mismatched_sha256
                packages_batch.append(package)

            contentartifact = ContentArtifact(
                artifact=metadata_artifact,
                content=package,
                relative_path=f"{filename}.metadata",
            )
            artifact_batch.append(metadata_artifact)
            contentartifact_batch.append(contentartifact)

            if len(artifact_batch) == BATCH_SIZE:
                Artifact.objects.bulk_create(artifact_batch, batch_size=BATCH_SIZE)
                ContentArtifact.objects.bulk_create(contentartifact_batch, batch_size=BATCH_SIZE)
                artifact_batch.clear()
                contentartifact_batch.clear()
            if len(packages_batch) == BATCH_SIZE:
                PythonPackageContent.objects.bulk_update(
                    packages_batch, ["metadata_sha256"], batch_size=BATCH_SIZE
                )
                packages_batch.clear()

        if artifact_batch:
            Artifact.objects.bulk_create(artifact_batch, batch_size=BATCH_SIZE)
            ContentArtifact.objects.bulk_create(contentartifact_batch, batch_size=BATCH_SIZE)
        if packages_batch:
            PythonPackageContent.objects.bulk_update(
                packages_batch, ["metadata_sha256"], batch_size=BATCH_SIZE
            )


class Migration(migrations.Migration):

    dependencies = [
        ("python", "0018_packageprovenance"),
    ]

    operations = [
        migrations.RunPython(
            create_missing_metadata_artifacts,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
