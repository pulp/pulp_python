echo 'pip install --trusted-host pulp -i $CONTENT_ADDR/pulp/content/foo/simple/ shelf-reader'
pip install --trusted-host pulp -i $CONTENT_ADDR/pulp/content/foo/simple/ shelf-reader

echo "is shelf reader installed?"
pip list | grep shelf-reader
