from pulpcore.plugin import PulpPluginAppConfig

__version__ = "3.2.0.dev"


class PulpPythonPluginAppConfig(PulpPluginAppConfig):
    """
    Entry point for pulp_python plugin.
    """

    name = "pulp_python.app"
    label = "python"
    version = __version__
