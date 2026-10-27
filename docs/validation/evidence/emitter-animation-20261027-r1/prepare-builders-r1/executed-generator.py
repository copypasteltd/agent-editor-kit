"""Derive immutable CLI37 delivery tools; pin Skill only after installed tests."""
from pathlib import Path
import argparse,hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/emitter-animation-20261027-r1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf8',newline='\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['builders','skill']);a=ap.parse_args()
    out=BASE/('prepare-'+a.stage+'-r1');out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def derive(source,target,extra=()):
        s=(ROOT/'scripts'/source).read_text('utf8')
        for old,new in [('gpu-dispatch-20261027-r1','emitter-animation-20261027-r1'),
                        ('alpha.4-local.34','alpha.4-local.35'),('0.1.36','0.1.37'),*extra]:s=s.replace(old,new)
        write(ROOT/'scripts'/target,s)
    if a.stage=='builders':
        derive('build_float_gpu_dispatch_20261027.py','build_emitter_animation_20261027.py')
        derive('activate_float_gpu_dispatch_20261027.py','activate_emitter_animation_20261027.py')
        derive('validate_float_gpu_dispatch_20261027.py','validate_emitter_animation_20261027.py')
        derive('verify_float_gpu_dispatch_20261027.py','verify_emitter_animation_20261027.py',[
            ('r37 kit','r38 kit'),('unified-skill-r37.zip','unified-skill-r38.zip'),
            ("'gpu-dispatch-kit-'","'emitter-animation-kit-'"),("report['files'] == 119","report['files'] == 120")])
        p=ROOT/'scripts/verify_emitter_animation_20261027.py';s=p.read_text('utf8')
        marker="        generation=caps['capabilities']['generative_video_editing']['complete_video_generation']"
        assert marker in s
        s=s.replace(marker,"        assert caps['capabilities']['procedural_particles']['emitter_animation']['protocol']=='source-anchored-emitter-keyframes-v1'\n"
            "        properties=run('emitter-properties', [*ps,launcher,'vfx','animation-properties'],True)\n"
            "        assert properties['count']==21\n"
            "        run('emitter-animate-help', [*ps,launcher,'vfx','animate','--help'])\n"+marker,1)
        write(p,s)
    else:
        install=json.loads((BASE/'installation-final-r1/verification.json').read_bytes())
        tests=json.loads((BASE/'installed-regression-r1/verification.json').read_bytes())
        assert install['status']=='installed-and-byte-verified' and install['source_file_count']==235
        assert tests['status']=='passed' and tests['tests']==679 and tests['skipped']==0
        folder=ROOT/'skills/agent-ffmpeg-local-editor'
        for name in ('SKILL.md','references/runtime.md'):
            p=folder/name;s=p.read_text('utf8').replace('alpha.4-local.34','alpha.4-local.35').replace('0.1.36','0.1.37')
            if name=='SKILL.md':
                s=s.replace('emitter parameters stay in the project.',
                    'all 21 emitter parameters support source-clock keyframes.\n'
                    'Use `vfx animation-properties` to discover constraints and `vfx animate` to\n'
                    'add/replace/remove one property. Distinguish integrated birth rate, birth-\n'
                    'sampled motion/lifetime and live appearance; preview the actual source time.')
            write(p,s)
        p=folder/'scripts/run.py';s=p.read_text('utf8')
        s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
        s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.35'",s,count=1,flags=re.M);assert n==1
        write(p,s)
        p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=json.loads(p.read_bytes())
        m.update(release='v0.1.0-alpha.4-local.35',cli_version='0.1.37',manifest_sha256=install['manifest_sha256'])
        m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                    for p in sorted(folder.rglob('*')) if p.is_file()]
        assert len(m['files'])==76 and sum(Path(v['path']).name=='SKILL.md' for v in m['files'])==1
        m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md');write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    result={'status':'prepared','stage':a.stage,'cli_version':'0.1.37','source_fallback':False}
    write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
