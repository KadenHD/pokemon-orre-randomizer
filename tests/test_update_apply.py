"""Exercise the actual Windows update helper against disposable dummy apps."""
import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from orre_randomizer.update_apply import automatic_updates_supported, read_update_result, update_kind

HELPER = Path(__file__).resolve().parents[1] / 'orre_randomizer/windows_update.ps1'
WINDOWS = Path(os.environ.get('SystemRoot', 'C:/Windows'))
POWERSHELL = WINDOWS / 'System32/WindowsPowerShell/v1.0/powershell.exe'
CSC = WINDOWS / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'


class UpdateApplyTests(unittest.TestCase):
    def test_source_interpreters_and_non_windows_apps_never_replace_themselves(self):
        with patch('orre_randomizer.update_apply.sys.frozen', False, create=True):
            self.assertFalse(automatic_updates_supported())
        with patch('orre_randomizer.update_apply.sys.platform', 'linux'):
            self.assertFalse(automatic_updates_supported())

    def test_install_kind_and_bounded_restart_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch('orre_randomizer.update_apply.sys.executable', str(root / 'OrreRandomizer.exe')):
                self.assertEqual(update_kind(), 'portable')
                (root / 'unins000.exe').touch()
                self.assertEqual(update_kind(), 'installer')
            status = root / 'status.json'
            for data, valid in ((dict(state='complete', version='1.2.20'), True),
                                (dict(state='error', version='1.2.20', code='disk'), True),
                                (dict(state='ready', version='1.2.20'), False),
                                (dict(state='complete', version=[]), False), ([], False)):
                status.write_text(json.dumps(data))
                self.assertEqual(read_update_result(status) is not None, valid)
            status.write_text('x' * 1025)
            self.assertIsNone(read_update_result(status))
            status.write_text('not json')
            self.assertIsNone(read_update_result(status))


@unittest.skipUnless(sys.platform == 'win32' and CSC.is_file(), 'requires Windows .NET compiler')
class WindowsUpdateHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = tempfile.TemporaryDirectory(prefix='orre-updater-test-tools-')
        cls.addClassCleanup(cls.tools.cleanup)
        root = Path(cls.tools.name).resolve(strict=True)
        cls.versions = {}
        for version in ('old', 'new'):
            code = root / f'{version}.cs'
            # Windowless fixture. Restart readiness is not process termination:
            # the test must observe the exact owned process before deleting it.
            code.write_text('''using System; using System.IO; using System.Threading; using System.Diagnostics;
class App { static void Main(string[] args) {
string root = AppDomain.CurrentDomain.BaseDirectory;
if (args.Length > 0 && args[0] == "--hold") {
while (!File.Exists(Path.Combine(root, "release-parent"))) Thread.Sleep(20);
} else { File.WriteAllText(Path.Combine(root, "relaunched.txt"), "''' + version + '''");
File.WriteAllText(Path.Combine(root, "reset-env.txt"), Environment.GetEnvironmentVariable("PYINSTALLER_RESET_ENVIRONMENT") ?? "");
using (Process current = Process.GetCurrentProcess()) {
File.WriteAllLines(Path.Combine(root, "restart-process.tmp"), new string[] {
current.Id.ToString(), current.StartTime.ToFileTimeUtc().ToString(), current.MainModule.FileName });
File.Move(Path.Combine(root, "restart-process.tmp"), Path.Combine(root, "restart-process.txt"));
}
Stopwatch watchdog = Stopwatch.StartNew();
while (!File.Exists(Path.Combine(root, "release-restarted")) && watchdog.ElapsedMilliseconds < 10000) Thread.Sleep(10);
if (!File.Exists(Path.Combine(root, "release-restarted"))) Environment.Exit(73);
string delay = Path.Combine(root, "restart-delay-ms");
if (File.Exists(delay)) Thread.Sleep(Math.Min(1000, Math.Max(0, Int32.Parse(File.ReadAllText(delay)))));
}
} }''')
            executable = root / f'{version}.exe'
            subprocess.run([str(CSC), '/nologo', '/target:winexe', f'/out:{executable}', str(code)],
                           check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
            cls.versions[version] = executable.read_bytes()
        installer = root / 'installer.cs'
        installer.write_text('''using System; using System.IO;
class Setup { static int Main(string[] args) {
string work = AppDomain.CurrentDomain.BaseDirectory;
File.WriteAllLines(Path.Combine(work, "installer-arguments.txt"), args);
if (File.Exists(Path.Combine(work, "fail-installer"))) return 7;
string dir = null; foreach (string arg in args) if (arg.StartsWith("/DIR=")) dir = arg.Substring(5);
if (dir == null) return 8;
File.WriteAllBytes(Path.Combine(dir, "OrreRandomizer.exe"), Convert.FromBase64String("'''
            + base64.b64encode(cls.versions['new']).decode() + '''"));
File.WriteAllText(Path.Combine(dir, "_internal", "version.txt"), "new");
return 0; } }''')
        executable = root / 'installer.exe'
        subprocess.run([str(CSC), '/nologo', '/target:winexe', f'/out:{executable}', str(installer)],
                       check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
        cls.installer = executable.read_bytes()

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix='orre-updater-test-')
        self.addCleanup(self.folder.cleanup)
        # Match start_helper(): hosted Windows TEMP may use an 8.3 path alias,
        # while Process.MainModule.FileName reports the full executable path.
        self.root = Path(self.folder.name).resolve(strict=True)
        self.target = self.root / 'Portable app with spaces é'
        self.work = self.root / 'private-job'
        self.target.mkdir()
        self.work.mkdir()
        self.exe = self.target / 'OrreRandomizer.exe'
        self.exe.write_bytes(self.versions['old'])
        (self.target / '_internal').mkdir()
        (self.target / '_internal/version.txt').write_text('old')
        (self.target / '_internal/obsolete.txt').write_text('old bundle file')
        (self.target / '_internal/user-note.txt').write_text('keep personal note')
        (self.target / 'input.iso').write_bytes(b'keep ROM')
        (self.target / 'save.gci').write_bytes(b'keep save')
        (self.target / 'profile.json').write_text('keep profile')
        (self.target / 'update-files.json').write_text(json.dumps([
            'OrreRandomizer.exe', '_internal/version.txt', '_internal/obsolete.txt', 'update-files.json']))
        self.parent = subprocess.Popen([str(self.exe), '--hold'], creationflags=subprocess.CREATE_NO_WINDOW)
        self.addCleanup(self.stop_parent)
        self.restart_reaped = False
        self.addCleanup(self.reap_restarted_fixture)
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel = kernel
        kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                     wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
        self.assertTrue(kernel.GetProcessTimes(wintypes.HANDLE(self.parent._handle), ctypes.byref(created),
            ctypes.byref(exited), ctypes.byref(system), ctypes.byref(user)))
        self.birth = str(created.dwLowDateTime | created.dwHighDateTime << 32)

    def stop_parent(self):
        if self.parent.poll() is None:
            (self.target / 'release-parent').touch()
            self.parent.wait(timeout=10)

    def wait_restarted_fixture(self, *, required=True):
        if self.restart_reaped:
            return
        marker = self.target / 'restart-process.txt'
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        if not marker.exists() and not required:
            return
        self.assertTrue(marker.is_file(), 'The restarted fixture did not publish its process identity')
        pid, birth, recorded_path = marker.read_text('utf-8-sig').splitlines()
        self.assertEqual(Path(recorded_path).resolve(strict=True), self.exe)
        # A native handle retains identity even if the numeric PID is reused.
        handle = self.kernel.OpenProcess(0x00101001, False, int(pid))
        self.assertTrue(handle, 'Cannot observe the owned restarted fixture')
        identified = False
        try:
            created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
            self.assertTrue(self.kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                                       ctypes.byref(system), ctypes.byref(user)))
            self.assertEqual(str(created.dwLowDateTime | created.dwHighDateTime << 32), birth)
            image = ctypes.create_unicode_buffer(32768)
            length = wintypes.DWORD(len(image))
            self.assertTrue(self.kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(length)))
            self.assertEqual(Path(image.value).resolve(strict=True), self.exe)
            identified = True
            (self.target / 'release-restarted').touch()
            result = self.kernel.WaitForSingleObject(handle, 5000)
            self.assertEqual(result, 0, 'The restarted fixture kept its executable mapped after release')
            code = wintypes.DWORD()
            self.assertTrue(self.kernel.GetExitCodeProcess(handle, ctypes.byref(code)))
            self.assertEqual(code.value, 0)
            self.restart_reaped = True
        finally:
            # On a failed assertion, clean up only the verified private fixture;
            # retain the original failure instead of ignoring a lingering child.
            if identified and self.kernel.WaitForSingleObject(handle, 0) == 258:
                self.kernel.TerminateProcess(handle, 74)
                self.kernel.WaitForSingleObject(handle, 1000)
            self.kernel.CloseHandle(handle)
            child = getattr(self, 'fixture_child', None)
            if identified and child is not None and child.pid == int(pid):
                child.wait(timeout=1)
                child._handle.Close()

    def reap_restarted_fixture(self):
        # Runs after stop_helper and before stop_parent/TemporaryDirectory.
        # Also covers an assertion failing between the helper's exit and the
        # child's readiness marker. The fixture has its own bounded watchdog.
        if ((self.target / 'restart-process.txt').exists()
                or hasattr(self, 'helper') and self.parent.poll() is not None):
            self.wait_restarted_fixture(required=False)

    def make_job(self, extra=None, bad_hash=False, wrong_parent=False, kind='portable'):
        package = self.work / ('package.zip' if kind == 'portable' else 'package.exe')
        files = {'OrreRandomizer.exe': self.versions['new'], '_internal/version.txt': b'new'}
        files['update-files.json'] = json.dumps([*files, 'update-files.json']).encode()
        if kind == 'portable':
            with zipfile.ZipFile(package, 'x') as archive:
                for name, data in files.items():
                    archive.writestr('OrreRandomizer/' + name, data)
                if extra:
                    archive.writestr(*extra)
        else:
            package.write_bytes(self.installer)
        request = self.work / 'request.json'
        request.write_text(json.dumps(dict(package=str(package), size=package.stat().st_size,
            sha256='0' * 64 if bad_hash else hashlib.sha256(package.read_bytes()).hexdigest(),
            kind=kind, version='1.2.20', executable=str(self.exe), parent=self.parent.pid,
            parent_started='0' if wrong_parent else self.birth)), encoding='utf-8')
        self.log = (self.work / 'helper.log').open('wb')
        self.addCleanup(self.log.close)
        self.helper = subprocess.Popen([str(POWERSHELL), '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden',
            '-ExecutionPolicy', 'Bypass', '-File', str(HELPER), '-Request', str(request)],
            stdout=self.log, stderr=self.log, creationflags=subprocess.CREATE_NO_WINDOW)
        self.addCleanup(self.stop_helper)

    def stop_helper(self):
        if self.helper.poll() is None:
            (self.work / 'cancel').touch()
            self.stop_parent()
            try:
                self.helper.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.helper.terminate()
                self.helper.wait(timeout=5)

    def finish_helper(self):
        try:
            self.helper.wait(timeout=12)
        except subprocess.TimeoutExpired:
            self.fail((self.work / 'helper.log').read_text(errors='replace'))
        if self.parent.poll() is not None and not (self.work / 'cancel').exists():
            self.wait_restarted_fixture()

    def wait_status(self, state, timeout=15):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            value = read_update_result(self.work / 'status.json')
            # The public result reader deliberately ignores the ready handshake.
            try:
                raw = json.loads((self.work / 'status.json').read_text('utf-8-sig'))
            except (OSError, ValueError):
                raw = {}
            if raw.get('state') == state:
                return raw
            if raw.get('state') == 'error' or self.helper.poll() is not None:
                self.fail(f'Unexpected helper result {value}: {(self.work / "helper.log").read_text(errors="replace")}')
            time.sleep(.05)
        self.fail(f'Helper timeout: {(self.work / "helper.log").read_text(errors="replace")}')

    def assert_personal_files(self):
        self.assertEqual((self.target / 'input.iso').read_bytes(), b'keep ROM')
        self.assertEqual((self.target / 'save.gci').read_bytes(), b'keep save')
        self.assertEqual((self.target / 'profile.json').read_text(), 'keep profile')
        self.assertEqual((self.target / '_internal/user-note.txt').read_text(), 'keep personal note')

    def test_portable_update_replaces_bundle_restarts_and_preserves_unmanaged_files(self):
        self.make_job()
        self.wait_status('ready')
        self.assertEqual(self.exe.read_bytes(), self.versions['old'])
        self.stop_parent()
        self.finish_helper()
        self.wait_status('complete')
        self.assertEqual(self.helper.returncode, 0)
        self.assertEqual(self.exe.read_bytes(), self.versions['new'])
        self.assertEqual((self.target / '_internal/version.txt').read_text(), 'new')
        self.assertFalse((self.target / '_internal/obsolete.txt').exists())
        deadline = time.monotonic() + 5
        while not (self.target / 'relaunched.txt').exists() and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertEqual((self.target / 'relaunched.txt').read_text(), 'new')
        self.assertEqual((self.target / 'reset-env.txt').read_text(), '1')
        self.assertFalse((self.work / 'package.zip').exists())
        self.assertFalse((self.work / 'staged').exists())
        self.assertFalse(list(self.target.glob('.orre-update-backup-*')))
        self.assert_personal_files()

    def test_installer_runs_silently_in_the_same_folder_and_restarts(self):
        self.make_job(kind='installer')
        self.wait_status('ready')
        self.stop_parent()
        self.finish_helper()
        self.assertEqual(read_update_result(self.work / 'status.json')['state'], 'complete')
        arguments = (self.work / 'installer-arguments.txt').read_text(encoding='utf-8').splitlines()
        self.assertIn('/VERYSILENT', arguments)
        self.assertIn('/SUPPRESSMSGBOXES', arguments)
        self.assertIn('/NORESTART', arguments)
        self.assertIn('/DIR=' + str(self.target), arguments)
        self.assertEqual(self.exe.read_bytes(), self.versions['new'])
        self.assertFalse((self.work / 'package.exe').exists())
        self.assert_personal_files()

    def test_restart_marker_does_not_release_the_executable_before_the_process_exits(self):
        self.stop_parent()
        (self.target / 'restart-delay-ms').write_text('250')
        child = subprocess.Popen([str(self.exe)], creationflags=subprocess.CREATE_NO_WINDOW)
        self.fixture_child = child
        marker = self.target / 'restart-process.txt'
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertTrue(marker.is_file())
        self.assertIsNone(child.poll())
        # Negative control: the old marker-only cleanup really fails on Windows.
        with self.assertRaises(PermissionError):
            self.exe.unlink()
        started = time.monotonic()
        self.wait_restarted_fixture()
        self.assertGreaterEqual(time.monotonic() - started, .15)
        self.assertEqual(child.wait(timeout=1), 0)
        self.exe.unlink()  # The image is now genuinely unmapped and deletable.

    def test_failed_installer_reports_failure_and_restarts_the_old_app(self):
        self.make_job(kind='installer')
        (self.work / 'fail-installer').touch()
        self.wait_status('ready')
        self.stop_parent()
        self.finish_helper()
        self.assertEqual(read_update_result(self.work / 'status.json')['state'], 'error')
        self.assertEqual(self.exe.read_bytes(), self.versions['old'])
        self.assert_personal_files()

    def test_cancel_before_handoff_never_restarts_or_changes_the_old_app(self):
        self.make_job()
        self.wait_status('ready')
        (self.work / 'cancel').touch()
        self.finish_helper()
        self.assertIsNone(self.parent.poll())
        self.assertEqual(self.exe.read_bytes(), self.versions['old'])
        self.assertFalse((self.target / 'relaunched.txt').exists())
        self.assert_personal_files()

    def test_bad_hash_does_not_close_or_change_the_old_app(self):
        self.make_job(bad_hash=True)
        self.helper.wait(timeout=15)
        result = read_update_result(self.work / 'status.json')
        self.assertEqual(result['code'], 'checksum')
        self.assertIsNone(self.parent.poll())
        self.assertEqual(self.exe.read_bytes(), self.versions['old'])
        self.assertFalse((self.target / 'relaunched.txt').exists())
        self.assert_personal_files()

    def test_wrong_parent_instance_is_rejected(self):
        self.make_job(wrong_parent=True)
        self.helper.wait(timeout=15)
        self.assertEqual(read_update_result(self.work / 'status.json')['state'], 'error')
        self.assertIsNone(self.parent.poll())
        self.assertEqual(self.exe.read_bytes(), self.versions['old'])

    def test_traversal_case_collision_rom_entry_and_ntfs_stream_are_rejected(self):
        for name in ('OrreRandomizer/../escaped.txt', 'OrreRandomizer/_internal/../../escaped.txt',
                     'OrreRandomizer/orrerandomizer.exe', 'OrreRandomizer/payload.iso',
                     'OrreRandomizer/_internal/file:stream'):
            with self.subTest(path=name):
                self.make_job(extra=(name, b'invalid'))
                self.helper.wait(timeout=15)
                self.assertEqual(read_update_result(self.work / 'status.json')['code'], 'package')
                self.assertIsNone(self.parent.poll())
                self.assertEqual(self.exe.read_bytes(), self.versions['old'])
                (self.work / 'status.json').unlink()
        self.assertFalse((self.root / 'escaped.txt').exists())
        self.assert_personal_files()

    def test_locked_bundle_file_rolls_back_the_replaced_executable(self):
        self.make_job()
        self.wait_status('ready')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                      wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateFileW(str(self.target / '_internal/version.txt'), 0x80000000, 1, None, 3, 0, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            self.stop_parent()
            self.finish_helper()
            self.assertEqual(read_update_result(self.work / 'status.json')['state'], 'error')
            self.assertEqual(self.exe.read_bytes(), self.versions['old'])
            self.assertEqual((self.target / '_internal/version.txt').read_text(), 'old')
            self.assertFalse(list(self.target.glob('.orre-update-backup-*')))
            self.assert_personal_files()
        finally:
            kernel.CloseHandle(handle)
