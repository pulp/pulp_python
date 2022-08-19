#!/usr/bin/env sh

export BASE_ADDR=https://pulp
export CONTENT_ADDR=https://pulp

pip install -r doc_requirements.txt

cd docs/_scripts/
bash ./quickstart.sh
