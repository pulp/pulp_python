import re
import os
from django.core.management import BaseCommand, CommandError
from gettext import gettext as _

from django.conf import settings

from pulpcore.plugin.util import extract_pk
from pulp_python.app.models import PythonPackageContent, PythonRepository
from pulp_python.app.utils import artifact_to_python_content_data


def repair_metadata(content):
    """
    Repairs the metadata for the passed in content queryset.
    :param content: The PythonPackageContent queryset.
    Return: number of content units that were repaired
    """
    # TODO: Add on_demand content repair?
    os.chdir(settings.WORKING_DIRECTORY)
    content = content.select_related("pulp_domain")
    immediate_content = content.filter(contentartifact__artifact__isnull=False)
    batch = []
    set_of_update_fields = set()
    total_repaired = 0
    for package in immediate_content.prefetch_related('_artifacts').iterator(chunk_size=1000):
        new_data = artifact_to_python_content_data(
            package.filename, package._artifacts.get(), package.pulp_domain
        )
        changed = False
        for field, value in new_data.items():
            if getattr(package, field) != value:
                setattr(package, field, value)
                set_of_update_fields.add(field)
                changed = True
        if changed:
            batch.append(package)
        if len(batch) == 1000:
            total_repaired += len(batch)
            PythonPackageContent.objects.bulk_update(batch, set_of_update_fields)
            batch = []
            set_of_update_fields.clear()

    if len(batch) > 0:
        total_repaired += len(batch)
        PythonPackageContent.objects.bulk_update(batch, set_of_update_fields)

    return total_repaired


def href_prn_list_handler(value):
    """Common list parsing for a string of hrefs/prns."""
    r = re.compile(
        rf"""
        (?:{settings.API_ROOT}(?:[-_a-zA-Z0-9]+/)?api/v3/repositories/python/python/[-a-f0-9]+/)
        |(?:prn:python\.pythonrepository:[-a-f0-9]+)
        """,
        re.VERBOSE
    )
    values = []
    for v in value.split(","):
        if v:
            if match := r.match(v.strip()):
                values.append(match.group(0))
            else:
                raise CommandError(f"Invalid href/prn: {v}")
    return values


class Command(BaseCommand):
    """
    Management command to repair metadata of PythonPackageContent.
    """

    help = _("Repair the metadata of PythonPackageContent stored in PythonRepositories")

    def add_arguments(self, parser):
        """Set up arguments."""
        parser.add_argument(
            "--repositories",
            type=href_prn_list_handler,
            required=False,
            help=_(
                "List of PythonRepository hrefs/prns whose content's metadata will be repaired. "
                "Leave blank to include all repositories in all domains. Mutually exclusive "
                "with domain."
            ),
        )
        parser.add_argument(
            "--domain",
            default=None,
            required=False,
            help=_(
                "The pulp domain to gather the repositories from if specified. Mutually"
                " exclusive with repositories."
            ),
        )

    def handle(self, *args, **options):
        """Implement the command."""
        domain = options.get("domain")
        repository_hrefs = options.get("repositories")
        if domain and repository_hrefs:
            raise CommandError(_("--domain and --repositories are mutually exclusive"))

        repositories = PythonRepository.objects.all()
        if repository_hrefs:
            repos_ids = [extract_pk(r) for r in repository_hrefs]
            repositories = repositories.filter(pk__in=repos_ids)
        elif domain:
            repositories = repositories.filter(pulp_domain__name=domain)

        content_set = set()
        for repository in repositories:
            content_set.update(repository.latest_version().content.values_list("pk", flat=True))
        content = PythonPackageContent.objects.filter(pk__in=content_set)
        num_repaired = repair_metadata(content)
        print(f"{len(content_set)} packages processed, {num_repaired} package metadata repaired.")
