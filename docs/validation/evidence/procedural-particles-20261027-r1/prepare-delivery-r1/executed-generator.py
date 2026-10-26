"""Pin the tested native build and update the single Skill without adding entries."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/procedural-particles-20261027-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def write(p,s):p.write_text(s,encoding='utf8',newline='\n')
def main():
    out=BASE/'prepare-delivery-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json');assert install['source_file_count']==233
    assert install['status']=='installed-and-byte-verified' and install['capability_count']==76
    assert load(BASE/'installed-particles-r1/verification.json')['status']=='passed'
    assert load(BASE/'installed-particle-gpu-r1/verification.json')['status']=='passed'
    folder=ROOT/'skills/agent-ffmpeg-local-editor'
    for name in ('SKILL.md','references/runtime.md'):
        p=folder/name;s=p.read_text('utf8').replace('alpha.4-local.32','alpha.4-local.33').replace('0.1.34','0.1.35')
        if name=='SKILL.md':
            s=s.replace('native tracking, GPU text/image','native tracking, seeded GPU particles, GPU text/image',1)
            marker='For repeated GPU generation with the same prompt, read'
            assert marker in s
            s=s.replace(marker,'For editable snow/confetti/embers/bokeh/rain/sparkles, read\n[procedural particles](references/procedural-particles.md). Use native Float32\nrendering and actual preview evidence; emitter parameters stay in the project.\n'+marker,1)
        write(p,s)
    p=folder/'scripts/run.py';s=p.read_text('utf8')
    s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
    s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.33'",s,count=1,flags=re.M);assert n==1
    write(p,s)
    path=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(path);old=sha(path)
    m.update(release='v0.1.0-alpha.4-local.33',cli_version='0.1.35',manifest_sha256=install['manifest_sha256'])
    m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(m['files'])==76 and sum(Path(v['path']).name=='SKILL.md' for v in m['files'])==1
    m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
    m['skills'][0]['purpose_zh']='唯一入口：17内部模块、可编辑GPU粒子、GPU模型会话/视频生成、原生跟踪/烘焙、Float32/GPU合成、500滤镜、语义检索、字幕配音及四轨分离'
    write(path,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    p=ROOT/'scripts/package_community_skill.py';s=p.read_text('utf8')
    assert "'PROCEDURAL_PARTICLES.md'" not in s
    write(p,s.replace("'MODEL_SESSIONS.md',","'MODEL_SESSIONS.md', 'PROCEDURAL_PARTICLES.md',",1))
    # Reuse the already reviewed local activation path; only release/evidence constants change.
    s=(ROOT/'scripts/activate_model_session_20261027.py').read_text('utf8')
    s=s.replace('model-session-20261027-r1','procedural-particles-20261027-r1').replace('local.32/final-r3','local.33/final-r1')
    write(ROOT/'scripts/activate_particle_delivery_20261027.py',s)
    # Preserve the existing isolated-kit checks and historical fixture dates.
    s=(ROOT/'scripts/verify_model_session_skill_kit_20261027.py').read_text('utf8')
    s=s.replace('single-entry r35 kit','single-entry r36 kit').replace('model-session-20261027-r1','procedural-particles-20261027-r1')
    s=s.replace('unified-skill-r35.zip','unified-skill-r36.zip').replace("'model-session-kit-'","'particle-kit-'").replace('0.1.34','0.1.35')
    s=s.replace("report['files'] == 116 and report['skill_files'] == 75","report['files'] == 118 and report['skill_files'] == 76")
    marker="        run('session-start-help'"
    assert marker in s
    insertion="        assert len(capabilities['capabilities']) == 76\n" if "capabilities = run('capabilities'" in s else ''
    # Add real vfx discovery/help through the isolated installed launcher.
    s=s.replace(marker,"        particle_list=run('particle-list', [*ps,launcher,'vfx','list'],True)\n        assert particle_list['count']==6\n        assert run('particle-inspect', [*ps,launcher,'vfx','inspect','--name','rain'],True)['preset']['version']=='1.0.0'\n        run('particle-apply-help', [*ps,launcher,'vfx','apply','--help'])\n"+marker,1)
    write(ROOT/'scripts/verify_particle_skill_kit_20261027.py',s)
    result={'status':'pinned','old_namespace_sha256':old,'namespace_sha256':sha(path),'skill_files':76,'skill_count':1,
        'module_count':17,'cli_version':'0.1.35','manifest_sha256':install['manifest_sha256'],'source_fallback':False}
    write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
