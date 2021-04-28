# This script will execute the component scripts and ensure that the documented examples
# work as expected.

# THIS SCRIPT CURRENTLY MUST BE RUN IN A PULPLIFT DEVELOPMENT ENVIRONMENT
# TODO: remove the usage of pulp-devel bash functions so they can be directly modified
# for user environments.

# From the _scripts directory, run with `source quickstart.sh` (source to preserve the environment
# variables)
export PLUGIN_SOURCE="../../"
set -e

source base.sh
source clean.sh

source repo.sh
source remote.sh
source sync.sh

source publication.sh
source distribution.sh
source autoupdate.sh
source pip.sh

source upload.sh
source add_content_repo.sh

source index.sh
source twine.sh
