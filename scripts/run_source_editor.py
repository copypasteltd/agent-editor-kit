"""Explicit developer source entry. Never used as an installed Skill fallback."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'product/src'
sys.dont_write_bytecode = True
sys.path.insert(0, str(SOURCE))
import ai_ad_editor

if Path(ai_ad_editor.__file__).resolve() != SOURCE/'ai_ad_editor/__init__.py':
    raise RuntimeError('Developer entry loaded an unexpected package')

if __name__ == '__main__':
    from ai_ad_editor.cli import main
    raise SystemExit(main())
