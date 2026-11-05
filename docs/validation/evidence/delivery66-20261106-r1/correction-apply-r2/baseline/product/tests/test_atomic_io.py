"""Real Windows atomic replacement against shared and non-delete-shared readers."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

import test_local_vace as native_fixtures
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, atomic_write_text, read_json_snapshot, shared_binary_reader


@unittest.skipUnless(sys.platform=='win32','Native Windows sharing')
class AtomicIoTests(unittest.TestCase):
    def setUp(self):
        configure_local_runtime()
        temporary=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.runtime/temp')
        self.addCleanup(temporary.cleanup);self.root=Path(temporary.name).resolve();self.path=self.root/'state.json'
        atomic_write_json(self.path,{'frames':1})

    def test_shared_snapshot_keeps_old_contents_during_actual_replacement(self):
        with shared_binary_reader(self.path) as reader:
            atomic_write_json(self.path,{'frames':2})
            self.assertEqual(json.loads(reader.read().decode('utf-8')),{'frames':1})
            self.assertEqual(read_json_snapshot(self.path),{'frames':2})

    def test_transient_reader_allows_json_and_text_after_retry(self):
        for writer,value in ((atomic_write_json,{'frames':3}),(atomic_write_text,'updated text')):
            close=native_fixtures.PipelineCleanupTests.open_reader_without_delete_sharing(self,self.path)
            timer=threading.Timer(.2,close);timer.start()
            try:writer(self.path,value)
            finally:timer.join(timeout=2)
            self.assertFalse(timer.is_alive())
            if isinstance(value,dict):self.assertEqual(read_json_snapshot(self.path),value)
            else:self.assertEqual(self.path.read_text(encoding='utf-8'),value)

    def test_other_process_keeps_old_snapshot_while_new_reads_see_replacements(self):
        child = "import sys;sys.path.insert(0,sys.argv[2]);from pathlib import Path;from ai_ad_editor.utils import shared_binary_reader;\nwith shared_binary_reader(Path(sys.argv[1])) as stream:\n print('ready',flush=True);sys.stdin.readline();print(stream.read().decode('utf-8'),flush=True)"
        process = subprocess.Popen([sys.executable,'-I','-B','-c',child,str(self.path),str(Path(__file__).resolve().parents[1]/'src')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
        try:
            self.assertEqual(process.stdout.readline().strip(),'ready')
            for frame in range(2,22):
                atomic_write_json(self.path,{'frames':frame})
                self.assertEqual(read_json_snapshot(self.path),{'frames':frame})
            stdout,stderr=process.communicate('\n',timeout=10)
            self.assertEqual(process.returncode,0,stderr)
            self.assertEqual(json.loads(stdout),{'frames':1})
        finally:
            if process.poll() is None:process.kill();process.communicate(timeout=10)

    def test_persistent_reader_preserves_target_and_cleans_staged_file(self):
        original=self.path.read_bytes()
        close=native_fixtures.PipelineCleanupTests.open_reader_without_delete_sharing(self,self.path)
        try:
            with self.assertRaises(PermissionError):atomic_write_json(self.path,{'frames':99})
            self.assertEqual(self.path.read_bytes(),original)
            self.assertEqual(list(self.root.glob('.state.json.*.tmp')),[])
        finally:close()

    def test_snapshot_budget_and_corrupt_json_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'budget'):read_json_snapshot(self.path,max_bytes=3)
        self.path.write_bytes(b'{broken')
        with self.assertRaises(ValueError):read_json_snapshot(self.path)


if __name__=='__main__':unittest.main()
