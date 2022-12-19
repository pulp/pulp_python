from pulpcore.plugin import PulpPluginAppConfig


class PulpPythonPluginAppConfig(PulpPluginAppConfig):
    """
    Entry point for pulp_python plugin.
    """

    name = "pulp_python.app"
    label = "python"
    version = "3.8.0"
    python_package_name = "pulp-python"
