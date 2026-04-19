# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for Model Manager
# Build: pyinstaller model_manager.spec

import sys
from pathlib import Path

block_cipher = None

# Collect customtkinter assets (themes, images)
import customtkinter
ctk_path = Path(customtkinter.__file__).parent
ctk_datas = [(str(ctk_path), "customtkinter")]

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=[
        "paramiko",
        "paramiko.transport",
        "paramiko.auth_handler",
        "cryptography",
        "bcrypt",
        "customtkinter",
        "darkdetect",
        "PIL",
        "PIL.Image",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "unittest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="model-manager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,       # No terminal window on launch
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",  # Uncomment and add icon file when ready
)
