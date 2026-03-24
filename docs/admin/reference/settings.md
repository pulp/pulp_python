# Settings

`pulp_python` adds configuration options to those offered by `pulpcore`.

## PYTHON_GROUP_UPLOADS

> This setting controls whether the uploading of packages through the PyPI APIs can be grouped
> inside http sessions. When enabled, Pulp tries to group the uploaded distributions of a package
> into one task generating one repository version. Defaults to False.

## PYPI_API_HOSTNAME

> This specifies the hostname where the PyPI API is served. It defaults to the fully qualified
> hostname of the system where the process is running. This needs to be adjusted if running behind
> a non local reverse proxy.

## PYPI_PATH_PREFIX

> This specifies where the PyPI endpoints can be found at. It defaults to `/pypi/`. The value is
> used along with `PYPI_API_HOSTNAME` to generate the links to the PyPI endpoints and should start
> and end in a slash.
