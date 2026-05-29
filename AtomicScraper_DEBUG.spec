# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\Users\\ADMIN\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\customtkinter', 'customtkinter'), ('C:\\Users\\ADMIN\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\playwright', 'playwright'), ('C:\\Users\\ADMIN\\Desktop\\gmaps-scraper-suite\\shared\\industries_data.json', 'shared'), ('C:\\Users\\ADMIN\\Desktop\\gmaps-scraper-suite\\shared\\cities.py', 'shared')]
binaries = []
hiddenimports = ['twilio', 'twilio.rest', 'shared', 'shared.config', 'shared.machine_id', 'atomicscraper.industries', 'engine', 'tkinter', 'tkinter.ttk']
tmp_ret = collect_all('playwright')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['atomicscraper\\app.py'],
    pathex=['.', 'scraper_node'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='AtomicScraper_DEBUG',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
