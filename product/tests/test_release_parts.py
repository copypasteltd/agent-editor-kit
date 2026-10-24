"""A corrupt or incomplete download must never produce a usable release ZIP."""
from pathlib import Path
import hashlib
import importlib.util
import json
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('look_parts',Path(__file__).resolve().parents[2]/'scripts/assemble_look500_release.py')
parts=importlib.util.module_from_spec(spec);spec.loader.exec_module(parts)


class ReleasePartTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[1]/'.runtime/parts-tests'
        root.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=root);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.output=self.root/'out/release.zip'
        chunks=[b'first ZIP segment\x00\xff',b'second ZIP segment']
        rows=[]
        for i,chunk in enumerate(chunks,1):
            name=f'aek.zip.part{i:02}';(self.root/name).write_bytes(chunk)
            rows.append({'name':name,'bytes':len(chunk),'sha256':hashlib.sha256(chunk).hexdigest()})
        self.full=b''.join(chunks)
        (self.root/'parts.json').write_text(json.dumps({'parts':rows,'bytes':len(self.full),'sha256':hashlib.sha256(self.full).hexdigest()}),encoding='utf-8')

    def test_exact_binary_reassembly_and_repeat_preserve_output(self):
        parts.assemble(self.root,self.output)
        self.assertEqual(self.output.read_bytes(),self.full)
        self.assertTrue(parts.assemble(self.root,self.output)['already_assembled'])

    def test_corruption_and_missing_part_never_publish_output(self):
        path=self.root/'aek.zip.part02';original=path.read_bytes();path.write_bytes(b'corrupt')
        with self.assertRaises(ValueError):parts.assemble(self.root,self.output)
        self.assertFalse(self.output.exists())
        path.unlink()
        with self.assertRaises(OSError):parts.assemble(self.root,self.output)
        self.assertFalse(self.output.exists())
        path.write_bytes(original);self.output.parent.mkdir();self.output.write_bytes(b'keep user file')
        with self.assertRaises(ValueError):parts.assemble(self.root,self.output)
        self.assertEqual(self.output.read_bytes(),b'keep user file')
