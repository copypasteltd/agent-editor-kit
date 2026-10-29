"""Audit exact candidate bytes, passed cases and unchanged formal59/history."""
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_bytes())

def main():
    r=load(BASE/'installation-candidate-r1/verification.json')
    assert r['status']=='installed-and-byte-verified' and r['cli_version']=='0.1.60'
    installed=Path(r['installed']);assert sha(Path(r['archive']))==r['archive_sha256']
    source=ROOT/'product/src/ai_ad_editor';pins={p.name:sha(p) for p in source.glob('*.py')}
    assert len(pins)==283 and pins=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
    accepted=['source60-contracts-r1','installed60-bootstrap-r1','installed60-loop-r1',
        'installed60-control-r1','installed60-selection-r1','installed60-semantic-r1',
        'installed60-gpu-r1','installed-actual-case-r1','installed-publication-r1']
    for name in accepted:
        data=load(BASE/name/'verification.json');assert data['status']=='passed'
        for file,pin in data.get('file_hashes',{}).items():assert sha(ROOT/file)==pin
    capabilities=load(BASE/'installation-candidate-r1/capabilities.stdout')
    assert 'music.repair-loop' in capabilities['data']['capabilities']['ai']['community_music']['commands']
    assert all(sha(Path(p))==pin for p,pin in r['registered_skill_file_hashes'].items())
    namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert namespace['cli_version']=='0.1.59'
    assert len(namespace['files'])==93
    assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    assert sha(ROOT/'docs/skills/agent-editor-kit-community-unified-skill-r57.zip')=='46815047a247e32b85d4c5516062486c3f181c54a8d38b9c21710b1757e3b7fd'
    git=[GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    reference='19af0377978e7160c935b58122d1b3c11462054e'
    def old(name):return subprocess.check_output([*git,'show',reference+':'+name],cwd=ROOT).decode('utf-8')
    for name in ['README.md','README.en.md','README.zh-TW.md']:
        prior=[x for x in old(name).splitlines() if re.match(r'^\| R\d+ \|',x)]
        text=(ROOT/name).read_text(encoding='utf-8');assert len(prior)==470 and all(x in text for x in prior)
        ids=re.findall(r'^\| (R\d+) \|',text,re.M);assert len(ids)==len(set(ids))==475
    name='docs/product/GOAL_GAPS_20261025.md'
    def closures(text):return {x.split('|')[1].strip():x.split('|')[5] for x in text.splitlines() if re.match(r'^\| G\d+ \|',x)}
    goals=closures((ROOT/name).read_text(encoding='utf-8'));assert len(goals)==38 and goals==closures(old(name))
    assets=ROOT/'docs/assets/music-loop60-installed-20261029-r1'
    for name,data in load(assets/'SOURCE_AND_LICENSES.json')['files'].items():
        p=assets/name;assert p.stat().st_size==data['bytes'] and sha(p)==data['sha256']
    for name in ['docs/product/MUSIC_LOOP.md','docs/validation/CLI60独立安装交付_2026-10-29.md']:
        p=ROOT/name
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8')):
            if not target.startswith('http'):assert (p.parent/target.split('#')[0]).is_file(),target
    terminal=(BASE/'installed60-contracts-r1/verification.json').exists()
    if terminal:assert load(BASE/'installed60-contracts-r1/verification.json')['status']=='passed'
    out=BASE/'candidate-audit-r1';out.mkdir(exist_ok=False)
    report=dict(status='passed',candidate_cli='0.1.60',formal_cli='0.1.59',source_and_installed_modules=283,
        protected_files=95,formal_skill_files=93,formal_r57_unchanged=True,
        all_38_closure_conditions_unchanged=True,previous_R_rows_preserved=470,current_R_rows=475,
        actual_installed_function_cases_accepted=True,installed400_terminal=terminal,
        candidate_skill_activated=False,full_product_goal_closed=False)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
