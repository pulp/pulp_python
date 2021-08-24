#!/usr/bin/env bash

echo "Setting environment variables for default hostname/port for the API and the Content app"
export BASE_ADDR=${BASE_ADDR:-http://localhost:24817}
export CONTENT_ADDR=${CONTENT_ADDR:-http://localhost:24816}

# Necessary for `django-admin`
export DJANGO_SETTINGS_MODULE=pulpcore.app.settings

# Install from source
if [ -z "$(pip freeze | grep pulp-cli)" ]; then
  echo "Installing Pulp CLI"
  git clone https://github.com/pulp/pulp-cli.git
  cd pulp-cli
  pip install -e .
  cd ..
fi

# Set up CLI config file
if [ ! -f ~/.config/pulp/settings.toml ]; then
  echo "Configuring pulp-cli"
  mkdir -p ~/.config/pulp
  cat > ~/.config/pulp/cli.toml << EOF
[cli]
base_url = "$BASE_ADDR"
verify_ssl = false
format = "json"
EOF
fi
