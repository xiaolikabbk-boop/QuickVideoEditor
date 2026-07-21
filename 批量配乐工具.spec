# -*- mode: python ; coding: utf-8 -*-
import os
import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

datas = []
ffmpeg_bin = os.environ.get('FFMPEG_BIN_DIR')
ffmpeg = Path(ffmpeg_bin, 'ffmpeg.exe') if ffmpeg_bin else Path(shutil.which('ffmpeg') or '')
ffprobe = Path(ffmpeg_bin, 'ffprobe.exe') if ffmpeg_bin else Path(shutil.which('ffprobe') or '')
if not ffmpeg.is_file() or not ffprobe.is_file():
    raise RuntimeError('找不到 ffmpeg.exe/ffprobe.exe，请设置 FFMPEG_BIN_DIR。')
binaries = [(str(ffmpeg), 'ffmpeg'), (str(ffprobe), 'ffmpeg')]
hiddenimports = []
tmp_ret = collect_all('customtkinter')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('tkinterdnd2')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
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
    [],
    exclude_binaries=True,
    name='批量配乐工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    version='.version_info.txt',
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='批量配乐工具',
)
