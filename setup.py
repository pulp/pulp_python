#!/usr/bin/env python3

from setuptools import setup, find_packages

requirements = [
    'pulpcore-plugin',
    'pkginfo',
    'packaging',
]

with open('README.rst') as f:
    long_description = f.read()

setup(
    name='pulp-python',
    version='3.0.0b2',
    description='pulp-python plugin for the Pulp Project',
    long_description=long_description,
    license='GPLv2+',
    python_requires='>=3.5',
    author='Pulp Project Developers',
    author_email='pulp-list@redhat.com',
    url='http://www.pulpproject.org',
    install_requires=requirements,
    include_package_data=True,
    packages=find_packages(exclude=['tests']),
    classifiers=(
        'License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)',
        'Operating System :: POSIX :: Linux',
        'Development Status :: 4 - Beta',
        'Framework :: Django',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ),
    entry_points={
        'pulpcore.plugin': [
            'pulp_python = pulp_python:default_app_config',
        ]
    }
)
