"""PyInstaller launcher; normal launches use the existing application entry."""
import sys
import os
from pathlib import Path

_dll_directories = []
if getattr(sys, 'frozen', False):
    for folder in ('PySide6', 'shiboken6'):
        _dll_directories.append(os.add_dll_directory(str(Path(sys._MEIPASS) / folder)))

from calico_pet.app import main

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--release-check":
        try:
            from calico_pet.release_check import run
            code = run(sys.argv[2])
        except Exception:
            import json
            import traceback
            from pathlib import Path
            Path(sys.argv[2]).write_text(json.dumps({'ok': False, 'error': traceback.format_exc()}), encoding='utf-8')
            code = 1
        raise SystemExit(code)
    raise SystemExit(main())
