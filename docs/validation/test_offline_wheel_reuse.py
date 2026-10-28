"""Exercise exact-payload reuse refusals without building or installing a package."""
import hashlib,json,runpy,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
API=runpy.run_path(str(ROOT/'product/offline/build.py'))
PROJECT='''[tool.setuptools.package-data]
ai_ad_editor = ["data/*.bin"]
'''
class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'local/tmp');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.package=self.root/'source';self.package.mkdir()
        (self.package/'__init__.py').write_bytes(b"VERSION='1.2.3'\n")
        (self.package/'data').mkdir();(self.package/'data/asset.bin').write_bytes(b'actual payload')
        self.wheel=self.root/'ai_ad_editor-1.2.3-py3-none-win_amd64.whl'
    def create(self,changes=None,alias=False):
        prefix='ai_ad_editor-1.2.3.data/purelib/ai_ad_editor/'
        files={prefix+p.relative_to(self.package).as_posix():p.read_bytes() for p in self.package.rglob('*') if p.is_file()}
        files.update({'ai_ad_editor-1.2.3.dist-info/METADATA':b'Name: ai-ad-editor\nVersion: 1.2.3\n',
            'ai_ad_editor-1.2.3.dist-info/WHEEL':b'Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: py3-none-win_amd64\n',
            'ai_ad_editor-1.2.3.dist-info/RECORD':b''})
        for key,value in (changes or {}).items():
            if value is None:files.pop(key)
            else:files[key]=value
        if alias:files['ai_ad_editor/__init__.py']=b"VERSION='1.2.3'\n"
        with zipfile.ZipFile(self.wheel,'w') as archive:
            for name,content in files.items():archive.writestr(name,content)
        return 'sha256:'+hashlib.sha256(self.wheel.read_bytes()).hexdigest()
    def validate(self,pin):return API['validate_product_wheel'](self.wheel,'1.2.3',PROJECT,self.package,pin)
    def test_exact_data_scheme_payload_is_accepted(self):
        result=self.validate(self.create());self.assertEqual(result['payload_files'],2);self.assertTrue(result['payload_byte_exact'])
    def test_pin_mismatch_is_refused(self):
        self.create()
        with self.assertRaisesRegex(ValueError,'digest'):self.validate('sha256:'+'0'*64)
    def test_missing_pin_is_refused(self):
        self.create()
        with self.assertRaisesRegex(ValueError,'explicit'):self.validate(None)
    def test_modified_current_source_is_refused(self):
        pin=self.create();(self.package/'data/asset.bin').write_bytes(b'changed value')
        with self.assertRaisesRegex(ValueError,'differs'):self.validate(pin)
    def test_missing_current_resource_is_refused(self):
        pin=self.create({'ai_ad_editor-1.2.3.data/purelib/ai_ad_editor/data/asset.bin':None})
        with self.assertRaisesRegex(ValueError,'Incomplete'):self.validate(pin)
    def test_unexpected_payload_is_refused(self):
        pin=self.create({'ai_ad_editor-1.2.3.data/purelib/ai_ad_editor/old.py':b'old'})
        with self.assertRaisesRegex(ValueError,'Unexpected'):self.validate(pin)
    def test_alias_destination_is_refused(self):
        pin=self.create(alias=True)
        with self.assertRaisesRegex(ValueError,'duplicate'):self.validate(pin)
    def test_parent_traversal_is_refused(self):
        pin=self.create({'../outside':b'unsafe'})
        with self.assertRaisesRegex(ValueError,'Unsafe'):self.validate(pin)
    def test_metadata_version_is_refused(self):
        pin=self.create({'ai_ad_editor-1.2.3.dist-info/METADATA':b'Name: ai-ad-editor\nVersion: 0.0.0\n'})
        with self.assertRaisesRegex(ValueError,'metadata'):self.validate(pin)

if __name__=='__main__':
    out=ROOT/'docs/validation/evidence/aces-delivery-20261029-r1/wheel-reuse-tests-r1';out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    with (out/'tests.txt').open('w',encoding='utf-8') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ReuseTests))
    report=dict(status='passed' if r.wasSuccessful() else 'failed',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),builder_sha256=hashlib.sha256((ROOT/'product/offline/build.py').read_bytes()).hexdigest())
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report));assert r.wasSuccessful()
