Added PackagePermissionGuard content guard for fine-grained package-level access control.

PackagePermissionGuard allows controlling download and upload permissions for individual PyPI packages
within a single distribution/index. Policies map package names to lists of user/group PRNs that are
allowed to access those packages.

