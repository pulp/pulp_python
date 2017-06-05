#!/usr/bin/env python3

from setuptools import find_packages, setup


setup(
    name='pulp-python-common',
    version='3.0.0a1.dev0',
    packages=find_packages(exclude=['test']),
    url='http://www.pulpproject.org',
    license='GPLv2+',
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    description='Common code for Pulp\'s Python support.',
)
