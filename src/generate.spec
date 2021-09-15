# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

datas = [
    (
        "C:/Users/dkozlov/.virtualenvs/edc-charts-3xEQx6NU/Lib/site-packages/altair/vegalite/v4/schema/vega-lite-schema.json",
        "./altair/vegalite/v4/schema/"
    )
]

a = Analysis(['generate.py'],
             pathex=['D:\\python\\.msdk\\edc-charts\\src'],
             binaries=[],
             datas=datas,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='generate',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )
