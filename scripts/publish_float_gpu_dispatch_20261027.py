"""Copy the built r37 kit into versioned docs with a verified public digest."""
from pathlib import Path
import hashlib,json,shutil,zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    source=ROOT/'local/agent-ffmpeg/gpu-dispatch-kit-build-r1'
    info=json.loads((source/'package.json').read_bytes())
    assert info['cli_version']=='0.1.36' and info['files']==119 and info['skill_count']==1 and info['module_count']==17
    archive=Path(info['archive']);assert hashlib.sha256(archive.read_bytes()).hexdigest()==info['sha256']
    with zipfile.ZipFile(archive) as z:assert len(z.namelist())==119
    target=ROOT/'docs/skills'/archive.name;assert not target.exists()
    shutil.copy2(archive,target);assert target.read_bytes()==archive.read_bytes()
    info['archive']=target.relative_to(ROOT).as_posix()
    metadata=ROOT/'docs/skills/community-unified-skill-package-0.1.36-r37.json';assert not metadata.exists()
    metadata.write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(info,ensure_ascii=False))

if __name__=='__main__':main()
