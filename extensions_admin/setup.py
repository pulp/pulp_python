#!/usr/bin/env python3

from setuptools import find_packages, setup

requirements = [
    'pulp-python-common'
]

setup(
    name='pulp-python-cli',
    version='3.0.0a1.dev0',
    packages=find_packages(exclude=['test']),
    url='http://www.pulpproject.org',
    install_requires=requirements,
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
