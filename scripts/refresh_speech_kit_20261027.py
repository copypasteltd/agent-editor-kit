"""Finalize the not-yet-committed r44 kit while retaining its initial candidate."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
target=ROOT/'docs/skills/agent-editor-kit-community-unified-skill-r44.zip'
git='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
tracked=subprocess.run([git,'ls-files','--error-unmatch','--',target.relative_to(ROOT).as_posix()],cwd=ROOT,capture_output=True)
assert tracked.returncode==1,'Only an uncommitted new candidate may be replaced'
backup=BASE/'kit-r1/retained-input-kit.zip';assert not backup.exists();shutil.copy2(target,backup)
metadata=ROOT/'docs/skills/community-unified-skill-package-0.1.43-r44.json';old=json.loads(metadata.read_bytes())
assert hashlib.sha256(backup.read_bytes()).hexdigest()==old['sha256']
info=json.loads((ROOT/'local/agent-ffmpeg/native-speech-enhancement-kit-build-r2/package.json').read_bytes())
archive=Path(info['archive']);assert info['files']==132 and hashlib.sha256(archive.read_bytes()).hexdigest()==info['sha256']
shutil.copy2(archive,target);info['archive']=target.relative_to(ROOT).as_posix();metadata.write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
for name in ('README.md','README.zh-TW.md','README.en.md','docs/validation/本地对白增强实测_2026-10-27.md'):
    p=ROOT/name;s=p.read_text('utf8').replace('native-speech-enhancement-20261027-r1/kit-r1/verification.json','native-speech-enhancement-20261027-r1/kit-r2/verification.json');p.write_text(s,encoding='utf8',newline='\n')
p=ROOT/'scripts/audit_speech_enhancement_20261027.py';p.write_text(p.read_text('utf8').replace("BASE/'kit-r1/verification.json'","BASE/'kit-r2/verification.json'"),encoding='utf8',newline='\n')
print(json.dumps(dict(status='uncommitted-r44-candidate-finalized',sha256=info['sha256'],retained_initial_kit=str(backup.relative_to(ROOT)))))
