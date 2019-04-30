echo 'pip install --trusted-host localhost -i $CONTENT_ADDR/pulp/content/foo/simple/ shelf-reader'
pip install --trusted-host localhost -i $CONTENT_ADDR/pulp/content/foo/simple/ shelf-reader

echo "is shelf reader installed?"
pip freeze | grep shelf-reader
