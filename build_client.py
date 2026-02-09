"""
Build script — LEAKCHECK Client .exe
Generates a .spec and builds via PyInstaller for full control over Tcl/Tk bundling.
Run from the project root:  python build_client.py
"""

import os
import sys
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
PY_DIR = sys.base_prefix          # real Python install, not the venv Scripts/ dir
DLLS   = os.path.join(PY_DIR, "DLLs")

# ── Paths ──
SPEC   = os.path.join(HERE, "LeakCheck.spec")
DIST   = os.path.join(HERE, "dist")
BUILD  = os.path.join(HERE, "build")

# ── Tcl/Tk source paths ──
TCL_DIR = os.path.join(PY_DIR, "tcl", "tcl8.6")
TK_DIR  = os.path.join(PY_DIR, "tcl", "tk8.6")

# ── Write the spec file manually for full control ──
spec_content = f'''# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    [{repr(os.path.join(HERE, 'leakcheck.py'))}],
    pathex=[{repr(HERE)}],
    binaries=[
        ({repr(os.path.join(DLLS, 'tcl86t.dll'))}, '.'),
        ({repr(os.path.join(DLLS, 'tk86t.dll'))}, '.'),
        ({repr(os.path.join(DLLS, '_tkinter.pyd'))}, '.'),
    ],
    datas=[
        ({repr(os.path.join(HERE, 'config_client.py'))}, '.'),
        ({repr(os.path.join(HERE, 'api_client.py'))}, '.'),
        ({repr(os.path.join(HERE, 'gui.py'))}, '.'),
        ({repr(os.path.join(HERE, 'logo.ico'))}, '.'),
        ({repr(TCL_DIR)}, '_tcl_data'),
        ({repr(TK_DIR)}, '_tk_data'),
    ],
    hiddenimports=[
        'config_client', 'api_client', 'gui',
        'requests', 'hashlib', 'tkinter', '_tkinter',
    ],
    hookspath=[],
    hooksconfig={{}},
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
    name='LeakCheck',
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
    icon=[{repr(os.path.join(HERE, 'logo.ico'))}],
)
'''

with open(SPEC, "w") as f:
    f.write(spec_content)
print(f"[OK] Spec written -> {SPEC}")

# ── Clean previous build ──
if os.path.isdir(BUILD):
    shutil.rmtree(BUILD, ignore_errors=True)
client_exe = os.path.join(DIST, "LeakCheck.exe")
if os.path.isfile(client_exe):
    try:
        os.remove(client_exe)
    except OSError:
        pass

# ── Build ──
import PyInstaller.__main__
PyInstaller.__main__.run([
    SPEC,
    "--distpath", DIST,
    "--workpath", BUILD,
    "--noconfirm",
])

print(f"\n[OK] Client .exe built -> dist/LeakCheck.exe")
