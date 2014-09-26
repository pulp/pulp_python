#!/usr/bin/env bash

# Use this bash script to run argument 1 on each setup.py in this project

for setup in `find . -name setup.py`; do
    pushd `dirname $setup`;
    python setup.py "$@";
    popd;
done;
