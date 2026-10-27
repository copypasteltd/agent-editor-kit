"""Pin byte-verified HDR candidate for real Skill tests; full regression gates delivery."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-hdr-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
    out=BASE/'skill-pin-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r1/verification.json');assert install['status']=='installed-and-byte-verified'
    pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==240
    for name,count in [('source-numeric-r4',12),('source-compat-r1',239)]:
        test=load(BASE/name/'verification.json')
        assert test['status']=='passed' and test['tests']==count and test['failures']==test['errors']==test['skipped']==0
        assert test['frozen_equal'] and test['test_frozen_equal'] and test['product_files']==pins
    assert pins=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
    folder=ROOT/'skills/agent-ffmpeg-local-editor'
    for name in ('SKILL.md','references/runtime.md'):
        p=folder/name;s=p.read_text('utf8').replace('alpha.4-local.37','alpha.4-local.38').replace('0.1.39','0.1.40')
        if name=='SKILL.md':
            s=s.replace('native tracking, seeded GPU particles,','native tracking, explicit PQ/HLG HDR and SDR previews, seeded GPU particles,')
            marker='For repeated GPU generation with the same prompt, read'
            assert marker in s
            s=s.replace(marker,'For PQ/HLG HDR media and client SDR viewing, read\n'
                '[HDR display](references/hdr-display.md). Declare source/working/output\n'
                'reference white, HLG display peak/system gamma and a separate SDR preview\n'
                'mapping; inspect actual 10-bit pixels and matching VUI after rendering.\n'+marker,1)
        write(p,s)
    p=folder/'scripts/run.py';s=p.read_text('utf8')
    s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
    s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.38'",s,count=1,flags=re.M);assert n==1
    write(p,s)
    p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p)
    m.update(release='v0.1.0-alpha.4-local.38',cli_version='0.1.40',manifest_sha256=install['manifest_sha256'])
    m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(m['files'])==79 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
    m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md');write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    report=dict(status='candidate_pinned_for_real_skill_acceptance',cli_version='0.1.40',product_files=240,
        source_numeric_tests=12,source_compatibility_tests=239,full_installed_regression_required_by_delivery_audit=True,
        single_entry=True,internal_modules=17,skill_files=79,source_fallback=False,namespace_manifest_sha256=sha(p))
    write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
