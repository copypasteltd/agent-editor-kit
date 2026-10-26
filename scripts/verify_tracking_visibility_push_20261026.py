"""Read-only verification of the pushed main commit and usable local artifacts."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def load(path):return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    out=ROOT/'local/agent-ffmpeg/tracking-visibility-push-r1'
    out.mkdir(exist_ok=False)
    def git(*args):
        return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false',
            '-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=120)
    assert git('branch','--show-current').strip()==b'main'
    assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
    head=git('rev-parse','HEAD').decode().strip()
    remote=git('ls-remote','origin','refs/heads/main')
    (out/'ls-remote.txt').write_bytes(remote)
    assert remote.decode().split()[0]==head
    assert not git('status','--porcelain=v1','-z')
    base=ROOT/'docs/validation/evidence/tracking-visibility-20261026-r1'
    installation=load(base/'installation-final-r1/verification.json')
    runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
    kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.31-r32.json')
    assert runtime['release']=='v0.1.0-alpha.4-local.29'
    assert installation['manifest_sha256']==runtime['manifest_sha256']
    assert sha(Path(installation['archive']))==installation['archive_sha256']
    assert Path(installation['archive']).stat().st_size==installation['archive_bytes']
    assert sha(ROOT/kit['archive'])==kit['sha256']
    installed=Path(runtime['installed_directory'])
    pins=load(base/'final-delivery-r2/product-files.json')
    assert len(pins)==224
    for name,value in pins.items():
        assert sha(ROOT/'product/src/ai_ad_editor'/name)==sha(installed/'site/ai_ad_editor'/name)==value
    assert load(base/'final-delivery-r2/verification.json')['status']=='passed'
    assert load(base/'staged-byte-r2/verification.json')['status']=='passed'
    result=dict(status='passed',checked_at_utc=datetime.now(timezone.utc).isoformat(),head=head,
        remote_main_equal=True,working_tree_clean=True,branch='main',normal_push=True,
        cli_version='0.1.31',release=runtime['release'],source_installed_test_pins_equal=224,
        archive_bytes=installation['archive_bytes'],archive_sha256=installation['archive_sha256'],
        kit_sha256=kit['sha256'],source_fallback=False,new_renders=0,new_model_forwards=0)
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
