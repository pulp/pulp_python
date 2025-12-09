import logging

from rest_framework.viewsets import ViewSet
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.exceptions import NotAcceptable
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from datetime import datetime, timezone, timedelta

from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.utils import DatabaseError
from django.http.response import (
    Http404,
    HttpResponseNotFound,
    HttpResponseForbidden,
    HttpResponseBadRequest,
    StreamingHttpResponse,
    HttpResponse,
)
from drf_spectacular.utils import extend_schema
from dynaconf import settings
from itertools import chain
from packaging.utils import canonicalize_name
from urllib.parse import urljoin, urlparse, urlunsplit
from pathlib import PurePath

from pulpcore.plugin.viewsets import OperationPostponedResponse
from pulpcore.plugin.tasking import dispatch
from pulpcore.plugin.util import get_domain, get_url
from pulp_python.app.models import (
    PythonDistribution,
    PythonPackageContent,
    PythonPublication,
    PackageProvenance,
)
from pulp_python.app.pypi.serializers import (
    SummarySerializer,
    PackageMetadataSerializer,
    PackageUploadSerializer,
    PackageUploadTaskSerializer,
)
from pulp_python.app.utils import (
    write_simple_index,
    write_simple_index_json,
    write_simple_detail,
    write_simple_detail_json,
    python_content_to_json,
    PYPI_LAST_SERIAL,
    PYPI_SERIAL_CONSTANT,
    get_remote_package_filter,
    get_remote_simple_page,
)

from pulp_python.app import tasks

log = logging.getLogger(__name__)

ORIGIN_HOST = settings.CONTENT_ORIGIN if settings.CONTENT_ORIGIN else settings.PYPI_API_HOSTNAME
BASE_CONTENT_URL = urljoin(ORIGIN_HOST, settings.CONTENT_PATH_PREFIX)
BASE_API_URL = urljoin(settings.PYPI_API_HOSTNAME, "pypi/")

PYPI_SIMPLE_V1_HTML = "application/vnd.pypi.simple.v1+html"
PYPI_SIMPLE_V1_JSON = "application/vnd.pypi.simple.v1+json"


class PyPISimpleHTMLRenderer(TemplateHTMLRenderer):
    media_type = PYPI_SIMPLE_V1_HTML


class PyPISimpleJSONRenderer(JSONRenderer):
    media_type = PYPI_SIMPLE_V1_JSON


class PyPIMixin:
    """Mixin to get index specific info."""

    _distro = None

    @property
    def distribution(self):
        if self._distro:
            return self._distro

        path = self.kwargs["path"]
        distro = self.get_distribution(path)
        self._distro = distro
        return distro

    @staticmethod
    def get_distribution(path):
        """Finds the distribution associated with this base_path."""
        distro_qs = PythonDistribution.objects.select_related(
            "repository", "publication", "publication__repository_version", "remote"
        )
        try:
            return distro_qs.get(base_path=path, pulp_domain=get_domain())
        except ObjectDoesNotExist:
            raise Http404(f"No PythonDistribution found for base_path {path}")

    @staticmethod
    def get_repository_version(distribution):
        """Finds the repository version this distribution is serving."""
        pub = distribution.publication
        rep = distribution.repository
        rep_version = distribution.repository_version
        if pub:
            return pub.repository_version or pub.repository.latest_version()
        elif rep:
            return rep.latest_version()
        elif rep_version:
            return rep_version
        else:
            raise Http404("No repository associated with this index")

    @staticmethod
    def get_content(repository_version):
        """Returns queryset of the content in this repository version."""
        return PythonPackageContent.objects.filter(pk__in=repository_version.content)

    @staticmethod
    def get_provenances(repository_version):
        """Returns queryset of the provenance for this repository version."""
        return PackageProvenance.objects.filter(pk__in=repository_version.content)

    def should_redirect(self, repo_version=None):
        """Checks if there is a publication the content app can serve."""
        if self.distribution.publication:
            return True
        rv = repo_version or self.get_repository_version(self.distribution)
        return PythonPublication.objects.filter(repository_version=rv).exists()

    def get_rvc(self):
        """Takes the base_path and returns the repository_version and content."""
        if self.distribution.remote:
            if not self.distribution.repository and not self.distribution.publication:
                return None, None
        repo_ver = self.get_repository_version(self.distribution)
        content = self.get_content(repo_ver)
        return repo_ver, content

    def initial(self, request, *args, **kwargs):
        """Perform common initialization tasks for PyPI endpoints."""
        super().initial(request, *args, **kwargs)
        domain_name = get_domain().name
        if settings.DOMAIN_ENABLED:
            self.base_content_url = urljoin(BASE_CONTENT_URL, f"{domain_name}/")
            self.base_api_url = urljoin(BASE_API_URL, f"{domain_name}/")
        else:
            self.base_content_url = BASE_CONTENT_URL
            self.base_api_url = BASE_API_URL

    @classmethod
    def urlpattern(cls):
        """Mocking NamedModelViewSet behavior to get PyPI APIs to support RBAC access polices."""
        return f"pypi/{cls.endpoint_name}"


class PackageUploadMixin(PyPIMixin):
    """A Mixin to provide package upload support."""

    def upload(self, request, path):
        """
        Upload a package to the index.

        0. Check if the index allows uploaded packages (live-api-enabled)
        1. Check request is in correct format
        2. Check if the package is in the repository already
        3. If present then reject request
        4. Spawn task to add content if no/old session present
        5. Add uploads to current session to group into one task
        """
        if not self.distribution.allow_uploads:
            return HttpResponseForbidden(reason="Index is not allowing uploads")

        repo = self.distribution.repository
        if not repo:
            return HttpResponseBadRequest(reason="Index is not pointing to a repository")

        serializer = PackageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        artifact, filename = serializer.validated_data["content"]
        attestations = serializer.validated_data.get("attestations", None)
        repo_content = self.get_content(self.get_repository_version(self.distribution))
        if repo_content.filter(filename=filename).exists():
            return HttpResponseBadRequest(reason=f"Package {filename} already exists in index")

        if settings.PYTHON_GROUP_UPLOADS:
            return self.upload_package_group(
                repo, artifact, filename, attestations, request.session
            )

        result = dispatch(
            tasks.upload,
            exclusive_resources=[artifact, repo],
            kwargs={
                "artifact_sha256": artifact.sha256,
                "filename": filename,
                "attestations": attestations,
                "repository_pk": str(repo.pk),
            },
        )
        return OperationPostponedResponse(result, request)

    def upload_package_group(self, repo, artifact, filename, attestations, session):
        """Steps 4 & 5, spawns tasks to add packages to index."""
        start_time = datetime.now(tz=timezone.utc) + timedelta(seconds=5)
        task = "updated"
        if not session.get("start"):
            task = self.create_group_upload_task(
                session, repo, artifact, filename, attestations, start_time
            )
        else:
            sq = Session.objects.select_for_update(nowait=True).filter(pk=session.session_key)
            try:
                with transaction.atomic():
                    sq.first()
                    current_start = datetime.fromisoformat(session["start"])
                    if current_start >= datetime.now(tz=timezone.utc):
                        session["artifacts"].append((str(artifact.sha256), filename, attestations))
                        session["start"] = str(start_time)
                        session.modified = False
                        session.save()
                    else:
                        raise DatabaseError
            except DatabaseError:
                session.cycle_key()
                task = self.create_group_upload_task(
                    session, repo, artifact, filename, attestations, start_time
                )
        data = {"session": session.session_key, "task": task, "task_start_time": start_time}
        return Response(data=data)

    def create_group_upload_task(
        self, cur_session, repository, artifact, filename, attestations, start_time
    ):
        """Creates the actual task that adds the packages to the index."""
        cur_session["start"] = str(start_time)
        cur_session["artifacts"] = [(str(artifact.sha256), filename, attestations)]
        cur_session.modified = False
        cur_session.save()
        task = dispatch(
            tasks.upload_group,
            exclusive_resources=[artifact, repository],
            kwargs={
                "session_pk": str(cur_session.session_key),
                "repository_pk": str(repository.pk),
            },
        )
        return get_url(task)


class SimpleView(PackageUploadMixin, ViewSet):
    """View for the PyPI simple API."""

    endpoint_name = "simple"
    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "*",
                "effect": "allow",
            },
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "index_has_repo_perm:python.modify_pythonrepository",
            },
        ],
    }

    def perform_content_negotiation(self, request, force=False):
        """
        Uses standard content negotiation, defaulting to HTML if no acceptable renderer is found.
        """
        try:
            return super().perform_content_negotiation(request, force)
        except NotAcceptable:
            return TemplateHTMLRenderer(), TemplateHTMLRenderer.media_type  # text/html

    def get_renderers(self):
        """
        Uses custom renderers for PyPI Simple API endpoints, defaulting to standard ones.
        """
        if self.action in ["list", "retrieve"]:
            # Ordered by priority if multiple content types are present
            return [TemplateHTMLRenderer(), PyPISimpleHTMLRenderer(), PyPISimpleJSONRenderer()]
        else:
            return [JSONRenderer(), BrowsableAPIRenderer()]

    def get_provenance_url(self, package, version, filename):
        """Gets the provenance url for a package."""
        base_path = self.distribution.base_path
        return urljoin(
            self.base_api_url, f"{base_path}/integrity/{package}/{version}/{filename}/provenance/"
        )

    @extend_schema(summary="Get index simple page")
    def list(self, request, path):
        """Gets the simple api html page for the index."""
        repo_version, content = self.get_rvc()
        if self.should_redirect(repo_version=repo_version):
            return redirect(urljoin(self.base_content_url, f"{path}/simple/"))
        names = content.order_by("name").values_list("name", flat=True).distinct().iterator()
        media_type = request.accepted_renderer.media_type
        headers = {"X-PyPI-Last-Serial": str(PYPI_SERIAL_CONSTANT)}

        if media_type == PYPI_SIMPLE_V1_JSON:
            index_data = write_simple_index_json(names)
            return Response(index_data, headers=headers)
        else:
            index_data = write_simple_index(names, streamed=True)
            kwargs = {"content_type": media_type, "headers": headers}
            return StreamingHttpResponse(index_data, **kwargs)

    def pull_through_package_simple(self, package, path, remote):
        """Gets the package's simple page from remote."""

        def parse_package(release_package):
            parsed = urlparse(release_package.url)
            stripped_url = urlunsplit(chain(parsed[:3], ("", "")))
            redirect_path = f"{path}/{release_package.filename}?redirect={stripped_url}"
            d_url = urljoin(self.base_content_url, redirect_path)
            return {
                "filename": release_package.filename,
                "url": d_url,
                "sha256": release_package.digests.get("sha256", ""),
                "requires_python": release_package.requires_python,
                "metadata_sha256": (release_package.metadata_digests or {}).get("sha256"),
                "size": release_package.size,
                "upload_time": release_package.upload_time,
                "version": release_package.version,
                "provenance": release_package.provenance_url,
            }

        rfilter = get_remote_package_filter(remote)
        if not rfilter.filter_project(package):
            return {}

        page = get_remote_simple_page(package, remote)
        if not page:
            log.info(f"Failed to fetch {package} simple page from {remote.url}")
            return {}
        return {
            p.filename: parse_package(p)
            for p in page.packages
            if rfilter.filter_release(package, p.version)
        }

    @extend_schema(operation_id="pypi_simple_package_read", summary="Get package simple page")
    def retrieve(self, request, path, package):
        """Retrieves the simple api html/json page for a package."""
        media_type = request.accepted_renderer.media_type

        repo_ver, content = self.get_rvc()
        # Should I redirect if the normalized name is different?
        normalized = canonicalize_name(package)
        releases = {}
        if self.distribution.remote:
            releases = self.pull_through_package_simple(normalized, path, self.distribution.remote)
        elif self.should_redirect(repo_version=repo_ver):
            return redirect(urljoin(self.base_content_url, f"{path}/simple/{normalized}/"))
        if content:
            local_packages = content.filter(name__normalize=normalized)
            packages = local_packages.values(
                "filename",
                "sha256",
                "metadata_sha256",
                "requires_python",
                "size",
                "pulp_created",
                "version",
            )
            provenances = PackageProvenance.objects.filter(package__in=local_packages).values_list(
                "package__filename", flat=True
            )
            local_releases = {
                p["filename"]: {
                    **p,
                    "url": urljoin(self.base_content_url, f"{path}/{p['filename']}"),
                    "upload_time": p["pulp_created"],
                    "provenance": (
                        self.get_provenance_url(normalized, p["version"], p["filename"])
                        if p["filename"] in provenances
                        else None
                    ),
                }
                for p in packages
            }
            releases.update(local_releases)
        if not releases:
            return HttpResponseNotFound(f"{normalized} does not exist.")

        media_type = request.accepted_renderer.media_type
        headers = {"X-PyPI-Last-Serial": str(PYPI_SERIAL_CONSTANT)}

        if media_type == PYPI_SIMPLE_V1_JSON:
            detail_data = write_simple_detail_json(normalized, releases.values())
            return Response(detail_data, headers=headers)
        else:
            detail_data = write_simple_detail(normalized, releases.values())
            kwargs = {"content_type": media_type, "headers": headers}
            return HttpResponse(detail_data, **kwargs)

    @extend_schema(
        request=PackageUploadSerializer,
        responses={200: PackageUploadTaskSerializer},
        summary="Upload a package",
    )
    def create(self, request, path):
        """
        Upload package to the index.
        This endpoint has the same functionality as the upload endpoint at the `/legacy` url of the
        index. This is provided for convenience for users who want a single index url for all their
        Python tools. (pip, twine, poetry, pipenv, ...)
        """
        return self.upload(request, path)


class MetadataView(PyPIMixin, ViewSet):
    """View for the PyPI JSON metadata endpoint."""

    endpoint_name = "pypi"
    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["retrieve"],
                "principal": "*",
                "effect": "allow",
            },
        ],
    }

    @extend_schema(
        tags=["Pypi: Metadata"],
        responses={200: PackageMetadataSerializer},
        summary="Get package metadata",
    )
    def retrieve(self, request, path, meta):
        """
        Retrieves the package's core-metadata specified by
        https://packaging.python.org/specifications/core-metadata/.
        `meta` must be a path in form of `{package}/json/` or `{package}/{version}/json/`
        """
        repo_ver, content = self.get_rvc()
        meta_path = PurePath(meta)
        name = None
        version = None
        domain = None
        if meta_path.match("*/*/json"):
            version = meta_path.parts[1]
            name = meta_path.parts[0]
        elif meta_path.match("*/json"):
            name = meta_path.parts[0]
        if name:
            normalized = canonicalize_name(name)
            package_content = content.filter(name__normalize=normalized)
            # TODO Change this value to the Repo's serial value when implemented
            headers = {PYPI_LAST_SERIAL: str(PYPI_SERIAL_CONSTANT)}
            if settings.DOMAIN_ENABLED:
                domain = get_domain()
            json_body = python_content_to_json(
                path, package_content, version=version, domain=domain
            )
            if json_body:
                return Response(data=json_body, headers=headers)
        return Response(status="404")


class PyPIView(PyPIMixin, ViewSet):
    """View for base_url of distribution."""

    endpoint_name = "root"
    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["list", "retrieve"],
                "principal": "*",
                "effect": "allow",
            },
        ],
    }

    @extend_schema(responses={200: SummarySerializer}, summary="Get index summary")
    def retrieve(self, request, path):
        """Gets package summary stats of index."""
        repo_ver, content = self.get_rvc()
        files = content.count()
        releases = content.distinct("name", "version").count()
        projects = content.distinct("name").count()
        data = {"projects": projects, "releases": releases, "files": files}
        return Response(data=data)


class UploadView(PackageUploadMixin, ViewSet):
    """View for the `/legacy` upload endpoint."""

    endpoint_name = "legacy"
    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["create"],
                "principal": "authenticated",
                "effect": "allow",
                "condition": "index_has_repo_perm:python.modify_pythonrepository",
            },
        ],
    }

    @extend_schema(
        request=PackageUploadSerializer,
        responses={200: PackageUploadTaskSerializer},
        summary="Upload a package",
    )
    def create(self, request, path):
        """
        Upload package to the index.

        This is the endpoint that tools like Twine and Poetry use for their upload commands.
        """
        return self.upload(request, path)


class ProvenanceView(PyPIMixin, ViewSet):
    """View for the PyPI provenance endpoint."""

    endpoint_name = "integrity"
    DEFAULT_ACCESS_POLICY = {
        "statements": [
            {
                "action": ["retrieve"],
                "principal": "*",
                "effect": "allow",
            },
        ],
    }

    @extend_schema(summary="Get package provenance")
    def retrieve(self, request, path, package, version, filename):
        """Gets the provenance for a package."""
        repo_ver, content = self.get_rvc()
        if content:
            package_content = content.filter(
                name__normalize=package, version=version, filename=filename
            ).first()
            if package_content:
                provenance = self.get_provenances(repo_ver).filter(package=package_content).first()
                if provenance:
                    return Response(data=provenance.provenance)
        return HttpResponseNotFound(f"{package} {version} {filename} provenance does not exist.")
