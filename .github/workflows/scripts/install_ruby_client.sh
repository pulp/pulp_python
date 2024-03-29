#!/bin/bash

# WARNING: DO NOT EDIT!
#
# This file was generated by plugin_template, and is managed by it. Please use
# './plugin-template --github pulp_python' to update this file.
#
# For more info visit https://github.com/pulp/plugin_template

set -mveuo pipefail

# make sure this script runs at the repo root
cd "$(dirname "$(realpath -e "$0")")"/../../..

source .github/workflows/scripts/utils.sh

PULP_URL="${PULP_URL:-https://pulp}"
export PULP_URL
PULP_API_ROOT="${PULP_API_ROOT:-/pulp/}"
export PULP_API_ROOT

REPORTED_STATUS="$(pulp status)"
REPORTED_VERSION="$(echo "$REPORTED_STATUS" | jq --arg plugin "python" -r '.versions[] | select(.component == $plugin) | .version')"
VERSION="$(echo "$REPORTED_VERSION" | python -c 'from packaging.version import Version; print(Version(input()))')"

pushd ../pulp-openapi-generator
rm -rf pulp_python-client

if pulp debug has-plugin --name "core" --specifier ">=3.44.0.dev"
then
  curl --fail-with-body -k -o api.json "${PULP_URL}${PULP_API_ROOT}api/v3/docs/api.json?bindings&component=python"
  USE_LOCAL_API_JSON=1 ./generate.sh pulp_python ruby "$VERSION"
else
  ./generate.sh pulp_python ruby "$VERSION"
fi

pushd pulp_python-client
gem build pulp_python_client
gem install --both "./pulp_python_client-$VERSION.gem"
tar cvf ../../pulp_python/python-ruby-client.tar "./pulp_python_client-$VERSION.gem"
popd
popd
