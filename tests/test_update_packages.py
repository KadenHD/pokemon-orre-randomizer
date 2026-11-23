"""Malformed update archives get their own bounded Windows worker process."""
from tests import test_update_apply as fixture
from orre_randomizer.update_apply import read_update_result


class WindowsUpdatePackageTests(fixture.WindowsUpdateFixture):
    def assert_rejected(self, name):
        self.make_job(extra=(name, b'invalid'))
        self.helper.wait(timeout=15)
        self.assertEqual(read_update_result(self.work / 'status.json')['code'], 'package')
        self.assertIsNone(self.parent.poll())
        self.assertEqual(self.exe.read_bytes(), self.versions['old'])
        self.assertFalse((self.root / 'escaped.txt').exists())
        self.assert_personal_files()

    def test_parent_traversal_is_rejected(self):
        self.assert_rejected('OrreRandomizer/../escaped.txt')

    def test_nested_parent_traversal_is_rejected(self):
        self.assert_rejected('OrreRandomizer/_internal/../../escaped.txt')

    def test_case_collision_is_rejected(self):
        self.assert_rejected('OrreRandomizer/orrerandomizer.exe')

    def test_rom_entry_is_rejected(self):
        self.assert_rejected('OrreRandomizer/payload.iso')

    def test_ntfs_stream_is_rejected(self):
        self.assert_rejected('OrreRandomizer/_internal/file:stream')
