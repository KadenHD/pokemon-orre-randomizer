# Native Windows widgets only. Keep a small, explicit Qt LGPL library surface.
from pathlib import Path
import os
import sys

root = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(root))
from colosseum_randomizer import APP_EXECUTABLE, __version__

native_codec = root / 'colosseum_randomizer/_native/colosseum_lzss.dll'
interface_pack = 'colosseum_randomizer/assets/game'
app_assets = root / 'colosseum_randomizer/assets/app'
if not native_codec.is_file():
    raise RuntimeError('Build the Rust codec first: python scripts/build_native.py')
if not (app_assets / 'icon.ico').is_file():
    raise RuntimeError('Build the application icon first: python scripts/build_app_icon.py')
data_files = [(str(app_assets / name), 'colosseum_randomizer/assets/app')
              for name in ('icon.ico', 'provenance.json')]
if os.environ.get('COLOSSEUM_BUNDLE_GAME_ASSETS', '1') == '1':
    data_files.append((str(root / interface_pack), interface_pack))
a = Analysis([str(root / 'scripts/desktop_entry.py')], pathex=[str(root)],
             binaries=[(str(native_codec), 'colosseum_randomizer/_native')],
             datas=data_files,
             hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['PySide6.QtQml', 'PySide6.QtQuick',
                                        'PySide6.QtWebEngineCore', 'tkinter'],
             noarchive=False, optimize=0)

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
