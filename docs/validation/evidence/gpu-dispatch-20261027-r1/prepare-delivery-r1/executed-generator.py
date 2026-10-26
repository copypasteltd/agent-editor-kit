"""Pin CLI36 and retain the single verified native Skill discovery contract."""
from pathlib import Path
import hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-dispatch-20261027-r1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf8',newline='\n')

def main():
    out=BASE/'prepare-delivery-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=json.loads((BASE/'installation-final-r1/verification.json').read_bytes())
    assert install['source_file_count']==234 and install['capability_count']==76
    assert install['status']=='installed-and-byte-verified'
    folder=ROOT/'skills/agent-ffmpeg-local-editor'
    for name in ('SKILL.md','references/runtime.md'):
        p=folder/name;s=p.read_text('utf8').replace('alpha.4-local.33','alpha.4-local.34').replace('0.1.35','0.1.36')
        if name=='SKILL.md':
            marker='For editable snow/confetti/embers/bokeh/rain/sparkles, read'
            assert marker in s
            s=s.replace(marker,'Native Float32 GPU operations now use bounded owned control pipes. Read\n'
                '[GPU execution](references/projection-gpu.md) for policy, actual operator counts,\n'
                'cancellation and process/thread/stream cleanup receipts.\n'+marker,1)
        write(p,s)
    p=folder/'scripts/run.py';s=p.read_text('utf8')
    s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
    s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.34'",s,count=1,flags=re.M);assert n==1
    write(p,s)
    p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=json.loads(p.read_bytes());old=sha(p)
    m.update(release='v0.1.0-alpha.4-local.34',cli_version='0.1.36',manifest_sha256=install['manifest_sha256'])
    m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(m['files'])==76 and sum(Path(v['path']).name=='SKILL.md' for v in m['files'])==1
    m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
    write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    s=(ROOT/'scripts/activate_particle_delivery_20261027.py').read_text('utf8')
    s=s.replace('procedural-particles-20261027-r1','gpu-dispatch-20261027-r1').replace('local.33/final-r2','local.34/final-r1')
    write(ROOT/'scripts/activate_float_gpu_dispatch_20261027.py',s)
    s=(ROOT/'scripts/verify_particle_skill_kit_20261027.py').read_text('utf8')
    s=s.replace('r36 kit','r37 kit').replace('procedural-particles-20261027-r1','gpu-dispatch-20261027-r1')
    s=s.replace('unified-skill-r36.zip','unified-skill-r37.zip').replace("'particle-kit-'","'gpu-dispatch-kit-'").replace('0.1.35','0.1.36')
    s=s.replace("report['files'] == 118", "report['files'] == 119")
    marker="        generation=caps['capabilities']['generative_video_editing']['complete_video_generation']"
    assert marker in s
    s=s.replace(marker,"        assert caps['capabilities']['hardware_acceleration']['float32_projection']['control']['protocol']=='owned-inherited-binary-pipes-v1'\n"+marker,1)
    write(ROOT/'scripts/verify_float_gpu_dispatch_20261027.py',s)
    s=(ROOT/'scripts/validate_particle_skill_20261027.py').read_text('utf8')
    s=s.replace('procedural-particles-20261027-r1','gpu-dispatch-20261027-r1').replace('0.1.35','0.1.36')
    write(ROOT/'scripts/validate_float_gpu_dispatch_20261027.py',s)
    result={'status':'pinned','old_manifest_sha256':old,'manifest_sha256':sha(p),
        'skill_count':1,'skill_files':76,'modules':17,'source_fallback':False,'cli_version':'0.1.36'}
    write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
