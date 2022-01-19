if [ -n "$(pulp python repository list | grep foo)" ]; then
  pulp python repository destroy --name foo
fi

if [ -n "$(pulp python remote list | grep foo)" ]; then
  pulp python remote destroy --name bar
fi

if [ -n "$(pulp python publication list | grep pulp)" ]; then
  pulp python publication destroy --href "$(pulp python publication list | jq .[0].pulp_href)"
fi

if [ -n "$(pulp python distribution list | grep foo)" ]; then
  pulp python distribution destroy --name foo
fi

pulp orphan cleanup --protection-time 0
pip uninstall -y shelf-reader
