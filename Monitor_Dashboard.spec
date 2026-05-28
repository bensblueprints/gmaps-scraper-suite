# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/ADMIN/Desktop/gmaps-scraper-suite/monitor/app.py'],
    pathex=['C:/Users/ADMIN/Desktop/gmaps-scraper-suite', 'C:/Users/ADMIN/Desktop/gmaps-scraper-suite/monitor'],
    binaries=[],
    datas=[('C:/Users/ADMIN/AppData/Local/Programs/Python/Python311/Lib/site-packages/customtkinter', 'customtkinter')],
    hiddenimports=['shared', 'shared.config', 'data_manager', 'tkinter', 'tkinter.ttk'],
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
    name='Monitor_Dashboard',
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
)
