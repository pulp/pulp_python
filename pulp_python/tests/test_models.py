from django.test import TestCase
import unittest

from pulp_python.app.models import PythonPackageContent, PythonRemote
from pulpcore.plugin.models import Repository, RepositoryVersion


@unittest.skip("very out of date, fails")
class RemotesTestCase(TestCase):

    def setUp(self):

        repo1 = Repository.objects.create(name='repo1')
        self.remote1 = PythonRemote.objects.create(
            name='remote1', download_policy='immediate', sync_mode='mirror',
            projects=[])
        content = PythonPackageContent.objects.create(
            filename='filename', packagetype='bdist_wheel',
            name='project', version='0.0.1')

        self.repo_v1 = RepositoryVersion.objects.create(repository=repo1, number=1)
        self.repo_v1.add_content(content)

        self.repo_v1.save()

    def test_fetch_inventory(self):

        remote = self.remote1._fetch_inventory(self.repo_v1)
        self.assertEqual(remote, {'filename'})

    def test_find_delta_mirror_true(self):

        inventory = set(['test1', 'test3'])
        remote = set(['test1', 'test2'])
        delta = self.remote1._find_delta(inventory, remote, True)

        self.assertEqual(len(delta.additions), 1)
        self.assertTrue('test2' in delta.additions)

        self.assertEqual(len(delta.removals), 1)
        self.assertTrue('test3' in delta.removals)

    def test_find_delta_mirror_false(self):

        inventory = set(['test1', 'test3'])
        remote = set(['test1', 'test2'])
        delta = self.remote1._find_delta(inventory, remote, False)

        self.assertEqual(len(delta.additions), 1)
        self.assertTrue('test2' in delta.additions)

        self.assertEqual(len(delta.removals), 0)
