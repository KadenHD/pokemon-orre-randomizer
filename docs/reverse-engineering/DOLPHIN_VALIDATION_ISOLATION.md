# Isolation and closure status of Dolphin trials

Search of October 31, 2026. The local binary bears the tag UI Dolphin 2609a. The official sources of
tag 2609a were recovered at commit `409881c34357d0f105fd473167d15ab0bd9c1628`, with their SHA-256 in
the local manifest `build/dolphin-validation/references-isolation/manifest.json`. The binary is
imprinted separately at each trial. This search does not purport to establish a compilation
equivalence between binary and sources.

## What the code establishes

The option `-u`/`--user` is declared by
[CommandLineParse.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/UICommon/CommandLineParse.cpp).
In
[Main.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/DolphinQt/Main.cpp),
`SetUserDirectory` receives this path before the initialization of the configurations and
`Settings`. The explicit directory is given priority over the Windows folding mechanisms. The
`portable.txt` file requires a fallback in `User/` next to the executable when no explicit path is
provided.
[UICommon.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/UICommon/UICommon.cpp)

`Settings::GetQSettings` place `Qt.ini` under the configuration directory from the user path.
[Settings.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/DolphinQt/Settings.cpp)
The paths rebuilt by Dolphin place the SRAM GameCube in its user GC directory. The boot
configuration uses this path.
[FileUtil.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Common/FileUtil.cpp),
[ConfigManager.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/ConfigManager.cpp)

A memory card path indicated in an INI may, however, target a file external to the profile.
Therefore, the argument `-u` alone does not replace the check of configured paths.

The normal end of `MainWindow::OnStopComplete`, when an output is requested, calls
`QGuiApplication::exit(0)`.
[MainWindow.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/DolphinQt/MainWindow.cpp)
`Main.cpp` returns the result of the Qt loop. Some boot failures explicitly produce 1. These static
observations are not enough to explain the status 1 of the former launcher after a played session.

## Corrections to the validation device

`scripts/run_dolphin_validation.py` directly launches a list of arguments by `subprocess.Popen`,
without intermediate shell. It lists the PID, arguments, paths and status `running` in a JSON
report, then the true `return_code` of the process and its hexadecimal equivalent when closed.
Readers can follow JSON atomic updates. Stdout/stderr captures remain in two associated files. An
existing file is refused. The status of the monitor is distinct from the recorded native code.

The launcher requires a copy of Dolphin with `portable.txt`, a prepared profile and a report located
under `build/`. The physically linked symbolic links, junctions and files are refused for validation
targets. The known editable paths of the INI configuration and game must remain in the trial
profile. The native non-assignment line gecco sections are accepted without allowing external
redirections of memory card.

The game image, the executable and the additional protected files are printed before and after. The
entire personal profile is inventoried, beyond the only Config/GC folders. No automatic shutdown or
forced restoration of personal file is performed. The results of a interrupted session are not
presented as a final audit. The hashes prove a stability of the files monitored over the interval,
not the absence of any system activity or the proper functioning of each scenario of the game.

`scripts/start_dolphin_test.ps1` now delegates to this monitor. By default, it uses the
`build/dolphin-validation/portable/Dolphin.exe` copy, accepts an explicit copy path, and returns the
status of the monitor. The native process code is read in the JSON report. No emulator is included
in the distributions.

Example, after preparation of the portable copy and test profile.

```powershell
python scripts/run_dolphin_validation.py --emulator build/dolphin-validation/portable/Dolphin.exe --iso build/v05-qa/unchanged.iso --profile build/dolphin-validation/profiles/baseline-empty --report build/dolphin-validation/baseline-empty-run.json
```

Choose a new report name at each repetition. The option `--protect-file` can be repeated to add the
original images and the original installation of Dolphin to the audit, in addition to the mounted
image and the clone already monitored. `--debugger` opens the debugger panels when the scenario
requires it.

## First controlled observation

On an ISO strictly identical to the original, an empty profile and D3D12, the observed process PID
30268 ended with the native code **0** after closing by the interface. The monitor confirmed the
unchanged protected files and the **46 files of the personal profile unchanged**. Local proof:
`build/dolphin-validation/baseline-empty-run.json`.

This observation does not duplicate the former status 1 and does not establish the cause
retroactively. Tests with copied maps and randomized images are recorded in their separate reports
and in the main validation report.

## Windows events and context comparison

A targeted reading of the events Application Error / Windows Error Reporting for `Dolphin.exe` over
the previous 48 hours found real reports `APPCRASH`, missing from the Dolphin text journal. The
private file `build/dolphin-validation/dolphin-windows-errors.json` keeps the 12 filtered events,
SHA-256 `a2fd75282984acc9efb184c0e83daf8d80251ea969dacfec20c2ca74dc113e81`.

| Local time October 31st | Process and path | Module and exception |
| --- | --- | --- |
| 11:37:32 to 11:37:35 | PID 10276 (`0x2824`), `Dolphin-x64/Dolphin.exe` | `ntdll.dll`, `0xc0000008` |
| 11:45:43 | Same PID and same path | `XInputUap.dll`, `0xc0000005`, offset `0x22c7` |

These schedules are consistent with the old copied card session, of which the Dolphin newspaper had
been created at 11:37:32. The old launcher did not record the PID. The exact link with its code 1
remains a temporal correlation. Windows reports establish a native Dolphin anomaly in these modules.
They do not demonstrate that the randomized data or backup are the cause. Without the chosen call
stack, the fault module is not enough to designate a root cause in Dolphin, Windows or a driver.

The test clone then launched in the non-AppContainer desktop context, PID 8140, loaded
`C:\WINDOWS\SYSTEM32\DINPUT8.dll`] and `C:\WINDOWS\SYSTEM32\xinput1_4.dll`. `XInputUap.dll` was not
included in this targeted inventory. Local proof:
`build/dolphin-validation/host-input-modules.json`. This difference provides a verifiable
environmental track. It does not alone prove a resolution of the closure crash.

In pinned sources, the Win32 backend initializes XInput globally, even if the selected controller
uses DInput. Its uninstallation releases the DLL. No INI key to disable this backend is present in
the inspected functions. Writing an invented option would not constitute a correction.
[Win32.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/InputCommon/ControllerInterface/Win32/Win32.cpp),
[XInput.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/InputCommon/ControllerInterface/XInput/XInput.cpp)
The controller's four sources are stored with their fingerprints in
`references-isolation/controller-manifest.json`, under the local QA folder.

For debugger testing, run the Dolphin monitor and its GDB client in the same context out of
AppContainer desktop avoids local loop blocking observed in the container. No AppContainer network
exemption or other Windows setting ns has been changed. The debugging launch remained blocked in the
container has been explicitly stopped as an abandoned diagnostic trial. Its status `0xffffffff`
should not be counted as a normal closing test.

The verifiable correction of the device is therefore an isolated and identified launch, with valid
stdout/stderr channels, complete monitoring of originals, consistent debugging context and recorded
native codes. The following actual closures on blank image and randomized image remain decisive
observations to judge the stability of the chosen context.

## Savestates during GDB shutdown

A status backup requested in the interface calls `State::SaveAs`, then `Core::RunOnCPUThread`. When
the heart is started, this operation puts serialization on hold on the thread CPU.
[State.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/State.cpp#L458),
[Core.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/Core.cpp#L767)

The thread CPU stopped by GDB waits in `ProcessCommands(true)`. It does not empty this file during
this wait. In addition to the code, a backup can remain outstanding until the GDB client resumes.
The reference to the metadata of savestates also takes a lock that awaits the end of the backup
tasks, which can temporarily block the interface. For fixtures, create the status before the
dialogue of the PNJ, or during an ordinary pause, then install the breakpoints.
[CPU.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/HW/CPU.cpp#L145),
[State.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/State.cpp#L562)

## Closing of private fixtures

The local helper `build/dolphin-validation/finalize_validation.py` refuses any correction if a
Dolphin process is running again or if the control is running in AppContainer. It compares the
initial fingerprints of the 2011 game files, 2691 files from the original installation, 46 personal
files and two source images. It never restores a personal file.

After the tests have stopped, its option `--apply` keeps a copy of the binary and INI test, restores
the only official clone, then disables GDB, debugger mode and the cheats of private profiles. A new
trial without debugger must then end normally, then an audit without `--apply` closes the check. The
states built for fixtures remain in the private folders of QA.

## Automatic checks

Nine targeted tests pass in `tests/test_dolphin_validation.py`: exact transmission of paths with
shellless spaces, non-zero native code, fingerprints of the entire profile, detection of
modification or disappearance of a file, refusal of external paths and material links, absence of
replacement of a report, and control of map paths in game-specific INIs.

Five private tests of the finaliser cover refusal of an active process, clone-limited restoration,
blocking if an original has changed, refusal to overwrite a report and lack of correction in audit
alone. These tests use temporary files and simulated inventories.
