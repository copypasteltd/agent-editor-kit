"""Stage a single CLI61 Skill only after native installation and complete checks."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_bytes())
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);a=parser.parse_args()
    assert a.run.replace('-','').isalnum()
    paths={'installation':BASE/'installation-candidate-r1/verification.json',
        'source_case':BASE/'actual-case-r1/verification.json',
        'installed_case':BASE/'installed-actual-case-r1/verification.json'}
    for mode in ['source61','installed61']:
        for group in ['bootstrap','control','selection','semantic','contracts','gpu']:
            paths[mode+'_'+group]=BASE/(mode+'-'+group+'-r1/verification.json')
        paths[mode+'_lipsync']=BASE/(mode+'-lipsync-cuda-r1/verification.json')
    paths['source_loop']=BASE/'source61-loop-r1/verification.json'
    paths['installed_loop']=BASE/'installed61-loop-r1/verification.json'
    missing=[k for k,p in paths.items() if not p.is_file()]
    if missing:
        print(json.dumps(dict(status='pending',ready=False,missing=missing,mutated=False)),flush=True)
        return 2
    reports={k:load(p) for k,p in paths.items()}
    assert reports['installation']['status']=='installed-and-byte-verified'
    installed=Path(reports['installation']['installed']).resolve()
    assert installed.is_relative_to((ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.59').resolve())
    assert reports['installation']['cli_version']=='0.1.61' and reports['installation']['source_file_count']==283
    for mode in ['source61','installed61']:
        for group,count in [('bootstrap',31),('control',19),('selection',57),('semantic',104),('contracts',403)]:
            r=reports[mode+'_'+group]
            assert r['status']=='passed' and r['cli_version']=='0.1.61' and r['tests']==count
            assert r['frozen_equal'] and r['failures']==r['errors']==r['skipped']==0
            assert all(sha(ROOT/name)==pin for name,pin in r['file_hashes'].items())
            if mode=='installed61':assert r['source_and_installed_equal'] and Path(r['installed']).resolve()==installed
        r=reports[mode+'_gpu']
        assert r['status']=='passed' and r['actual_CUDA_model'] and r['complete_PCM_replay_equal']
        assert r['code_files']==283 and r['frozen_equal']
        if mode=='installed61':assert r['complete_source_installed_PCM_equal'] and Path(r['installed']).resolve()==installed
    for mode in ['source61','installed61']:
        r=reports[mode+'_lipsync']
        assert r['status']=='passed' and r['cli_version']=='0.1.61' and r['actual_MuseTalk_CUDA']
        assert r['frames']==133 and r['complete_master_RGBA_bytes']==139460608
        assert r['complete_package_rendered_RGBA_PCM_equal'] and r['owned_process_cleanup_passed']
        assert r['model_execution']['CPU_fallback'] is False and r['model_execution']['calls']['unet']==67
        if mode=='installed61':assert r['complete_source_installed_master_and_render_equal']
    for k in ['source_loop','installed_loop']:
        r=reports[k];assert r['status']=='passed' and r['tests']==37 and r['frozen_equal']
        assert r['failures']==r['errors']==r['skipped']==0
        assert all(sha(ROOT/name)==pin for name,pin in r['file_hashes'].items())
    for k in ['source_case','installed_case']:
        r=reports[k];assert r['status']=='passed' and r['complete_package_recipe_repair_PCM_equal']
        assert r['complete_repeated_PCM_equal'] and r['frozen_equal']
    assert reports['installed_case']['complete_source_installed_PCM_equal']
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';runtime=ROOT/'local/agent-ffmpeg/runtime.json'
    live=load(namespace);assert live['cli_version']=='0.1.59' and len(live['files'])==93
    guard={namespace:sha(namespace),runtime:sha(runtime)}
    for item in live['files']:
        p=ROOT/item['path'];assert sha(p)==item['sha256'];guard[p]=item['sha256']
    source=ROOT/'product/src/ai_ad_editor';pins={p.name:sha(p) for p in source.glob('*.py')}
    assert len(pins)==283 and pins=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
    home=ROOT/'local/agent-ffmpeg'/('music61-skill-stage-'+a.run);home.mkdir(exist_ok=False)
    skill=home/'skills/agent-ffmpeg-local-editor'
    for item in live['files']:
        target=home/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes((ROOT/item['path']).read_bytes())
    release='v0.1.0-alpha.4-local.59'
    p=skill/'SKILL.md';text=p.read_text(encoding='utf-8')
    marker='`v0.1.0-alpha.4-local.57` / CLI `0.1.59`';assert text.count(marker)==1
    text=text.replace(marker,'`'+release+'` / CLI `0.1.61`',1)
    text+='\nFor sample-clock loop overlap repair and actual before/after auditions, read [community music](references/community-materials.md#sample-clock-loop-overlap-repair-cli0161). Overlap explicitly shortens the cycle; numerical continuity is not listening approval.\n'
    p.write_text(text,encoding='utf-8')
    p=skill/'references/runtime.md';text=p.read_text(encoding='utf-8')
    text=text.replace('v0.1.0-alpha.4-local.57',release).replace('CLI 0.1.59','CLI 0.1.61')
    p.write_text(text,encoding='utf-8')
    p=skill/'references/community-materials.md'
    with p.open('a',encoding='utf-8') as f:f.write('''

## Sample-clock loop overlap repair (CLI0.1.61)

Use `music repair-loop --project PROJECT --asset-id SOURCE --crossfade-ms 50
--curve raised-cosine --new-asset-id loop1 --dry-run`, inspect the plan,
then omit `--dry-run` to create an audition. Optional `--apply --track-id
track_audio_1` places it on an editable audio track. Use a new ID per revision.
Supported curves are linear and raised-cosine; default overlap is100ms,
maximum5000ms,at least2 samples. Source length must exceed twice the overlap
and be no longer than600seconds. Decode is explicitly48kHz stereo16bit.
The decoded body remains bit-identical; original24bit/compressed precision
is not preserved. Output cycle N-M is shorter by the overlap; do not promise
the original duration or silently pad. Dry-run does not decode and cannot
confirm the final exact sample count or sufficient source length.

Keep `assets/music-loops/loop_<asset-ID-hash>/master.wav`, `recipe.json`
and `SOURCE.json`. A portable project package keeps them and the source.
Re-render with `music repair-loop --project PROJECT --input RECIPE
--new-asset-id loop2`; input requires the original imported asset ID and
exact SHA256. Recipe input cannot be combined with source/curve/overlap
options. Rights, restrictions and verification are inherited, never promoted.
The CPU DSP engine has zero neural forwards and no hidden normalization.

Present the original and repaired WAVs, plus the actual boundary metrics
and shortened duration. A diagnostic PNG/GIF is not an audio audition or
GUI recording. Lower sample-boundary jumps do not prove inaudibility,
phase coherence,beat/phrase continuity,true peak or natural-music quality.
Obtain client selection before treating an audition as approved. Structural
rewriting,neural music and automatic visual semantic matching remain open.
Full commands,C76 before/after three-cycle audio,recipe and editable package:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/MUSIC_LOOP.md
''')
    p=skill/'scripts/run.py';text=p.read_text(encoding='utf-8')
    for key,value in [('MANIFEST',reports['installation']['manifest_sha256']),('RELEASE',release)]:
        text,count=re.subn(r'^'+key+r" = '[^']+'$",key+' = '+repr(value),text,count=1,flags=re.M);assert count==1
    compile(text,str(p),'exec');p.write_text(text,encoding='utf-8')
    config=load(runtime);config.update(release=release,installed_directory=str(installed),
        manifest_sha256=reports['installation']['manifest_sha256'],launcher_sha256=sha(installed/'run.py'))
    target=home/'local/agent-ffmpeg/runtime.json';target.parent.mkdir(parents=True,exist_ok=True);save(target,config)
    candidate={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}
    assert len(candidate)==93 and all(sha(p)==pin for p,pin in guard.items())
    report=dict(status='unregistered-candidate',cli_version='0.1.61',skill=str(skill),installed=str(installed),
        public_entries=1,modules=17,files=93,live_skill_changed=False,activated=False,candidate_files=candidate,
        protected_files={str(p):pin for p,pin in guard.items()},
        gates={str(p):sha(p) for p in paths.values()},requires_actual_PowerShell_loop_and_CUDA_before_activation=True,requires_installed403=True,requires_actual_installed_MuseTalk=True)
    save(home/'STAGING.json',report);print(json.dumps(report,ensure_ascii=False),flush=True);return 0

if __name__=='__main__':raise SystemExit(main())
