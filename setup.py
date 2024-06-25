#!/usr/bin/env python3

from setuptools import setup, find_packages

with open("requirements.txt") as requirements:
    requirements = requirements.readlines()

with open("README.md") as f:
    long_description = f.read()

setup(
    name="pulp-python",
    version="3.12.0",
    description="pulp-python plugin for the Pulp Project",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="GPLv2+",
    python_requires=">=3.9",
    author="Pulp Project Developers",
    author_email="pulp-list@redhat.com",
    url="https://www.pulpproject.org",
    install_requires=requirements,
    include_package_data=True,
    packages=find_packages(exclude=["tests"]),
    classifiers=(
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Operating System :: POSIX :: Linux",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
    ),
    entry_points={
        "pulpcore.plugin": ["pulp_python = pulp_python:default_app_config"],
        "pytest11": ["pulp_python = pulp_python.pytest_plugin"],
    },
)
