#!/usr/bin/env python3

from setuptools import setup

requirements = [
    'pulpcore-plugin',
    'pkginfo'
]

setup(
    name='pulp-python',
    version='3.0.0b1.dev0',
    description='pulp-python plugin for the Pulp Project',
    license='GPLv2+',
    author='Pulp Project Developers',
    author_email='pulp-list@redhat.com',
    url='http://www.pulpproject.org',
    install_requires=requirements,
    include_package_data=True,
    packages=['pulp_python', 'pulp_python.app'],
    entry_points={
        'pulpcore.plugin': [
            'pulp_python = pulp_python:default_app_config',
        ]
    }
)
