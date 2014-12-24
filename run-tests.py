#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import subprocess
import sys

from pulp.devel.test_runner import run_tests

# Find and eradicate any existing .pyc files, so they do not eradicate us!
PROJECT_DIR = os.path.dirname(__file__)
subprocess.call(['find', PROJECT_DIR, '-name', '*.pyc', '-delete'])

config_file = os.path.join(PROJECT_DIR, 'flake8.cfg')
flake8_exit_code = subprocess.call(['flake8', '--config', config_file, PROJECT_DIR])

PACKAGES = [PROJECT_DIR, 'pulp_python', ]

TESTS = [
    'common/test/unit/',
    'extensions_admin/test/unit/',
]

PLUGIN_TESTS = ['plugins/test/unit/']

dir_safe_all_platforms = [os.path.join(os.path.dirname(__file__), x) for x in TESTS]
dir_safe_non_rhel5 = [os.path.join(os.path.dirname(__file__), x) for x in PLUGIN_TESTS]

tests_exit_code = run_tests(PACKAGES, dir_safe_all_platforms, dir_safe_non_rhel5)

sys.exit(flake8_exit_code or tests_exit_code)
