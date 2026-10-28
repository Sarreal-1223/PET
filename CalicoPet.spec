from pathlib import Path
import struct

if struct.calcsize('P') != 8:
    raise RuntimeError('Build requires 64-bit Python')
root = Path(SPECPATH)
onefile = __import__('os').environ.get('CALICOPET_ONEFILE') == '1'
a = Analysis([str(root / 'packaging' / 'launcher.py')],
             pathex=[str(root / 'src')],
             datas=[(str(p), 'assets') for p in sorted((root / 'assets').rglob('*.png'))],
             binaries=[], hiddenimports=[], hookspath=[], hooksconfig={},
             runtime_hooks=[], excludes=['PySide6.QtTest'], noarchive=False)
# Qt 6.12 uses the Windows ICU ABI. A third-party ICU on the build machine's
# PATH can share the filename but export incompatible, versioned symbols.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.lower() not in {'icuuc.dll', 'icudt78.dll'}]
pyz = PYZ(a.pure)
if onefile:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='CalicoPet',
              console=False, debug=False, strip=False, upx=False)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='CalicoPet',
              console=False, debug=False, strip=False, upx=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='CalicoPet')
