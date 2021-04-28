# Build custom package
python -m build $PLUGIN_SOURCE
# Upload built package distributions to my-pypi
twine upload --repository-url $BASE_ADDR/pypi/my-pypi/simple/ -u admin -p password "$PLUGIN_SOURCE"dist/*
