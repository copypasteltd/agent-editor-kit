"""Materialize integrated recovery regressions before the batch test phase."""
import ast
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[2]


def main():
    source = (ROOT / 'docs/validation/validate_recovery66_candidate.py').read_text(encoding='utf-8')
    tree = ast.parse(source)
    cases = next(n for n in ast.walk(tree) if isinstance(n, ast.ClassDef) and n.name == 'RecoveryCases')
    text = textwrap.dedent('\n'.join(source.splitlines()[cases.lineno - 1:cases.end_lineno]))
    text = text.replace('class RecoveryCases', 'class IntegratedRecoveryTests')
    old = "self.root, _ = module.create_project(work / self._testMethodName, name='Disposable recovery candidate')"
    new = """temporary = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(temporary.cleanup)
        self.root, _ = module.create_project(Path(temporary.name) / '中文 工程', name='Integrated recovery')"""
    assert old in text
    text = text.replace(old, new)
    header = '''"""Real product recovery against disposable files, including the original defects."""
from pathlib import Path
import hashlib
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor import project as module
from ai_ad_editor.errors import AppError
from ai_ad_editor.runtime import configure_local_runtime


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(root):
    return {p.relative_to(root).as_posix(): sha(p) for p in root.rglob('*') if p.is_file()}


'''
    (ROOT / 'product/tests/test_transaction_preflight.py').write_text(header + text + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
