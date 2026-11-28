# -*- mode: python ; coding: utf-8 -*-
# Build with: uv run pyinstaller FlyNotes.spec --clean   →   dist/FlyNotes.exe

from PyInstaller.utils.hooks import copy_metadata


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    # Package metadata is bundled so fly_notes.__version__ works in the .exe.
    datas=[('assets/fly_notes.ico', 'assets')] + copy_metadata('fly-notes'),
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
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/fly_notes.ico',
)
