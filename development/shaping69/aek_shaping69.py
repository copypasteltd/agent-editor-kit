"""Independent development CLI; never substitutes for the installed product."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE / 'src'), str(HERE.parent / 'text68/src')]
from aek_shaping.cli import main

if __name__ == '__main__':
    raise SystemExit(main())
