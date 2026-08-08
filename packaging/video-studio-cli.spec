# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

app_root = Path(SPECPATH).resolve().parent
backend_root = app_root / "backend"

analysis = Analysis(
    [str(backend_root / "omniops-video-studio-cli.py")],
    pathex=[str(backend_root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="omniops-video-studio-cli",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="x86_64",
)
