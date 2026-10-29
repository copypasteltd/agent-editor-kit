"""Execute actual native worker entry bootstraps, without loading neural models."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

import ai_ad_editor


PACKAGE = Path(ai_ad_editor.__file__).resolve().parent
CONTRACTS = {
    'enhancement': 'rvm_worker', 'interpolation': 'rvm_worker', 'lama': 'rvm_worker',
    'lipsync': 'rvm_worker', 'sam2': 'rvm_worker', 'vace': 'rvm_worker',
    'rvm': 'local_matting', 'face': 'local_face', 'ocr': 'local_ocr',
    'yolo': 'local_vision', 'demucs': 'local_separation', 'ctc': 'whisper_worker',
    'vace_session': 'model_session', 'stem_separation': 'demucs_worker',
    'whisper': 'local_asr',
}


def probe(worker_name, *, preloaded_foreign=False):
    base = Path(__file__).resolve().parents[1]/'.runtime/test-native-worker-imports'
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base) as directory:
        root = Path(directory)
        app_site, native_site = root/'application site', root/'native model site'
        app = app_site/'ai_ad_editor'
        app.mkdir(parents=True)
        native_site.mkdir()
        (app/'__init__.py').write_text("ORIGIN='owned application'\n", encoding='utf-8')
        (app_site/'numpy.py').write_text("ORIGIN='bundled controller dependency'\n", encoding='utf-8')
        (native_site/'numpy.py').write_text("ORIGIN='registered model runtime'\n", encoding='utf-8')
        foreign = native_site/'ai_ad_editor'
        foreign.mkdir()
        (foreign/'__init__.py').write_text("ORIGIN='foreign application'\n", encoding='utf-8')
        # Stop at the first owned contract import, before every neural/file
        # processing operation. This tests bootstrap ownership, not inference.
        (app/(CONTRACTS[worker_name]+'.py')).write_text(
            "import ai_ad_editor,json,numpy\n"
            "print(json.dumps(dict(application=ai_ad_editor.ORIGIN,dependency=numpy.ORIGIN)))\n"
            "raise SystemExit(0)\n", encoding='utf-8')
        name = worker_name+'_worker.py'
        worker = app/name
        shutil.copyfile(PACKAGE/name, worker)
        match = re.search(r'''(?m)^PROTOCOL\s*=\s*['"]([^'"]+)['"]''', worker.read_text('utf-8'))
        payload = dict(network='disabled', runtime_root=str(root/'runtime'),
                       response=str(root/'response.json'), native=dict(runtime_root=str(root/'runtime')),
                       protocol=match[1] if match else 'agent-hdemucs-four-stems-v1')
        request = root/'request.json'
        request.write_text(json.dumps(payload), encoding='utf-8')
        code = ('import runpy,sys;sys.path.insert(0,'+repr(str(native_site))+');'
                + ('import ai_ad_editor;' if preloaded_foreign else '')
                + 'sys.argv=['+repr(str(worker))+','+repr(str(request))+'];'
                + 'runpy.run_path('+repr(str(worker))+",run_name='__main__')")
        stdin = (json.dumps(payload).encode() if worker_name == 'yolo' else
                 b'run\n' if worker_name in ('face', 'ocr') else b'')
        result = subprocess.run([sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', '-c', code],
                                input=stdin, capture_output=True, timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        response = root/'response.json'
        result.worker_response = response.read_bytes() if response.exists() else b''
        return result


class NativeWorkerImportTests(unittest.TestCase):
    pass


def isolation_test(name):
    def test(self):
        result = probe(name)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', 'replace'))
        self.assertEqual(json.loads(result.stdout),
                         dict(application='owned application', dependency='registered model runtime'))
    return test


def foreign_test(name):
    def test(self):
        result = probe(name, preloaded_foreign=True)
        # Workers may catch and serialize this error in their normal protocol,
        # or reject before their response wrapper. Both must refuse ownership.
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'NATIVE_WORKER_APPLICATION_CHANGED',
                      result.stdout+result.stderr+result.worker_response)
        self.assertNotIn(b'"dependency": "registered model runtime"', result.stdout)
    return test


for name in CONTRACTS:
    setattr(NativeWorkerImportTests, 'test_'+name+'_native_dependencies', isolation_test(name))
    setattr(NativeWorkerImportTests, 'test_'+name+'_preloaded_foreign_rejected', foreign_test(name))


if __name__ == '__main__':
    unittest.main(verbosity=2)
