# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\server_app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\config.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\database.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\auth.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\logger.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\routes_api.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\routes_admin.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\routes_payment.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\routes_admin_web.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\routes_referral.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\binance_pay.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\telegram_bot.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\server.py', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\server_config.json', '.'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\server\\templates', 'templates'), ('C:\\Users\\Administrator\\Desktop\\LEAKCHECK\\logo.ico', '.')],
    hiddenimports=['flask', 'flask.json', 'jinja2', 'config', 'database', 'auth', 'logger', 'routes_api', 'routes_admin', 'routes_payment', 'routes_admin_web', 'routes_referral', 'binance_pay', 'telegram_bot', 'server', 'requests'],
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
    name='LeakCheck_Server',
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
