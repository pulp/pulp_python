import hashlib
import unittest
from random import choice
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.pulp3.utils import (
    download_content_unit,
    gen_distribution,
    gen_repo,
    sync,
)

from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURES_URL,
    PYTHON_REMOTE_PATH,
    PYTHON_DISTRIBUTION_PATH,
    PYTHON_REPO_PATH,
)
from pulp_python.tests.functional.utils import (
    get_python_content_paths,
    gen_python_publication,
    gen_python_remote,
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class DownloadContentTestCase(unittest.TestCase):
    """
    Verify whether content served by pulp can be downloaded.
    """

    def test_all(self):
        """
        Verify whether content served by pulp can be downloaded.

        The process of publishing content is more involved in Pulp 3 than it
        was under Pulp 2. Given a repository, the process is as follows:

        1. Create a publication from the repository. (The latest repository
           version is selected if no version is specified.) A publication is a
           repository version plus metadata.
        2. Create a distribution from the publication. The distribution defines
           at which URLs a publication is available, e.g.
           ``http://example.com/content/pub-name/`` and
           ``https://example.com/content/pub-name/``.

        Do the following:

        1. Create, populate, publish, and distribute a repository.
        2. Select a random content unit in the distribution. Download that
           content unit from Pulp, and verify that the content unit has the
           same checksum when fetched directly from Pulp-Fixtures.

        This test targets the following issues:

        * `Pulp #2895 <https://pulp.plan.io/issues/2895>`_
        * `Pulp Smash #872 <https://github.com/PulpQE/pulp-smash/issues/872>`_
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        repo = client.post(PYTHON_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo['pulp_href'])

        body = gen_python_remote(PYTHON_FIXTURES_URL)
        remote = client.post(PYTHON_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote['pulp_href'])

        sync(cfg, remote, repo)
        repo = client.get(repo['pulp_href'])

        # Create a publication
        publication = gen_python_publication(cfg, repository=repo)
        self.addCleanup(client.delete, publication['pulp_href'])

        # Create a distribution.
        body = gen_distribution()
        body['publication'] = publication['pulp_href']
        distribution = client.using_handler(api.task_handler).post(
            PYTHON_DISTRIBUTION_PATH,
            body
        )
        self.addCleanup(client.delete, distribution['pulp_href'])

        # Pick a file, and download it from both Pulp Fixtures…
        unit_path = choice(get_python_content_paths(repo))
        fixtures_hash = hashlib.sha256(
            utils.http_get(urljoin(urljoin(PYTHON_FIXTURES_URL, 'packages/'), unit_path))
        ).hexdigest()

        # …and Pulp.
        content = download_content_unit(cfg, distribution, unit_path)
        pulp_hash = hashlib.sha256(content).hexdigest()

        self.assertEqual(fixtures_hash, pulp_hash)
