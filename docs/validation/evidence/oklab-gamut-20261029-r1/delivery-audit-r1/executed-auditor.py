"""Finalize actual r52 kit evidence and audit source/Skill/history alignment."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
BASELINE='7518a90c09e9cf2b6451f170a6fbf2a727daceb5'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def old(p):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','show',BASELINE+':'+p],cwd=ROOT).decode('utf8')
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('delivery-audit-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-auditor.py').write_bytes(Path(__file__).read_bytes())
    kitcheck=load(BASE/'kit-r1/verification.json');assert kitcheck['status']=='passed' and kitcheck['files']==148 and kitcheck['skill_files']==90
    assert kitcheck['actual_OKLab_frame_and_range_validated'] and kitcheck['actual_post_codec_48_frames_validated']
    meta=load(ROOT/'docs/skills/community-unified-skill-package-0.1.51-r52.json');assert meta['files']==148
    archive=ROOT/meta['archive'];assert sha(archive)==meta['sha256']==kitcheck['kit_sha256']
    with zipfile.ZipFile(archive) as z:assert len(z.namelist())==148 and len(load_inventory(z)['files'])==147
    ns=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert ns['cli_version']=='0.1.51' and len(ns['files'])==90
    for row in ns['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
    runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');assert runtime['release']=='v0.1.0-alpha.4-local.49' and runtime['manifest_sha256']==ns['manifest_sha256']
    pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==277
    assert pins=={p.name:sha(p) for p in (Path(runtime['installed_directory'])/'site/ai_ad_editor').glob('*.py')}
    for name,n in [('installed-measure-r1',64),('installed-preview-r1',18),('installed-compat-r2',352)]:
        t=load(BASE/name/'verification.json');assert t['status']=='passed' and t['tests']==n and t['product_files']==pins
        for module,digest in t['test_files'].items():assert sha(ROOT/'product/tests'/(module+'.py'))==sha(BASE/name/'executed-tests'/(module+'.py'))==digest
    case=load(BASE/'registered-case-r2/verification.json');assert case['status']=='passed' and case['registered_skill_used'] and case['frame9_RGBA16_maximum_code_error']<=2
    public=Path(case['public']);media=load(public/'SOURCE.json')
    for row in media['files']:assert sha(public/row['path'])==row['sha256']
    assert case['author_graph_unchanged'] and case['preview_project_bytes_unchanged'] and case['render_output_ledger_appended']
    assert case['complete_PCM_equal'] and case['PCM_bytes']==384000 and case['all_YUV_source_original_replay_equal']
    assert load(BASE/'skill-validation-r1/verification.json')['status']=='passed'
    newrow='| R353 | Independent r52 kit extraction and real isolated registration | 148 entries/147 inventory/90 Skill files; actual OKLab frame/range and48-frame post-codec meter | 2026-10-29 | [kit](docs/validation/evidence/oklab-gamut-20261029-r1/kit-r1/verification.json), [digest](docs/skills/community-unified-skill-package-0.1.51-r52.json) | real discovery junction unchanged;1 Skill/17 modules; no clean-host claim |'
    for name in ['README.md','README.zh-TW.md','README.en.md']:
        p=ROOT/name;s=p.read_text('utf8');prior=re.findall(r'^\| R\d+ .*$',old(name),re.M)
        current=re.findall(r'^\| R\d+ .*$',s,re.M);assert len(prior)==349 and current[:349]==prior
        if len(current)==352:
            s=s.replace(current[-1],current[-1]+'\n'+newrow,1);write(p,s)
        else:assert len(current)==353 and current[-1]==newrow
    gaps=ROOT/'docs/product/GOAL_GAPS_20261025.md'
    original={r.split('|')[1].strip():r for r in old(gaps.relative_to(ROOT).as_posix()).splitlines() if re.match(r'^\| G\d+ \|',r)}
    current={r.split('|')[1].strip():r for r in gaps.read_text('utf8').splitlines() if re.match(r'^\| G\d+ \|',r)}
    assert len(original)==len(current)==38
    for key,row in original.items():
        assert row.split('|')[-3]==current[key].split('|')[-3],key
        if key!='G08':assert row==current[key],key
    for suffix in ('','.zh-TW','.en'):
        text=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8')
        caps=load(ROOT/'docs/product/oklab-gamut-installed-capabilities-cli-0.1.51.json')['data']['capabilities']
        for key,value in caps.items():
            match=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',text,re.M|re.S)
            assert match and json.loads(match[1])==value,key
    changed=subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','diff','--name-only',BASELINE,'--','docs/releases/v0.1.0-alpha.3'],cwd=ROOT)
    assert not changed.strip(), 'Historical alpha.3 content changed'
    assert 'sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.49/unpacked-r2/manifest.json')==ns['manifest_sha256']
    result=dict(status='passed',product_files=277,skill_files=90,kit_files=148,inventory_files=147,
                current_readme_rows=353,historical_readme_rows_preserved=349,original_gap_closures_preserved=38,
                capability_entries_per_language=88,registered_skill_actual_case=True,independent_kit_verified=True,
                whole_goal_complete=False,public_alpha3_unchanged=True)
    write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))
def load_inventory(z):return json.loads(z.read('KIT-FILES.json'))
if __name__=='__main__':main()
