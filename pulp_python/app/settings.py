import socket

PYTHON_GROUP_UPLOADS = False
PYPI_API_HOSTNAME = 'https://' + socket.getfqdn()

DRF_ACCESS_POLICY = {
    "dynaconf_merge_unique": True,
    "reusable_conditions": ["pulp_python.app.global_access_conditions"],
}
