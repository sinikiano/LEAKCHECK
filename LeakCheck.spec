# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\leakcheck.py'],
    pathex=['C:\\Users\\Administrator\\Desktop\\LEAKCHECK'],
    binaries=[
        ('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\DLLs\\tcl86t.dll', '.'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\DLLs\\tk86t.dll', '.'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\DLLs\\_tkinter.pyd', '.'),
    ],
    datas=[
        ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\config_client.py', '.'),
        ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\api_client.py', '.'),
        ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\gui.py', '.'),
        ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\logo.ico', '.'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\tcl\\tcl8.6', '_tcl_data'),
        ('C:\\Users\\Administrator\\AppData\\Local\\Python\\pythoncore-3.14-64\\tcl\\tk8.6', '_tk_data'),
    ],
    hiddenimports=[
        'config_client', 'api_client', 'gui',
        'requests', 'hashlib', 'tkinter', '_tkinter',
    ],
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
    icon=['C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\logo.ico'],
)
