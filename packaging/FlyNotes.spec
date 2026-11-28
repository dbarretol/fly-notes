# -*- mode: python ; coding: utf-8 -*-
# Build with: uv run pyinstaller packaging/FlyNotes.spec --clean   →   dist/FlyNotes.exe

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

# Paths are relative to the project root, not to the directory PyInstaller is run from.
ROOT = Path(SPECPATH).resolve().parent.parent
ICON = ROOT / 'assets' / 'fly_notes.ico'

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=[],
    # Package metadata is bundled so fly_notes.__version__ works in the .exe.
    datas=[(str(ICON), 'assets')] + copy_metadata('fly-notes'),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FlyNotes',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON),
)
