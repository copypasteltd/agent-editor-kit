"""Derive CLI38 delivery tools and pin the Skill only after installed acceptance."""
from pathlib import Path
import argparse,hashlib,json,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/optical-effects-20261027-r1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_text(s,encoding='utf8',newline='\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('stage',choices=['builders','skill']);a=ap.parse_args()
    out=BASE/('prepare-'+a.stage+'-r1');out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def derive(source,target,extra=()):
        s=(ROOT/'scripts'/source).read_text('utf8')
        for old,new in [('emitter-animation-20261027-r1','optical-effects-20261027-r1'),
            ('alpha.4-local.35','alpha.4-local.36'),('0.1.37','0.1.38'),*extra]:s=s.replace(old,new)
        p=ROOT/'scripts'/target;assert not p.exists();write(p,s)
    if a.stage=='builders':
        derive('build_emitter_animation_20261027.py','build_optical_effects_20261027.py')
        derive('activate_emitter_animation_20261027.py','activate_optical_effects_20261027.py')
        derive('validate_emitter_animation_20261027.py','validate_optical_effects_20261027.py',[
            ('==76','==77'),("'skill_files':76","'skill_files':77")])
        derive('verify_emitter_animation_20261027.py','verify_optical_effects_20261027.py',[
            ('r38 kit','r39 kit'),('unified-skill-r38.zip','unified-skill-r39.zip'),
            ("'emitter-animation-kit-'","'optical-effects-kit-'"),
            ("report['files'] == 120","report['files'] == 122"),("report['skill_files'] == 76","report['skill_files'] == 77")])
        p=ROOT/'scripts/verify_optical_effects_20261027.py';s=p.read_text('utf8')
        marker="        generation=caps['capabilities']['generative_video_editing']['complete_video_generation']"
        assert marker in s
        s=s.replace(marker,"        assert len(caps['capabilities'])==77\n"
            "        assert caps['capabilities']['optical_effects']['protocol']=='author-clock-linear-float32-optical-effects-v1'\n"
            "        optical=run('optical-catalog', [*ps,launcher,'effects','list','--query','optical'],True)\n"
            "        assert optical['count']==3 and optical['catalog_version']=='0.10.0'\n"
            "        for name in ('lens_flare','light_leak','rgb_split'):\n"
            "            inspected=run('optical-'+name,[*ps,launcher,'effects','inspect','--name',name],True)\n"
            "            assert inspected['effect']['backend']=='native:float32-optics'\n"+marker,1)
        write(p,s)
        derive('publish_emitter_animation_20261027.py','publish_optical_effects_20261027.py',[
            ('r38 kit','r39 kit'),('emitter-animation-kit-build-r1','optical-effects-kit-build-r1'),
            ('==120','==122'),('0.1.38-r38.json','0.1.38-r39.json')])
        derive('audit_emitter_animation_stage_20261027.py','audit_optical_effects_stage_20261027.py',[
            ('66c5da3190d06398ab57171dfe855a532f62bbe3','f9776caf9d1d49d0878f8123b32be35f512b9f78'),
            ('235','237'),("len(manifest['files'])==76","len(manifest['files'])==77"),("'skill_files':76","'skill_files':77")])
    else:
        install=json.loads((BASE/'installation-final-r1/verification.json').read_bytes())
        tests=json.loads((BASE/'installed-regression-final-r2/verification.json').read_bytes())
        assert install['status']=='installed-and-byte-verified' and install['source_file_count']==237
        assert tests['status']=='passed' and tests['tests']==704 and tests['skipped']==0
        folder=ROOT/'skills/agent-ffmpeg-local-editor'
        assert (folder/'references/optical-effects.md').is_file()
        for name in ('SKILL.md','references/runtime.md'):
            p=folder/name;s=p.read_text('utf8').replace('alpha.4-local.35','alpha.4-local.36').replace('0.1.37','0.1.38')
            if name=='SKILL.md':
                s=s.replace('seeded GPU particles,','seeded GPU particles, editable GPU flare/light leaks/chromatic split,')
                marker='For repeated GPU generation with the same prompt, read'
                assert marker in s
                s=s.replace(marker,'For editable lens flare, light leaks and chromatic aberration, read\n'
                    '[optical effects](references/optical-effects.md). Discover actual constraints\n'
                    'with `effects list --query optical` / `effects inspect`; use explicit native\n'
                    'linear RGB and original author-clock keys. Preview additive light/range\n'
                    'clipping and color-split edges before delivery.\n'+marker,1)
            write(p,s)
        p=folder/'scripts/run.py';s=p.read_text('utf8')
        s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
        s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.36'",s,count=1,flags=re.M);assert n==1
        write(p,s)
        p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=json.loads(p.read_bytes())
        m.update(release='v0.1.0-alpha.4-local.36',cli_version='0.1.38',manifest_sha256=install['manifest_sha256'])
        m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                    for p in sorted(folder.rglob('*')) if p.is_file()]
        assert len(m['files'])==77 and sum(Path(v['path']).name=='SKILL.md' for v in m['files'])==1
        m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md');write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    result={'status':'prepared','stage':a.stage,'cli_version':'0.1.38','source_fallback':False}
    write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
