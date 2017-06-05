#!/usr/bin/env python3

from setuptools import find_packages, setup

requirements = [
    'pulpcore-plugin',
    'pulp-python-common'
]

setup(
    name='pulp-python',
    version='3.0.0a1.dev0',
    packages=find_packages(exclude=['test']),
    url='http://www.pulpproject.org',
    install_requires=requirements,
    license='GPLv2+',
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    description='Plugins for Python support in pulp',
    entry_points={
        'pulp.importers': [
            'importer = pulp_python.plugins.importers.importer:entry_point',
        ],
        'pulp.distributors': [
            'distributor = pulp_python.plugins.distributors.web:entry_point'
        ],
        'pulp.server.db.migrations': [
            'pulp_python = pulp_python.plugins.migrations',
        ],
        'pulp.unit_models': [
            'python_package = pulp_python.plugins.models:Package',
        ],
    }
)
