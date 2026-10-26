"""Pin the final bounded JSON reader; compare all previously measured core bytes."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/procedural-particles-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
    out=BASE/'loader-final-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    first=load(BASE/'installation-final-r1/verification.json');final=load(BASE/'installation-final-r2/verification.json')
    old=Path(first['installed'])/'site/ai_ad_editor';new=Path(final['installed'])/'site/ai_ad_editor'
    names={p.name for p in old.glob('*.py')};assert names=={p.name for p in new.glob('*.py')} and len(names)==233
    changed=[n for n in sorted(names) if sha(old/n)!=sha(new/n)];assert changed==['procedural_cli.py','utils.py']
    core={'procedural_particles.py','float_timeline.py','float_standard_render.py','render.py','float_gpu.py','float_gpu_native.py','float_gpu_worker.py'}
    assert core.isdisjoint(changed)
    assert load(BASE/'installed-native-regression-r1/verification.json')['status']=='passed'
    assert load(BASE/'installed-legacy-r1/verification.json')['status']=='passed'
    p=ROOT/'skills/agent-ffmpeg-local-editor/scripts/run.py';s=p.read_text('utf8')
    s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(final['manifest_sha256']),s,count=1,flags=re.M);assert n==1;write(p,s)
    p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m['manifest_sha256']=final['manifest_sha256']
    m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted((ROOT/'skills/agent-ffmpeg-local-editor').rglob('*')) if p.is_file()]
    assert len(m['files'])==76;write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    p=ROOT/'scripts/activate_particle_delivery_20261027.py';s=p.read_text('utf8')
    assert 'local.33/final-r1/installed' in s;write(p,s.replace('local.33/final-r1/installed','local.33/final-r2/installed'))
    result={'status':'passed','old_installation':first['installed'],'final_installation':final['installed'],
        'changed_product_files':changed,'byte_identical_product_files':231,'pixel_and_GPU_kernels_byte_identical':True,
        'final_manifest_sha256':final['manifest_sha256'],'source_files':233,
        'old_core_regressions':'installed-native-regression-r1 and installed-legacy-r1 are final-r1; 231 other product files, including all pixel/GPU kernels, remain byte-identical',
        'final_feature_tests':'Final-r2 particles/file loading/idempotency, actual GPU, native integration and legacy tests are rerun separately.',
        'rejected_installed_candidate_retained':True}
    write(out/'verification.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
