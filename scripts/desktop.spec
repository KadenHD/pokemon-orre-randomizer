# Native Windows widgets only. Keep a small, explicit Qt LGPL library surface.
from pathlib import Path
import os
import sys

root = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(root))
from orre_randomizer import APP_EXECUTABLE, __version__
from scripts.build_desktop import REQUIRED_RUNTIME_MODULES, REQUIRED_IMAGE_DECODERS, validate_native_runtime

validate_native_runtime()

native_codec = root / 'orre_randomizer/_native/orre_lzss.dll'
disc_codec = root / 'orre_randomizer/_native/orre_disc.dll'
music_codec = root / 'orre_randomizer/_native/orre_musyx.dll'
launcher = root / 'orre_randomizer/_native/OrreLauncher.exe'
interface_pack = 'orre_randomizer/assets/game'
app_assets = root / 'orre_randomizer/assets/app'
if not native_codec.is_file() or not disc_codec.is_file():
    raise RuntimeError('Build the Rust codec first: python scripts/build_native.py')
if not music_codec.is_file() or not launcher.is_file():
    raise RuntimeError('Build the launcher and music renderer: python scripts/build_native.py')
if not (app_assets / 'icon.ico').is_file():
    raise RuntimeError('Build the application icon first: python scripts/build_app_icon.py')
data_files = [(str(app_assets / name), 'orre_randomizer/assets/app')
              for name in ('icon.ico', 'provenance.json', 'logo.png', 'logo.json', 'controller.png', 'controller.json')]
data_files.append((str(root / 'orre_randomizer/windows_update.ps1'), 'orre_randomizer'))
data_files += [(str(launcher), 'orre_randomizer/_native'),
               (str(music_codec.with_suffix('.json')), 'orre_randomizer/_native')]
if os.environ.get('ORRE_BUNDLE_GAME_ASSETS', os.environ.get('COLOSSEUM_BUNDLE_GAME_ASSETS', '1')) == '1':
    data_files.append((str(root / interface_pack), interface_pack))
a = Analysis([str(root / 'scripts/desktop_entry.py')], pathex=[str(root)],
             binaries=[(str(native_codec), 'orre_randomizer/_native'),
                       (str(disc_codec), 'orre_randomizer/_native'),
                       (str(music_codec), 'orre_randomizer/_native')],
             datas=data_files,
             hiddenimports=sorted(REQUIRED_IMAGE_DECODERS), hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['PySide6.QtQml', 'PySide6.QtQuick',
                                        'PySide6.QtWebEngineCore', 'tkinter'],
             noarchive=False, optimize=0)

missing_runtime_modules = (REQUIRED_RUNTIME_MODULES | REQUIRED_IMAGE_DECODERS) - {entry[0] for entry in a.pure}
if missing_runtime_modules:
    raise RuntimeError('Required game-folder modules are not frozen: ' + ', '.join(sorted(missing_runtime_modules)))

qt_libraries = {'qt6core.dll', 'qt6gui.dll', 'qt6widgets.dll', 'qt6network.dll',
                'qt6opengl.dll', 'qt6svg.dll'}
qt_plugins = {'qwindows.dll', 'qoffscreen.dll', 'qmodernwindowsstyle.dll',
              'qgif.dll', 'qico.dll', 'qjpeg.dll', 'qsvg.dll', 'qsvgicon.dll',
              'qnetworklistmanager.dll', 'qcertonlybackend.dll', 'qschannelbackend.dll'}
def required(entry):
    destination = entry[0].replace('\\', '/').lower()
    filename = destination.rsplit('/', 1)[-1]
    if '/plugins/' in destination and destination.startswith('pyside6/'):
        return filename in qt_plugins
    if filename.startswith('qt6') and filename.endswith('.dll'):
        return filename in qt_libraries
    # Qt 6 on supported Windows uses the operating system's unversioned ICU API.
    # Never shadow it with a developer tool's differently versioned ICU library.
    if filename in {'icuuc.dll', 'icuin.dll'} or filename.startswith('icudt'):
        return False
    # Native QWidget rendering does not use the optional software OpenGL driver.
    return filename != 'opengl32sw.dll'
a.binaries = [entry for entry in a.binaries if required(entry)]

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=APP_EXECUTABLE,
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None,
          icon=str(app_assets / 'icon.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name=f'{APP_EXECUTABLE}-{__version__}')
