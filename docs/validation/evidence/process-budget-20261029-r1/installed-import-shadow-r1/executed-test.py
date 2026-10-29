"""Actual isolated-process bootstrap regressions, without a neural dependency install."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


WORKER = Path(__file__).resolve().parents[1]/'src/ai_ad_editor/semantic_worker.py'


class SemanticWorkerImportTests(unittest.TestCase):
    def test_own_application_and_native_model_dependencies_do_not_shadow_each_other(self):
        temp_root = WORKER.parents[2]/'.runtime/test-semantic-worker-imports'
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as directory:
            base = Path(directory)
            app_site = base/'application site'
            native_site = base/'native model site'
            app = app_site/'ai_ad_editor'
            app.mkdir(parents=True)
            native_site.mkdir()
            (app/'__init__.py').write_text("ORIGIN='owned application'\n", encoding='utf-8')
            (app_site/'numpy.py').write_text("ORIGIN='bundled controller dependency'\n", encoding='utf-8')
            (native_site/'numpy.py').write_text("ORIGIN='registered model runtime'\n", encoding='utf-8')
            rival = native_site/'ai_ad_editor'
            rival.mkdir()
            (rival/'__init__.py').write_text("raise RuntimeError('foreign application package imported')\n", encoding='utf-8')
            # Stop immediately after the real worker selects its own package
            # and its contract imports a model dependency. No model/network is
            # substituted into an inference test; this is the bootstrap oracle.
            (app/'semantic_contract.py').write_text(
                "import ai_ad_editor,json,numpy\n"
                "print(json.dumps(dict(application=ai_ad_editor.ORIGIN,dependency=numpy.ORIGIN)))\n"
                "raise SystemExit(0)\n", encoding='utf-8')
            worker = app/'semantic_worker.py'
            shutil.copyfile(WORKER, worker)
            code = ('import runpy,sys;sys.path.insert(0,'+repr(str(native_site))+');'
                    'runpy.run_path('+repr(str(worker))+",run_name='__main__')")
            result = subprocess.run([sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', '-c', code],
                                    capture_output=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
            self.assertEqual(json.loads(result.stdout),
                             dict(application='owned application', dependency='registered model runtime'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
