from django.test import TestCase
from pulp_python.app.models import PythonPackageContent, PythonImporter
from pulpcore.plugin.models import Repository, RepositoryContent


class ImportersTestCase(TestCase):

    def setUp(self):

        repo1 = Repository.objects.create(name='repo1')
        self.importer1 = PythonImporter.objects.create(
            name='importer1', download_policy='immediate', sync_mode='mirror',
            repository=repo1, project_names=[])
        content = PythonPackageContent.objects.create(
            filename='filename', packagetype='bdist_wheel',
            name='project', version='0.0.1')

        RepositoryContent.objects.create(repository=repo1, content=content)

    def test_fetch_inventory(self):

        remote = self.importer1._fetch_inventory()
        self.assertEqual(remote, {'filename'})

    def test_find_delta_mirror_true(self):

        inventory = set(['test1', 'test3'])
        remote = set(['test1', 'test2'])
        delta = self.importer1._find_delta(inventory, remote, True)

        self.assertEqual(len(delta.additions), 1)
        self.assertTrue('test2' in delta.additions)

        self.assertEqual(len(delta.removals), 1)
        self.assertTrue('test3' in delta.removals)

    def test_find_delta_mirror_false(self):

        inventory = set(['test1', 'test3'])
        remote = set(['test1', 'test2'])
        delta = self.importer1._find_delta(inventory, remote, False)

        self.assertEqual(len(delta.additions), 1)
        self.assertTrue('test2' in delta.additions)

        self.assertEqual(len(delta.removals), 0)
