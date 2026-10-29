"""Publish bounded source59 development work; never activate an unverified install."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
BASE = ROOT/'docs/validation/evidence/music-score-20261029-r1'

def main():
    for name in ['contracts-r3','source59-bootstrap-r1','source59-selection-r1',
                 'source59-semantic-r1','source59-contracts-r1','source59-control-r2',
                 'actual-case-r1','publication-r1','developer-entry-r1']:
        assert json.loads((BASE/name/'verification.json').read_bytes())['status']=='passed'
    files=['.gitattributes','README.md','README.en.md','README.zh-TW.md',
        'product/pyproject.toml','product/src/ai_ad_editor/__init__.py',
        'product/src/ai_ad_editor/music_score.py','product/src/ai_ad_editor/community_cli.py',
        'product/src/ai_ad_editor/capabilities.py','product/src/ai_ad_editor/convert.py',
        'product/tests/test_music_score.py','product/tests/test_process_operation_budget.py',
        'scripts/run_source_editor.py','docs/product/MUSIC_SCORE.md',
        'docs/product/MUSIC_BACKEND_ADMISSION.md','docs/product/GOAL_GAPS_20261025.md',
        'docs/product/CASES.md','docs/product/SKILLS.md','docs/local/INSTALLATION.md',
        'docs/validation/CLI58独立安装交付_2026-10-29.md',
        'docs/validation/CLI59谱面合成_2026-10-29.md',
        'docs/validation/run_music_score_regressions.py',
        'docs/validation/run_music_score_compatibility.py',
        'docs/validation/run_music_score_case.py','docs/validation/publish_music_score_case.py',
        'docs/validation/commit_source59_score.py']
    files += ['docs/product/COMMUNITY_MATERIALS'+suffix+'.md' for suffix in ['', '.en','.zh-TW']]
    # Only immediate files in these explicitly bounded, completed evidence directories.
    dirs=[*BASE.iterdir(),ROOT/'docs/assets/music-score59-20261029-r1',
        ROOT/'docs/validation/evidence/yue2-native-20261029-r1/probe-r1',
        ROOT/'docs/validation/evidence/ad-content-uniqueness-20261029-r1/rollout-consistency-r1']
    for directory in dirs:
        if directory.is_dir():
            for path in directory.iterdir():
                if path.is_file(): files.append(path.relative_to(ROOT).as_posix())
    files=sorted(set(files));assert all((ROOT/f).is_file() for f in files)
    out=ROOT/'local/agent-ffmpeg/source59-commit-r1';out.mkdir(exist_ok=False)
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    for name,args in [('add',['add','--',*files]),('check',['diff','--cached','--check','--',*files]),
        ('commit',['commit','--only','-m','feat: add editable score synthesis and verified original music case','--',*files])]:
        p=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
        (out/(name+'.stdout')).write_bytes(p.stdout);(out/(name+'.stderr')).write_bytes(p.stderr)
        print(json.dumps({'phase':name,'exit_code':p.returncode}),flush=True)
        if p.returncode:
            print(p.stderr.decode('utf-8','replace')[-2500:],flush=True);return p.returncode
    refs={}
    for name,args in [('head',['rev-parse','HEAD']),('origin',['rev-parse','origin/main']),
                      ('remote',['ls-remote','origin','refs/heads/main'])]:
        p=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True,check=True)
        refs[name]=p.stdout.decode().split()[0]
    assert len(set(refs.values()))==1
    (out/'verification.json').write_text(json.dumps({'status':'passed','refs':refs},indent=2)+'\n',encoding='utf-8')
    print(json.dumps(refs),flush=True)
    return 0

if __name__=='__main__': raise SystemExit(main())
