"""Reindex the single Skill after correcting the final-key example contract."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/optical-effects-20261027-r1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def main():
    out=BASE/'skill-example-correction-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    path=ROOT/'agent-ffmpeg-local-install-manifest.json';previous=path.read_bytes();m=json.loads(previous)
    assert m['cli_version']=='0.1.38' and m['release']=='v0.1.0-alpha.4-local.36'
    (out/'previous-manifest.json').write_bytes(previous)
    folder=ROOT/'skills/agent-ffmpeg-local-editor'
    m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(m['files'])==77 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
    m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md');save(path,m)
    save(out/'verification.json',dict(status='reindexed',files=77,entry_count=1,internal_modules=17,
        previous_manifest_sha256=hashlib.sha256(previous).hexdigest(),manifest_sha256=sha(path),
        application_manifest_unchanged=m['manifest_sha256'],reason='Explicit final-key interpolation in optical Skill example'))
if __name__=='__main__':main()
