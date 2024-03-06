from pulpcore.plugin.replica import Replicator

from pulp_glue.python.context import (
    PulpPythonDistributionContext,
    PulpPythonPublicationContext,
    PulpPythonRepositoryContext,
)
from pulp_python.app.models import PythonDistribution, PythonRemote, PythonRepository
from pulp_python.app.tasks import sync as python_sync


class PythonReplicator(Replicator):
    repository_ctx_cls = PulpPythonRepositoryContext
    distribution_ctx_cls = PulpPythonDistributionContext
    publication_ctx_cls = PulpPythonPublicationContext
    app_label = "python"
    remote_model_cls = PythonRemote
    repository_model_cls = PythonRepository
    distribution_model_cls = PythonDistribution
    distribution_serializer_name = "PythonDistributionSerializer"
    repository_serializer_name = "PythonRepositorySerializer"
    remote_model_serializer_name = "PythonRemoteSerializer"
    sync_task = python_sync

    def remote_extra_fields(self, upstream_distribution):
        # This could be dangerous since python remotes are default 'on_demand'
        # Upstream sources could be entirely 'on_demand' and this replicator policy would heavily
        # strain the upstream Pulp.
        return {"policy": "immediate", "prereleases": True}

    def repository_extra_fields(self, remote):
        # Use autopublish since publications result in faster serving times
        return {"autopublish": True}

    def sync_params(self, repository, remote):
        return {"remote_pk": str(remote.pk), "repository_pk": str(repository.pk), "mirror": True}


REPLICATION_ORDER = [PythonReplicator]
