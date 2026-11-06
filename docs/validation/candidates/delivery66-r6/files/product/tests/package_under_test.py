"""Bind test subprocesses/resources to the explicitly loaded product package."""
import os
import sys
from pathlib import Path
import ai_ad_editor

IMPORT_ROOT = Path(ai_ad_editor.__file__).resolve().parent.parent
requested = os.environ.get('AI_AD_EDITOR_TEST_PACKAGE_ROOT')
if requested:
    assert IMPORT_ROOT == Path(requested).resolve(), 'Test package differs from explicit source/install selection'


# Embedded native Python may ignore PYTHONPATH. Each child binds the exact
# source/installed package already selected by its parent test process.
_CHILD_PACKAGE_BINDING = """import sys
from pathlib import Path
_test_package_root = Path(sys.argv.pop(1)).resolve(strict=True)
sys.path.insert(0, str(_test_package_root))
import ai_ad_editor
if Path(ai_ad_editor.__file__).resolve() != _test_package_root / 'ai_ad_editor' / '__init__.py':
    raise RuntimeError('Child imported a different application package')
"""


def module_command(*arguments: str, force_ascii_stdio: bool = False) -> list[str]:
    """Run the actual package __main__, preserving the explicit test target."""
    program = _CHILD_PACKAGE_BINDING
    if force_ascii_stdio:
        # Establish the adversarial pipe encoding even when Python ignores
        # PYTHONIOENCODING; the real CLI must perform its own UTF-8 repair.
        program += """for _test_stream in (sys.stdout, sys.stderr):
    _test_stream.reconfigure(encoding='ascii', errors='strict')
    if _test_stream.encoding != 'ascii' or _test_stream.errors != 'strict':
        raise RuntimeError('ASCII pipe precondition was not established')
"""
    program += "import runpy\nrunpy.run_module('ai_ad_editor', run_name='__main__', alter_sys=True)\n"
    return [sys.executable, '-B', '-c', program, str(IMPORT_ROOT), *arguments]


def utf8_script_command(script: str) -> list[str]:
    """Run a UTF-8 test child script against the explicit application package."""
    program = _CHILD_PACKAGE_BINDING + "exec(compile(sys.argv.pop(1), '<explicit-package-script>', 'exec'))\n"
    return [sys.executable, '-B', '-X', 'utf8', '-c', program, str(IMPORT_ROOT), script]
