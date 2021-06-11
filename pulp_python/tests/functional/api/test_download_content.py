# coding=utf-8
"""Tests that verify download of content served by Pulp."""
import hashlib
import unittest
from random import choice
from urllib.parse import urljoin

from pulp_smash import utils
from pulp_smash.pulp3.utils import (
    download_content_unit,
    get_content_summary,
)
from pulp_python.tests.functional.constants import (
    PYTHON_FIXTURE_URL,
    PYTHON_LG_FIXTURE_SUMMARY,
    PYTHON_LG_PROJECT_SPECIFIER,
)
from pulp_python.tests.functional.utils import (
    cfg,
    get_python_content_paths,
    TestCaseUsingBindings,
    TestHelpersMixin,
)
from pulp_python.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


class DownloadContentTestCase(TestCaseUsingBindings, TestHelpersMixin):
    """Verify whether content served by pulp can be downloaded."""

    def test_all(self):
        """Verify whether content served by pulp can be downloaded.

        The process of publishing content is more involved in Pulp 3 than it
        was under Pulp 2. Given a repository, the process is as follows:

        1. Create a publication from the repository. (The latest repository
           version is selected if no version is specified.) A publication is a
           repository version plus metadata.
        2. Create a distribution from the publication. The distribution defines
           at which URLs a publication is available, e.g.
           ``http://example.com/content/foo/`` and
           ``http://example.com/content/bar/``.

        Do the following:

        1. Create, populate, publish, and distribute a repository.
        2. Select a random content unit in the distribution. Download that
           content unit from Pulp, and verify that the content unit has the
           same checksum when fetched directly from Pulp-Fixtures.

        This test targets the following issues:

        * `Pulp #2895 <https://pulp.plan.io/issues/2895>`_
        * `Pulp Smash #872 <https://github.com/pulp/pulp-smash/issues/872>`_
        """
        remote = self._create_remote()
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)
        # Pick a content unit (of each type), and download it from both Pulp Fixtures…
        unit_paths = [
            choice(paths) for paths in get_python_content_paths(repo.to_dict()).values()
        ]
        fixtures_hashes = [
            hashlib.sha256(
                utils.http_get(
                    urljoin(urljoin(PYTHON_FIXTURE_URL, "packages/"), unit_path[0])
                )
            ).hexdigest()
            for unit_path in unit_paths
        ]

        # …and Pulp.
        pulp_hashes = []
        for unit_path in unit_paths:
            content = download_content_unit(cfg, distro.to_dict(), unit_path[1])
            pulp_hashes.append(hashlib.sha256(content).hexdigest())

        self.assertEqual(fixtures_hashes, pulp_hashes)


class PublishPyPiJSON(TestCaseUsingBindings, TestHelpersMixin):
    """Test whether a distributed Python repository has a PyPi json endpoint
    a.k.a Can be consumed by another Pulp instance

    Test targets the following issue:

    * `Pulp #2886 <https://pulp.plan.io/issues/2886>`_
    """

    @unittest.skip("Content can not be synced without https")
    def test_basic_pulp_to_pulp_sync(self):
        """
        This test checks that the JSON endpoint is setup correctly to allow one Pulp instance
        to perform a basic sync from another Pulp instance
        """
        body = {"includes": PYTHON_LG_PROJECT_SPECIFIER, "prereleases": True}
        remote = self._create_remote(**body)
        repo = self._create_repo_and_sync_with_remote(remote)
        pub = self._create_publication(repo)
        distro = self._create_distribution_from_publication(pub)
        url_fragments = [
            cfg.get_content_host_base_url(),
            "pulp/content",
            distro.base_path,
            ""
        ]
        unit_url = "/".join(url_fragments)

        body["url"] = unit_url
        remote = self._create_remote(**body)
        repo2 = self._create_repo_and_sync_with_remote(remote)
        self.assertEqual(get_content_summary(repo2.to_dict()), PYTHON_LG_FIXTURE_SUMMARY)
