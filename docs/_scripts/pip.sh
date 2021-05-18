echo 'pip install --trusted-host pulp -i $BASE_ADDR/pypi/foo/simple/ shelf-reader'
pip install --trusted-host pulp -i $BASE_ADDR/pypi/foo/simple/ shelf-reader

echo "is shelf reader installed?"
pip list | grep shelf-reader
