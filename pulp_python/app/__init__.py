from django.db.models.signals import post_migrate
from pulpcore.plugin import PulpPluginAppConfig
from gettext import gettext as _


class PulpPythonPluginAppConfig(PulpPluginAppConfig):
    """
    Entry point for pulp_python plugin.
    """

    name = "pulp_python.app"
    label = "python"
    version = "3.12.0"
    python_package_name = "pulp-python"
    domain_compatible = True

    def ready(self):
        """Register PyPI access policy hook."""
        super().ready()
        post_migrate.connect(
            _populate_pypi_access_policies,
            sender=self,
            dispatch_uid="populate_pypi_access_policies_identifier",
        )


# TODO: Remove this when https://github.com/pulp/pulpcore/issues/5500 is resolved
def _populate_pypi_access_policies(sender, apps, verbosity, **kwargs):
    from pulp_python.app.pypi.views import PyPIView, SimpleView, UploadView, MetadataView

    try:
        AccessPolicy = apps.get_model("core", "AccessPolicy")
    except LookupError:
        if verbosity >= 1:
            print(_("AccessPolicy model does not exist. Skipping initialization."))
        return

    for viewset in (PyPIView, SimpleView, UploadView, MetadataView):
        access_policy = getattr(viewset, "DEFAULT_ACCESS_POLICY", None)
        if access_policy is not None:
            viewset_name = viewset.urlpattern()
            db_access_policy, created = AccessPolicy.objects.get_or_create(
                viewset_name=viewset_name, defaults=access_policy
            )
            if created:
                if verbosity >= 1:
                    print(
                        "Access policy for {viewset_name} created.".format(
                            viewset_name=viewset_name
                        )
                    )
            elif not db_access_policy.customized:
                dirty = False
                for key in ["statements", "creation_hooks", "queryset_scoping"]:
                    value = access_policy.get(key)
                    if getattr(db_access_policy, key, None) != value:
                        setattr(db_access_policy, key, value)
                        dirty = True
                if dirty:
                    db_access_policy.save()
                    if verbosity >= 1:
                        print(
                            "Access policy for {viewset_name} updated.".format(
                                viewset_name=viewset_name
                            )
                        )
