"""Publish an immutable versioned small Skill kit and verified local digest."""
from pathlib import Path
import hashlib,json,shutil,zipfile
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'local/agent-ffmpeg/gpu-gamut-kit-build-r1';info=json.loads((source/'package.json').read_bytes())
assert info['cli_version']=='0.1.52' and info['files']==150 and info['skill_count']==1 and info['module_count']==17
archive=Path(info['archive']);assert hashlib.sha256(archive.read_bytes()).hexdigest()==info['sha256']
with zipfile.ZipFile(archive) as z:assert len(z.namelist())==150
target=ROOT/'docs/skills'/archive.name;assert not target.exists();shutil.copyfile(archive,target)
assert target.read_bytes()==archive.read_bytes();info['archive']=target.relative_to(ROOT).as_posix()
metadata=ROOT/'docs/skills/community-unified-skill-package-0.1.52-r53.json';assert not metadata.exists()
metadata.write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps(info,ensure_ascii=False))
