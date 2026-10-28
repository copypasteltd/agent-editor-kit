"""Verify staged packaging rejects escaping inventories before creating output."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/aces-delivery-20261029-r1'

def main():
    out=BASE/'packager-source-refusals-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg/aces-packager-source-refusals-r1';work.mkdir(exist_ok=False)
    live=ROOT/'agent-ffmpeg-local-install-manifest.json';before=hashlib.sha256(live.read_bytes()).hexdigest()
    template=json.loads(live.read_bytes());calls=[]
    cases=[('outside-source',None,'C:/dev/sandbox','Skill source must stay inside the repository'),
           ('escaping-parent','../README.md',None,'Skill inventory path is not canonical'),
           ('normalized-parent','skills/agent-ffmpeg-local-editor/../agent-ffmpeg-local-editor/SKILL.md',None,'Skill inventory path is not canonical'),
           ('backslash-alias','skills\\agent-ffmpeg-local-editor\\SKILL.md',None,'Skill inventory path is not canonical')]
    for name,relative,external,message in cases:
        source=work/name;source.mkdir();target=work/(name+'-output')
        manifest=json.loads(json.dumps(template))
        if relative is not None:manifest['files']=[dict(path=relative,bytes=0,sha256='0'*64)]
        (source/'agent-ffmpeg-local-install-manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        command=[sys.executable,'-I','-S','-B','-u','-X','utf8',str(ROOT/'scripts/package_community_skill.py'),
                 '--skill-source',external or str(source),'--output',str(target),'--archive-name','refused.zip']
        r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout')).write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        assert r.returncode!=0 and message in r.stderr.decode('utf-8','replace') and not target.exists(),name
        calls.append(dict(name=name,argv=command,exit_code=r.returncode,output_created=False))
    assert hashlib.sha256(live.read_bytes()).hexdigest()==before
    report=dict(status='passed',refusals=len(calls),calls=calls,live_namespace_unchanged=True,source_fallback=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))

if __name__=='__main__':main()
