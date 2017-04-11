sdafdsf
#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import os
import subprocess
import sys


from pulp.devel import doc_check
from pulp.devel.test_runner import run_tests


# Find and eradicate any existing .pyc files, so they do not eradicate us!
PROJECT_DIR = os.path.dirname(__file__)
subprocess.call(['find', PROJECT_DIR, '-name', '*.pyc', '-delete'])

# Check the code for PEP-8 compliance
config_file = os.path.join(PROJECT_DIR, 'flake8.cfg')
exit_code = subprocess.call(['flake8', '--config', config_file, PROJECT_DIR])

if exit_code != 0:
    sys.exit(exit_code)

# Check the code for PEP-257 compliance
# We should remove some of these over time
pep257_fail_ignore_codes = 'D100,D103,D104,D200,D202,D203,D205,D400,D401,D402'

print "checking pep257 for failures, ignoring %s" % pep257_fail_ignore_codes
exit_code = subprocess.call(['pep257', '--ignore=' + pep257_fail_ignore_codes])

if exit_code != 0:
    sys.exit(exit_code)

# Ensure that all doc strings are present
doc_check.recursive_check(PROJECT_DIR)

PACKAGES = [PROJECT_DIR, 'pulp_python', ]

TESTS = [
    'common/test/unit/',
    'extensions_admin/test/unit/',
]

PLUGIN_TESTS = ['plugins/test/unit/']

dir_safe_all_platforms = [os.path.join(os.path.dirname(__file__), x) for x in TESTS]
dir_safe_non_rhel5 = [os.path.join(os.path.dirname(__file__), x) for x in PLUGIN_TESTS]

sys.exit(run_tests(PACKAGES, dir_safe_all_platforms, dir_safe_non_rhel5))
