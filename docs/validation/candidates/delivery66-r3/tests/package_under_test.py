"""Bind test subprocesses/resources to the explicitly loaded product package."""
import os
from pathlib import Path
import ai_ad_editor

IMPORT_ROOT = Path(ai_ad_editor.__file__).resolve().parent.parent
requested = os.environ.get('AI_AD_EDITOR_TEST_PACKAGE_ROOT')
if requested:
    assert IMPORT_ROOT == Path(requested).resolve(), 'Test package differs from explicit source/install selection'
