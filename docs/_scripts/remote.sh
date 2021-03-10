# Create a remote that syncs some versions of shelf-reader into your repository.
pulp python remote create --name bar --url https://pypi.org/ --includes '["shelf-reader"]'
