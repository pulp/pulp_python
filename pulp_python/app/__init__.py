from pulpcore.plugin import PulpPluginAppConfig


class PulpPythonPluginAppConfig(PulpPluginAppConfig):
    """
    Entry point for pulp_python plugin.
    """

    name = "pulp_python.app"
    label = "python"
    version = "3.11.6"
    python_package_name = "pulp-python"
