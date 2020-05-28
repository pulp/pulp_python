# Get a Python package or choose your own
curl -O https://repos.fedorapeople.org/pulp/pulp/fixtures/python-pypi/packages/shelf-reader-0.1.tar.gz
export PKG="shelf-reader-0.1.tar.gz"

# Upload it as an Artifact
echo "Upload a Python Package"
export ARTIFACT_HREF=$(http --form POST $BASE_ADDR/pulp/api/v3/artifacts/ \
    file@./$PKG | jq -r '.pulp_href')

echo "Inspecting artifact."
http $BASE_ADDR$ARTIFACT_HREF

