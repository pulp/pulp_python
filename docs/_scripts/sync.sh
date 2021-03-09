# Using the Remote we just created, we kick off a sync task
pulp python repository sync --name foo --remote bar

# The sync command will by default wait for the sync to complete
# Use Ctrl+c or the -b option to send the task to the background

# Show the latest version when sync is done
pulp python repository version show --repository foo
