"""Bounded source60 docs/media/history audit against the last pushed main."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def main():
    reference='f255162d8c7cf069134f4c8b697de4901cdf4532'
    git=[GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    def old(name):return subprocess.check_output([*git,'show',reference+':'+name],cwd=ROOT).decode('utf-8')
    result={}
    for name in ['README.md','README.en.md','README.zh-TW.md']:
        before=old(name);now=(ROOT/name).read_text(encoding='utf-8')
        history=[line for line in before.splitlines() if re.match(r'^\| R\d+ \|',line)]
        assert len(history)==468 and all(line in now for line in history)
        ids=re.findall(r'^\| (R\d+) \|',now,re.M)
        assert len(ids)==len(set(ids))==470
        assert '| F84 |' in now
        result[name]=dict(preserved=468,current=470)
    name='docs/product/GOAL_GAPS_20261025.md'
    def closure(text):
        rows=[line.split('|') for line in text.splitlines() if re.match(r'^\| G\d+ \|',line)]
        return {row[1].strip():row[5] for row in rows}
    old_closure=closure(old(name));current=closure((ROOT/name).read_text(encoding='utf-8'))
    assert len(current)==38 and current==old_closure
    inventory=json.loads((ROOT/'docs/assets/music-loop60-20261029-r1/SOURCE_AND_LICENSES.json').read_bytes())
    for name,info in inventory['files'].items():
        p=ROOT/'docs/assets/music-loop60-20261029-r1'/name
        assert p.stat().st_size==info['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==info['sha256']
    manual=ROOT/'docs/product/MUSIC_LOOP.md'
    for target in re.findall(r'\]\(([^)]+)\)',manual.read_text(encoding='utf-8')):
        assert (manual.parent/target).is_file(),target
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json'
    manifest=json.loads(namespace.read_bytes());assert manifest['cli_version']=='0.1.59'
    for record in manifest['files']:
        assert hashlib.sha256((ROOT/record['path']).read_bytes()).hexdigest()==record['sha256']
    report=dict(status='passed',reference=reference,readmes=result,
        all_38_goal_closure_conditions_unchanged=True,actual_media_files=len(inventory['files']),
        formal_skill_files=len(manifest['files']),formal_cli='0.1.59',formal_skill_unchanged=True,
        publication_first_attempt=dict(status='failed-before-readme-write',
            reason='Header beginning R was counted;469 lines versus468 numbered records',
            correction='Match only R followed by numeric ID; existing copied media checked byte-identical'),
        source_only=True)
    out=BASE/'documentation-audit-r1';out.mkdir(exist_ok=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
