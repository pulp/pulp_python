# This configures the repository to produce new publications when a new version is created
pulp python repository update --name foo --autopublish
# This configures the distribution to be track the latest repository version for a given repository
pulp python distribution update --name foo --repository foo
