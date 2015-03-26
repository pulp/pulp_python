#!/usr/bin/env python
from setuptools import find_packages, setup


setup(
    name='pulp_python_plugins',
    version='1.0.0c2',
    packages=find_packages(),
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
        ]
    }
)
