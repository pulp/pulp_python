# Get a Python package or choose your own
curl -O https://files.pythonhosted.org/packages/3a/e3/a6954c4134a899c0006515fbd40208922572947e960b35d0d19fd5a1b3d0/shelf-reader-0.1.tar.gz
export PKG="shelf-reader-0.1.tar.gz"

# Upload it as an Artifact
echo "Upload a Python Package"
export ARTIFACT_HREF=$(http --form POST $BASE_ADDR/pulp/api/v3/artifacts/ \
    file@./$PKG | jq -r '.pulp_href')

echo "Inspecting artifact."
http $BASE_ADDR$ARTIFACT_HREF

