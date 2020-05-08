#!/usr/bin/env python2

from setuptools import find_packages, setup


setup(
    name='pulp_python_plugins',
    version='2.0.4b1',
    packages=find_packages(exclude=['test', 'test.*']),
    url='http://www.pulpproject.org',
    license='GPLv2+',
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    description='plugins for python support in pulp',
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
