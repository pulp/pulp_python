Importer Reference
==================

The Python importer supports the standard Pulp importer keys, as well as one custom config key:

package_names: This key is a comma separated list of the names of the packages that should be
                synchronized from the feed URL. Sync will fail if either package_names or feed
                URL is missing.
