# Welcome to Pulp Python

The `python` plugin extends [pulpcore](site:pulpcore/) to support
hosting python packages. This plugin is a part of the [Pulp Project](site:/), and assumes some familiarity with the [pulpcore documentation](site:pulpcore/).

If you are just getting started, we recommend getting to know the [basic
workflows](site:pulp_python/docs/user/guides/pypi/).

The REST API documentation for `pulp_python` is available [here](site:pulp_python/restapi/).

## Features

- [Create local mirrors of PyPI](site:pulp_python/docs/user/guides/sync/) that you have full control over
- [Upload your own Python packages](site:pulp_python/docs/user/guides/upload/)
- [Perform pip install](site:pulp_python/docs/user/guides/publish/) from your Pulp Python repositories
- Download packages on-demand to reduce disk usage
- Every operation creates a restorable snapshot with Versioned Repositories
- Curate your Python repositories with allowed and disallowed packages
- Host content either locally or on S3/Azure/GCP
- De-duplication of all saved content

## Tech Preview

Some additional features are being supplied as a tech preview.  There is a possibility that
backwards incompatible changes will be introduced for these particular features.  For a list of
features currently being supplied as tech previews only, see the [tech preview page](site:pulp_python/docs/user/learn/tech-preview/).

## How to use these docs

The documentation here should be considered the **primary documentation for managing Python related content.**
All relevant workflows are covered here, with references to some pulpcore supplemental docs.
Users may also find pulpcore’s conceptual docs useful.

This documentation falls into two main categories:

1. `How-to Guides` shows the **major features** of the Python plugin, with links to reference docs.
2. The [REST API Docs](site:pulp_python/restapi/) are automatically generated and provide more detailed information for each 
minor feature, including all fields and options.
