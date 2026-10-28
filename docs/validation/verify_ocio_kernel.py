"""Native Windows source-stage OCIO proof. Run with the project's Python 3.13."""
import contextlib,hashlib,io,json,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/validation/evidence/aces-kernel-20261029-r1'
OUT.mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
import numpy as np
from ai_ad_editor import ocio_runtime as ocio
from ai_ad_editor.cli import main
from test_ocio_runtime import selection

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
    log=io.StringIO()
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromName('test_ocio_runtime'))
    (OUT/'tests.txt').write_text(log.getvalue(),encoding='utf-8')
    assert result.wasSuccessful() and result.testsRun==9 and not result.skipped,log.getvalue()
    stream=io.StringIO()
    with contextlib.redirect_stdout(stream):code=main(['surface','ocio-configs','--config','aces-2.1','--format','json'])
    assert code==0,stream.getvalue()
    (OUT/'cli-catalog.json').write_text(stream.getvalue(),encoding='utf-8')
    wheel=ROOT/'sources/opencolorio/2.6.0/opencolorio-2.6.0-cp313-cp313-win_amd64.whl'
    assert digest(wheel)=='9f389e858b7cb075a4fa6a0ab893b2cecd0267ac582d6d9992c755d69209a80c'
    source=np.random.default_rng(20261029).uniform(-.2,16,(37,41,4)).astype(np.float32)
    source[:,:,3]=np.random.default_rng(3).uniform(0,1,(37,41)).astype(np.float32)
    np.save(OUT/'input.npy',source,allow_pickle=False)
    # Reference uses original upstream wheel in a fresh isolated child, with no product import.
    child='''import sys,json;from pathlib import Path
sys.path.insert(0,sys.argv[1])
sys.path.insert(1,sys.argv[5])
import PyOpenColorIO as o
import numpy as np
p=Path(sys.argv[2]);a=np.load(p/'input.npy',allow_pickle=False)
c=o.Config.CreateFromBuiltinConfig(sys.argv[3]);c.validate()
t=o.DisplayViewTransform(src='ACEScg',display='sRGB - Display',view=sys.argv[4])
c.getProcessor(t).getDefaultCPUProcessor().applyRGBA(a.reshape(-1,4))
np.save(p/'reference.npy',a,allow_pickle=False)
print(json.dumps(dict(version=o.__version__,module=o.__file__,product_imported=any(k.startswith('ai_ad_editor') for k in sys.modules))))
'''
    comparisons=[]
    with tempfile.TemporaryDirectory(prefix='upstream-ocio-',dir=ROOT/'local') as temp:
        with zipfile.ZipFile(wheel) as z:
            for name in ['PyOpenColorIO/__init__.py','PyOpenColorIO/PyOpenColorIO.pyd','PyOpenColorIO/bin/OpenColorIO_2_6.dll']:
                z.extract(name,temp)
        for key in ocio.CONFIGS:
            value=selection(key)
            proc=subprocess.run([sys.executable,'-I','-B','-c',child,temp,str(OUT),ocio.CONFIGS[key],value['view'],str(Path(np.__file__).resolve().parent.parent)],capture_output=True,text=True,encoding='utf-8',timeout=60)
            assert proc.returncode==0,proc.stderr
            info=json.loads(proc.stdout);assert not info['product_imported']
            expected=np.load(OUT/'reference.npy',allow_pickle=False)
            with ocio.DisplayTransform(value) as t:actual,meta=t.apply(source)
            np.testing.assert_array_equal(actual,expected)
            np.save(OUT/(key+'-output.npy'),actual,allow_pickle=False)
            comparisons.append(dict(config=key,max_absolute_error=float(np.max(abs(actual-expected))),upstream=info,metadata=meta))
    receipt=dict(status='passed',scope='source-kernel-and-discovery-only',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
                 official_wheel_sha256=digest(wheel),reference_scope='independent process and original wheel; same upstream algorithm, not independent colour science',
                 comparisons=comparisons,source_files={str(p.relative_to(ROOT)):digest(p) for p in [*ocio.runtime_paths(),ROOT/'product/src/ai_ad_editor/cli.py',ROOT/'product/pyproject.toml',ROOT/'product/tests/test_ocio_runtime.py']},
                 timeline_integrated=False,preview_integrated=False,installed_skill_updated=False,GPU=False)
    (OUT/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:receipt[k] for k in ['status','tests','timeline_integrated','installed_skill_updated']}))

if __name__=='__main__':run()
