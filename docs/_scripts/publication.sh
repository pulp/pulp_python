# Create a new publication specifying the repository_version.
# Alternatively, you can specify just the repository, and Pulp will assume the latest version.
pulp python publication create --repository foo --version 1

# Publications can only be referenced through their pulp_href
PUBLICATION_HREF=$(pulp python publication list | jq -r .[0].pulp_href)
