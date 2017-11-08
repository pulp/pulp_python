from pulpcore.plugin import PulpPluginAppConfig


class PulpPythonPluginAppConfig(PulpPluginAppConfig):
    name = 'pulp_python.app'
    label = 'pulp_python'
