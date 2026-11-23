"""Read-only emulator ownership checks for card restore and cache maintenance."""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys

from .service import UserError


def dolphin_arguments():
    if sys.platform == "win32":
        # Fixed read-only query. No path or user input is interpolated into shell code.
        script = ("[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
                  "Get-CimInstance Win32_Process -Filter \"Name = 'Dolphin.exe'\" -ErrorAction Stop | "
                  "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress")
        try:
            powershell = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
            result = subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, timeout=12, check=True, creationflags=0x08000000)
            rows = json.loads(result.stdout.decode("utf-8-sig").strip() or "[]")
            rows = rows if isinstance(rows, list) else [rows]
            shell = ctypes.WinDLL("shell32", use_last_error=True)
            shell.CommandLineToArgvW.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
            shell.CommandLineToArgvW.restype = ctypes.POINTER(ctypes.c_wchar_p)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.LocalFree.argtypes = [ctypes.c_void_p]
            output = []
            for row in rows:
                command = row.get("CommandLine")
                if not command:
                    output.append(None); continue
                count = ctypes.c_int()
                argv = shell.CommandLineToArgvW(command, ctypes.byref(count))
                if not argv:
                    raise OSError("Unreadable process arguments")
                try:
                    output.append([argv[i] for i in range(count.value)])
                finally:
                    kernel.LocalFree(argv)
            return output
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            raise UserError("Impossible de vérifier si Dolphin est fermé. Fermez Dolphin puis réessayez.") from error
    if sys.platform.startswith("linux"):
        result = []
        for proc in Path("/proc").iterdir():
            if not proc.name.isdecimal():
                continue
            try:
                name = (proc / "comm").read_text().strip().lower()
                if name.startswith("dolphin"):
                    if name in ("dolphin", "dolphin-emu", "dolphin.exe"):
                        command = (proc / "cmdline").read_bytes().split(b"\0")
                        result.append([os.fsdecode(p) for p in command if p])
            except FileNotFoundError:
                continue
            except PermissionError as error:
                raise UserError("Impossible de vérifier si Dolphin est fermé. Fermez Dolphin puis réessayez.") from error
        return result
    raise UserError("Impossible de vérifier si Dolphin est fermé. Fermez Dolphin puis réessayez.")


def assert_dolphin_idle(folder=None, manifest=None):
    for argv in dolphin_arguments():
        if folder is None or not argv:
            raise UserError("Fermez Dolphin avant de gérer les sauvegardes ou les caches.")
        profile = Path(folder) / "DolphinUser"
        profiles = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg in ("-u", "--user")]
        profiles += [arg.split("=", 1)[1] for arg in argv if arg.startswith("--user=")]
        rom = Path(folder) / manifest["rom"] if manifest else None
        same_profile = any(Path(value).resolve() == profile.resolve() for value in profiles)
        same_rom = rom is not None and any(Path(value).resolve() == rom.resolve() for value in argv[1:]
                                          if value and not value.startswith("-"))
        if not profiles or same_profile or same_rom:
            raise UserError("Fermez Dolphin avant de gérer les sauvegardes ou les caches.")
