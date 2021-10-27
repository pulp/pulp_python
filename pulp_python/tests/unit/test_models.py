from django.test import TestCase

from pulp_python.app.models import PythonRemote, PythonRepository


DEFAULT_SERIAL = 10000


class TestNothing(TestCase):
    """Test Nothing (placeholder)."""

    def test_nothing_at_all(self):
        """Test that the tests are running and that's it."""
        self.assertTrue(True)


class TestRepositoryLastSerial(TestCase):
    """Tests `last_serial` gets properly set and reset with remote changes."""

    def setUp(self):
        """Set up class with repository with `last_serial` set."""
        self.remote = PythonRemote.objects.create(name="test", url="https://pypi.org")
        self.repo = PythonRepository.objects.create(
            name="test", remote=self.remote, last_serial=DEFAULT_SERIAL
        )

    def test_remote_change(self):
        """Test that `last_serial` gets reset upon remote change."""
        self.assertEqual(self.repo.remote.pk, self.remote.pk)
        self.assertEqual(self.repo.last_serial, DEFAULT_SERIAL)
        self.repo.remote = None
        self.repo.save()
        self.repo.refresh_from_db()
        self.assertEqual(self.repo.last_serial, 0)

    def test_remote_update(self):
        """Test that updating a remote will reset `last_serial`."""
        self.assertEqual(self.repo.remote.pk, self.remote.pk)
        self.assertEqual(self.repo.last_serial, DEFAULT_SERIAL)
        self.remote.url = "https://test.pypi.org"
        self.remote.save()
        self.repo.refresh_from_db()
        self.assertEqual(self.repo.last_serial, 0)

    def test_remote_update_no_change(self):
        """Test that changing 'includes' field doesn't reset `last_serial`."""
        self.assertEqual(self.repo.remote.pk, self.remote.pk)
        self.assertEqual(self.repo.last_serial, DEFAULT_SERIAL)
        self.remote.includes = ["shelf-reader"]
        self.remote.save()
        self.repo.refresh_from_db()
        self.assertEqual(self.repo.last_serial, DEFAULT_SERIAL)
