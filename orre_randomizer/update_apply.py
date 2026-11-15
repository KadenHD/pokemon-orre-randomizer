"""Launch a private Windows helper, never replace a running executable in Qt."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from . import APP_EXECUTABLE
from .update_service import allowed_download, _version_key


def automatic_updates_supported():
    executable = Path(sys.executable)
    return (sys.platform == "win32" and bool(getattr(sys, "frozen", False))
            and executable.name.lower() == f"{APP_EXECUTABLE}.exe".lower()
            and (executable.parent / "_internal").is_dir())


def update_kind():
    return "installer" if (Path(sys.executable).parent / "unins000.exe").is_file() else "portable"


def read_update_result(path):
    try:
        path = Path(path)
        if path.stat().st_size > 1024:
            return None
        result = json.loads(path.read_text("utf-8-sig"))
        if (isinstance(result, dict) and result.get("state") in ("complete", "error")
                and _version_key(result.get("version")) is not None):
            return result
    except (OSError, ValueError, TypeError):
        pass
    return None


def start_helper(package: Path, update, work: Path):
    """Only a frozen Windows app may request an update of its own directory."""
    if not automatic_updates_supported() or not allowed_download(update):
        raise OSError("unsupported")
    executable = Path(sys.executable).resolve(strict=True)
    if executable.parent == executable.parent.parent or executable.is_symlink():
        raise OSError("unsupported")
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(), ctypes.byref(created), ctypes.byref(exited),
                                  ctypes.byref(system), ctypes.byref(user)):
        raise ctypes.WinError(ctypes.get_last_error())
    script = work / "apply.ps1"
    shutil.copyfile(Path(__file__).with_name("windows_update.ps1"), script)
    request = work / "request.json"
    request.write_text(json.dumps(dict(package=str(package.resolve()), size=update.size,
        sha256=update.sha256, kind=update.kind, version=update.version,
        executable=str(executable), parent=os.getpid(),
        parent_started=str(created.dwLowDateTime | created.dwHighDateTime << 32))), encoding="utf-8")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    with (work / "helper.log").open("wb") as log:
        return subprocess.Popen([str(powershell), "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass", "-File", str(script), "-Request", str(request)],
            cwd=work, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW)
