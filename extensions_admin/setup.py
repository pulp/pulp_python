#!/usr/bin/env python2

from setuptools import find_packages, setup


setup(
    name='pulp_python_extensions_admin',
    version='2.0.4b1',
    packages=find_packages(exclude=['test']),
    url='http://www.pulpproject.org',
    license='GPLv2+',
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    description='pulp-admin extensions for python package support',
    entry_points={
        'pulp.extensions.admin': [
            'repo_admin = pulp_python.extensions.admin.pulp_cli:initialize',
        ]
    }
)
