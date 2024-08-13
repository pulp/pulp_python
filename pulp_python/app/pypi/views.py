import logging
import requests

from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect
from datetime import datetime, timezone, timedelta

from rest_framework.reverse import reverse
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.utils import DatabaseError
from django.http.response import (
    Http404,
    HttpResponseForbidden,
    HttpResponseBadRequest,
    StreamingHttpResponse
)
from drf_spectacular.utils import extend_schema
from dynaconf import settings
from itertools import chain
from packaging.utils import canonicalize_name
from urllib.parse import urljoin, urlparse, urlunsplit
from pathlib import PurePath
from pypi_simple.parse_stream import parse_links_stream_response

from pulpcore.plugin.tasking import dispatch
from pulp_python.app.models import (
    PythonDistribution,
    PythonPackageContent,
    PythonPublication,
)
from pulp_python.app.pypi.serializers import (
    SummarySerializer,
    PackageMetadataSerializer,
    PackageUploadSerializer,
    PackageUploadTaskSerializer
)
from pulp_python.app.utils import (
    write_simple_index,
    write_simple_detail,
    python_content_to_json,
    PYPI_LAST_SERIAL,
    PYPI_SERIAL_CONSTANT,
)

from pulp_python.app import tasks

log = logging.getLogger(__name__)

BASE_CONTENT_URL = urljoin(settings.CONTENT_ORIGIN, settings.CONTENT_PATH_PREFIX)


class PyPIMixin:
    """Mixin to get index specific info."""

    @staticmethod
    def get_repository_version(distribution):
        """Finds the repository version this distribution is serving."""
        pub = distribution.publication
        rep = distribution.repository
        if pub:
            return pub.repository_version or pub.repository.latest_version()
        elif rep:
            return rep.latest_version()
        else:
            raise Http404("No repository associated with this index")

    @staticmethod
    def get_distribution(path):
        """Finds the distribution associated with this base_path."""
        distro_qs = PythonDistribution.objects.select_related(
            "repository", "publication", "publication__repository_version", "remote"
        )
        try:
            return distro_qs.get(base_path=path)
        except ObjectDoesNotExist:
            raise Http404(f"No PythonDistribution found for base_path {path}")

    @staticmethod
    def get_content(repository_version):
        """Returns queryset of the content in this repository version."""
        return PythonPackageContent.objects.filter(pk__in=repository_version.content)

    def should_redirect(self, distro, repo_version=None):
        """Checks if there is a publication the content app can serve."""
        if distro.publication:
            return True
        rv = repo_version or self.get_repository_version(distro)
        return PythonPublication.objects.filter(repository_version=rv).exists()

    def get_drvc(self, path):
        """Takes the base_path and returns the distribution, repository_version and content."""
        distro = self.get_distribution(path)
        if distro.remote and not distro.repository and not distro.publication:
            return distro, None, None
        repo_ver = self.get_repository_version(distro)
        content = self.get_content(repo_ver)
        return distro, repo_ver, content


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
        distro = self.get_distribution(path)
        if not distro.allow_uploads:
            return HttpResponseForbidden(reason="Index is not allowing uploads")

        repo = distro.repository
        if not repo:
            return HttpResponseBadRequest(reason="Index is not pointing to a repository")

        serializer = PackageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        artifact, filename = serializer.validated_data["content"]
        repo_content = self.get_content(self.get_repository_version(distro))
        if repo_content.filter(filename=filename).exists():
            return HttpResponseBadRequest(reason=f"Package {filename} already exists in index")

        if settings.PYTHON_GROUP_UPLOADS:
            return self.upload_package_group(repo, artifact, filename, request.session)

        result = dispatch(tasks.upload, exclusive_resources=[artifact, repo],
                          kwargs={"artifact_sha256": artifact.sha256,
                                  "filename": filename,
                                  "repository_pk": str(repo.pk)})
        return Response(data={"task": reverse('tasks-detail', args=[result.pk], request=None)})

    def upload_package_group(self, repo, artifact, filename, session):
        """Steps 4 & 5, spawns tasks to add packages to index."""
        start_time = datetime.now(tz=timezone.utc) + timedelta(seconds=5)
        task = "updated"
        if not session.get("start"):
            task = self.create_group_upload_task(session, repo, artifact, filename, start_time)
        else:
            sq = Session.objects.select_for_update(nowait=True).filter(pk=session.session_key)
            try:
                with transaction.atomic():
                    sq.first()
                    current_start = datetime.fromisoformat(session['start'])
                    if current_start >= datetime.now(tz=timezone.utc):
                        session['artifacts'].append((str(artifact.sha256), filename))
                        session['start'] = str(start_time)
                        session.modified = False
                        session.save()
                    else:
                        raise DatabaseError
            except DatabaseError:
                session.cycle_key()
                task = self.create_group_upload_task(session, repo, artifact, filename, start_time)
        data = {"session": session.session_key, "task": task, "task_start_time": start_time}
        return Response(data=data)

    def create_group_upload_task(self, cur_session, repository, artifact, filename, start_time):
        """Creates the actual task that adds the packages to the index."""
        cur_session['start'] = str(start_time)
        cur_session['artifacts'] = [(str(artifact.sha256), filename)]
        cur_session.modified = False
        cur_session.save()
        result = dispatch(tasks.upload_group, exclusive_resources=[artifact, repository],
                          kwargs={"session_pk": str(cur_session.session_key),
                                  "repository_pk": str(repository.pk)})
        return reverse('tasks-detail', args=[result.pk], request=None)


class SimpleView(ViewSet, PackageUploadMixin):
    """View for the PyPI simple API."""

    permission_classes = [IsAuthenticatedOrReadOnly]

    @extend_schema(summary="Get index simple page")
    def list(self, request, path):
        """Gets the simple api html page for the index."""
        distro, repo_version, content = self.get_drvc(path)
        if self.should_redirect(distro, repo_version=repo_version):
            return redirect(urljoin(BASE_CONTENT_URL, f'{path}/simple/'))
        names = content.order_by('name').values_list('name', flat=True).distinct().iterator()
        return StreamingHttpResponse(write_simple_index(names, streamed=True))

    def pull_through_package_simple(self, package, path, remote):
        """Gets the package's simple page from remote."""
        def parse_url(link):
            parsed = urlparse(link.url)
            digest, _, value = parsed.fragment.partition('=')
            stripped_url = urlunsplit(chain(parsed[:3], ("", "")))
            redirect = f'{path}/{link.text}?redirect={stripped_url}'
            d_url = urljoin(BASE_CONTENT_URL, redirect)
            return link.text, d_url, value if digest == 'sha256' else ''

        url = remote.get_remote_artifact_url(f'simple/{package}/')
        kwargs = {}
        if proxy_url := remote.proxy_url:
            if remote.proxy_username or remote.proxy_password:
                parsed_proxy = urlparse(proxy_url)
                netloc = f"{remote.proxy_username}:{remote.proxy_password}@{parsed_proxy.netloc}"
                proxy_url = urlunsplit((parsed_proxy.scheme, netloc, "", "", ""))
            kwargs["proxies"] = {"http": proxy_url, "https": proxy_url}

        response = requests.get(url, stream=True, **kwargs)
        links = parse_links_stream_response(response)
        packages = (parse_url(link) for link in links)
        return StreamingHttpResponse(write_simple_detail(package, packages, streamed=True))

    @extend_schema(operation_id="pypi_simple_package_read", summary="Get package simple page")
    def retrieve(self, request, path, package):
        """Retrieves the simple api html page for a package."""
        distro, repo_ver, content = self.get_drvc(path)
        # Should I redirect if the normalized name is different?
        normalized = canonicalize_name(package)
        if distro.remote:
            if not repo_ver or not content.filter(name__normalize=normalized).exists():
                return self.pull_through_package_simple(normalized, path, distro.remote)
        if self.should_redirect(distro, repo_version=repo_ver):
            return redirect(urljoin(BASE_CONTENT_URL, f'{path}/simple/{normalized}/'))
        packages = (
            content.filter(name__normalize=normalized)
            .values_list('filename', 'sha256', 'name')
            .iterator()
        )
        try:
            present = next(packages)
        except StopIteration:
            raise Http404(f"{normalized} does not exist.")
        else:
            packages = chain([present], packages)
            name = present[2]
        releases = ((f, urljoin(BASE_CONTENT_URL, f'{path}/{f}'), d) for f, d, _ in packages)
        return StreamingHttpResponse(write_simple_detail(name, releases, streamed=True))

    @extend_schema(request=PackageUploadSerializer,
                   responses={200: PackageUploadTaskSerializer},
                   summary="Upload a package")
    def create(self, request, path):
        """
        Upload package to the index.
        This endpoint has the same functionality as the upload endpoint at the `/legacy` url of the
        index. This is provided for convenience for users who want a single index url for all their
        Python tools. (pip, twine, poetry, pipenv, ...)
        """
        return self.upload(request, path)


class MetadataView(ViewSet, PyPIMixin):
    """View for the PyPI JSON metadata endpoint."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(tags=["Pypi: Metadata"],
                   responses={200: PackageMetadataSerializer},
                   summary="Get package metadata")
    def retrieve(self, request, path, meta):
        """
        Retrieves the package's core-metadata specified by
        https://packaging.python.org/specifications/core-metadata/.
        `meta` must be a path in form of `{package}/json/` or `{package}/{version}/json/`
        """
        distro, repo_ver, content = self.get_drvc(path)
        meta_path = PurePath(meta)
        name = None
        version = None
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
            json_body = python_content_to_json(path, package_content, version=version)
            if json_body:
                return Response(data=json_body, headers=headers)
        return Response(status="404")


class PyPIView(ViewSet, PyPIMixin):
    """View for base_url of distribution."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(responses={200: SummarySerializer},
                   summary="Get index summary")
    def retrieve(self, request, path):
        """Gets package summary stats of index."""
        distro, repo_ver, content = self.get_drvc(path)
        files = content.count()
        releases = content.distinct("name", "version").count()
        projects = content.distinct("name").count()
        data = {"projects": projects, "releases": releases, "files": files}
        return Response(data=data)


class UploadView(ViewSet, PackageUploadMixin):
    """View for the `/legacy` upload endpoint."""

    @extend_schema(request=PackageUploadSerializer,
                   responses={200: PackageUploadTaskSerializer},
                   summary="Upload a package")
    def create(self, request, path):
        """
        Upload package to the index.

        This is the endpoint that tools like Twine and Poetry use for their upload commands.
        """
        return self.upload(request, path)
