# Add created PythonPackage content to repository
pulp python repository add --name foo --filename "shelf-reader-0.1.tar.gz"

# After the task is complete, it gives us a new repository version
pulp python repository version show --repository foo
