"""Audit source GPU delivery claims, immutable evidence and retained goal/history."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
PREVIOUS='9072fd8a89b2a34ee7aae95c7f9afd421bec5599'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def old(path):
    r=subprocess.run([GIT,'--no-optional-locks','-c','core.fsmonitor=false','show',PREVIOUS+':'+path],cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    assert r.returncode==0,r.stderr;return r.stdout
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('audit-'+a.run);out.mkdir(exist_ok=False);(out/'executed-auditor.py').write_bytes(Path(__file__).read_bytes())
    pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==278
    for name,n in [('source-r2',70),('gpu-control-r1',12)]:
        v=load(BASE/name/'verification.json');assert v['status']=='passed' and v['tests']==n and v['skipped']==0 and v['product_files']==pins and v['frozen_equal']
    probe=load(BASE/'4k-r1/verification.json');case=load(BASE/'case-r2/verification.json')
    assert probe['source_files']==case['source_files']==pins and probe['status']==case['status']=='passed'
    assert probe['pixels']==8294400 and probe['all_pixels_compared'] and probe['maximum_linear_RGB_error']<1e-6
    for k in ('worker_closed','shared_handles_closed'):assert probe['GPU_evidence'][k]
    assert probe['GPU_evidence']['operations']['gamut_map']==1
    assert case['YUV_bytes']==4976640 and case['PCM_bytes']==384000 and case['frame9_RGBA16_maximum_code_error']==0
    assert case['all_YUV_source_original_replay_equal'] and case['complete_PCM_equal'] and not case['registered_skill_used']
    calls=load(BASE/'case-r2/calls.json');assert len(calls)==18 and all(v['exit_code']==0 for v in calls)
    movie=load(BASE/'case-r2/render.stdout')['data']['delivery']['pixel_pipeline'];assert movie['projection_acceleration']['operations']['gamut_map']==10
    assert movie['last_display_mapping']['perceptual_gamut']['GPU']
    cap=load(ROOT/'docs/product/gpu-gamut-source-capabilities-cli-0.1.52.json');assert len(cap['data']['capabilities'])==89 and cap['provenance']['cli_version']=='0.1.52'
    installed=load(BASE/'installation-final-r1/verification.json');assert installed['cli_version']=='0.1.52' and installed['source_file_count']==278
    assert {v['path']:v['sha256'] for v in installed['source_files']}==pins
    assert sha(installed['archive'])==installed['archive_sha256'] and Path(installed['archive']).stat().st_size==installed['archive_bytes']
    with zipfile.ZipFile(installed['archive']) as archive:
        assert 'sha256:'+hashlib.sha256(archive.read('manifest.json')).hexdigest()==installed['manifest_sha256']
    assert load(BASE/'installation-final-r1/install.stdout.json')['manifest_sha256']==installed['manifest_sha256']
    assert {p.name:sha(p) for p in (Path(installed['installed'])/'site/ai_ad_editor').glob('*.py')}==pins
    ns=ROOT/'agent-ffmpeg-local-install-manifest.json';assert ns.read_bytes()==old(ns.name)
    v=load(ns);assert v['cli_version']=='0.1.51' and len(v['files'])==90
    for entry in v['files']:assert sha(ROOT/entry['path'])==entry['sha256']
    assert (ROOT/'local/agent-ffmpeg/runtime.json').read_bytes()==old('local/agent-ffmpeg/runtime.json')
    assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    history={}
    for name in ('README.md','README.zh-TW.md','README.en.md'):
        previous=re.findall(r'^\| R\d+ .*$',old(name).decode('utf8'),re.M);current=re.findall(r'^\| R\d+ .*$',(ROOT/name).read_text('utf8'),re.M)
        assert len(previous)==353 and len(current)==357 and current[:353]==previous
        history[name]=dict(old=353,current=357,all_previous_rows_preserved=True)
    goal='docs/product/GOAL_GAPS_20261025.md'
    closures=lambda text:{l.split('|')[1].strip():l.split('|')[-3] for l in text.splitlines() if re.match(r'^\| G\d\d \|',l)}
    previous=closures(old(goal).decode('utf8'));current=closures((ROOT/goal).read_text('utf8'));assert len(current)==38 and previous==current
    provenance=load(ROOT/'docs/assets/gpu-gamut-20261029-r2/SOURCE.json')
    for entry in provenance['files']:
        p=ROOT/'docs/assets/gpu-gamut-20261029-r2'/entry['path'];assert sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes']
    own_docs=['docs/product/GPU_GAMUT.md','docs/releases/CLI_0.1.52_SOURCE.md','docs/validation/GPU色域映射源码实测_2026-10-29.md']
    links=0
    for name in own_docs:
        p=ROOT/name
        for target in re.findall(r'\]\(([^)]+)\)',p.read_text('utf8')):
            if '://' in target or target.startswith('#'):continue
            assert (p.parent/target.split('#')[0]).resolve().exists(),(name,target);links+=1
    result=dict(status='passed',source_cli='0.1.52',source_files=278,source_capabilities=89,source_tests=70,gpu_control_tests=12,
        source_case_calls=18,independent_4K_pixels=8294400,installed_candidate_byte_exact=True,registered_skill_cli='0.1.51',registered_skill_files_unchanged=90,
        runtime_and_namespace_unchanged=True,history=history,all_original_38_closure_cells_unchanged=True,local_doc_links=links,
        live_tests_not_counted_as_passed=['compat-r1','installed-measure-r1','installed-compat-r1'],goal_complete=False)
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
