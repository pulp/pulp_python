# Get a Python package or choose your own
curl -O https://fixtures.pulpproject.org/python-pypi/packages/shelf-reader-0.1.tar.gz
export PKG="shelf-reader-0.1.tar.gz"

# Upload it to Pulp
pulp python content upload --relative-path "$PKG" --file "$PKG"
