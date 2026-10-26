"""Record raw unchanged GPU kernels and worker numeric functions across versions."""
from pathlib import Path
import ast,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-dispatch-20261027-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
BASELINE='d75e5cb26cb58d5f7c18923fb841dfe341f9716c'

def sha(data):return hashlib.sha256(data).hexdigest()
def old(name):
    return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0',
        '-c','maintenance.auto=false','show',BASELINE+':product/src/ai_ad_editor/'+name],cwd=ROOT,timeout=60)

def main():
    out=BASE/'kernel-identity-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=json.loads((BASE/'installation-final-r1/verification.json').read_bytes())
    source=ROOT/'product/src/ai_ad_editor';installed=Path(install['installed'])/'site/ai_ad_editor'
    prior=json.loads((ROOT/'docs/validation/evidence/procedural-particles-20261027-r1/installation-final-r2/verification.json').read_bytes())
    before={v['path']:v['sha256'] for v in prior['source_files']}
    pins={p.name:sha(p.read_bytes()) for p in source.glob('*.py')}
    assert pins=={p.name:sha(p.read_bytes()) for p in installed.glob('*.py')}
    unchanged=sorted(n for n in before if pins[n]==before[n])
    changed=sorted(n for n in before if pins[n]!=before[n])
    assert changed==['__init__.py','capabilities.py','float_gpu.py','float_gpu_worker.py','float_standard_render.py','render.py']
    assert sorted(set(pins)-set(before))==['float_gpu_control.py']
    identities={}
    for name in ('float_gpu_native.py','procedural_particles.py','float_timeline.py','float_geometry.py','float_composite.py'):
        a=old(name);b=(source/name).read_bytes();assert a==b
        identities[name]=sha(b)
    def functions(data):
        return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(data).body if isinstance(n,ast.FunctionDef)}
    a=functions(old('float_gpu_worker.py'));b=functions((source/'float_gpu_worker.py').read_bytes())
    assert all(a[n]==b[n] for n in ('execute','probe'))
    report={'status':'passed','baseline_commit':BASELINE,'prior_product_files':len(before),
        'new_product_files':len(pins),'byte_identical_existing_files':len(unchanged),'changed_files':changed,
        'new_files':['float_gpu_control.py'],'unchanged_numeric_files':identities,
        'worker_execute_and_probe_AST_equal':True,'source_and_installed_equal':True,
        'scope':'Raw kernel identity and numeric-function syntax identity; actual all-frame/PCM and CPU oracle checks are separate.'}
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    (out/'product-files.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
