#!/usr/bin/env python3

from setuptools import find_packages, setup


setup(
    name='pulp_python_common',
    version='1.2.0b1',
    packages=find_packages(exclude=['test']),
    url='http://www.pulpproject.org',
    license='GPLv2+',
    author='Pulp Team',
    author_email='pulp-list@redhat.com',
    description='Common code for Pulp\'s Python support.',
)
