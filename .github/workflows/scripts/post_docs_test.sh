#!/usr/bin/env sh

export BASE_ADDR=https://pulp
export CONTENT_ADDR=https://pulp

cmd_prefix bash -c "dnf install jq -y"

cmd_user_prefix bash -c "cd pulp_python/ && pip install -r doc_requirements.txt"

cmd_user_prefix bash -c "cd pulp_python/docs/_scripts/ && source ./quickstart.sh"
