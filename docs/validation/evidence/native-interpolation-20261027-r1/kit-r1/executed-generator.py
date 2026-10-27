"""Verify the single-entry r43 kit without changing actual Codex discovery."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/native-interpolation-20261027-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*', args.run)
    OUT = BASE / ('kit-' + args.run)
    OUT.mkdir(exist_ok=False)
    for fixture in ('float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip',
                    'tracking-retime-20261026-r1/editable-tracking-retime.aevpkg.zip',
                    'tracking-visibility-20261026-r2/editable-tracking-visibility.aevpkg.zip'):
        assert (ROOT/'docs/assets'/fixture).is_file(), fixture
    def save(name, value):
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r43.zip'
    home = ROOT / 'local/agent-ffmpeg' / ('native-interpolation-kit-' + args.run) / '独立工具 包'
    home.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(kit) as archive:
        inventory = json.loads(archive.read('KIT-FILES.json'))
        assert inventory['cli_version'] == '0.1.42'
        assert inventory['skill_count'] == 1 and inventory['module_count'] == 17
        names = [row['path'] for row in inventory['files']]
        assert set(archive.namelist()) == set(names) | {'KIT-FILES.json'}
        assert len(archive.namelist()) == len(set(archive.namelist())) == len(names) + 1
        assert sum(Path(name).name == 'SKILL.md' for name in names) == 1
        for row in inventory['files']:
            relative = Path(row['path'])
            assert not relative.is_absolute() and '..' not in relative.parts and ':' not in row['path']
            data = archive.read(row['path'])
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
            if row['path'].startswith('skills/'):
                assert data == (ROOT / relative).read_bytes()
            if row['path'].startswith('docs/') and row['path'].endswith('.md'):
                def externalize(match):
                    target=match[2]
                    if re.match(r'^[a-z]+:',target) or target.startswith('#'):return match.group()
                    plain,mark,fragment=target.partition('#')
                    resolved=(ROOT/relative).parent.joinpath(plain).resolve()
                    assert resolved.is_relative_to(ROOT)
                    name=resolved.relative_to(ROOT).as_posix()
                    if name in names:return match.group()
                    assert resolved.exists(),(relative,target)
                    return match[1]+'https://github.com/copypasteltd/agent-editor-kit/blob/main/'+name+(mark+fragment if mark else '')+')'
                expected=re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)',externalize,(ROOT/relative).read_bytes().decode('utf8')).encode('utf8')
                assert data==expected,('packaged documentation differs from current source',relative)
            target = home / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    devices = json.loads(Path(runtime['community_config']).read_bytes())
    actual = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    original_target = actual.resolve()
    ps = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File']
    calls = []
    def run(name, command, cli=False, *, timeout=900, code=0):
        command = list(map(str, command))
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = OUT / (name + '.stdout.txt'), OUT / (name + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        calls.append(dict(id=name, argv=command, exit_code=result.returncode, json_cli=cli,
                          stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save('calls.json', calls)
        assert result.returncode == code, result.stderr.decode('utf-8', 'replace')[-3000:]
        print(json.dumps(dict(id=name, code=result.returncode)), flush=True)
        if cli:
            value = json.loads(result.stdout.decode('utf-8-sig'))
            assert value['ok']
            return value['data']
    try:
        run('configure', [sys.executable, '-I', '-B', '-u', '-X', 'utf8', home / 'scripts/activate_community_runtime.py',
            '--installed', runtime['installed_directory'], '--packs', Path(devices['voice']['cpu_pack']).parent,
            '--voice-cuda-lib', devices['voice']['cuda_library_directory'],
            '--translation-cuda-lib', devices['translation']['cuda_library_directory'],
            '--semantic-config', runtime['semantic_config'], '--verify-timeout-seconds', '600'], timeout=2600)
        config_paths=[home/'local/agent-ffmpeg'/name for name in ('runtime.json','community-runtime.json')]
        configured={str(path):path.read_bytes() for path in config_paths}
        run('expected-verification-timeout', [sys.executable, '-I', '-B', '-u', '-X', 'utf8', home/'scripts/activate_community_runtime.py',
            '--installed',runtime['installed_directory'],'--packs',Path(devices['voice']['cpu_pack']).parent,
            '--verify-timeout-seconds','1'], code=1)
        assert configured=={str(path):path.read_bytes() for path in config_paths}
        timeouts=[path for path in (home/'local/agent-ffmpeg/activations').glob('*/verification.json')
                  if json.loads(path.read_bytes())['status']=='verification-timeout']
        assert len(timeouts)==1
        timeout_report=json.loads(timeouts[0].read_bytes())
        assert timeout_report['verify_timeout_seconds']==1 and timeout_report['earlier_runtime_configuration_unchanged']
        save('expected-verification-timeout.json',timeout_report)
        discovery = home.parent / 'isolated-discovery'
        run('register', [*ps, home / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
                         '-ReceiptPath', OUT / 'registration.json'])
        entry = discovery / 'agent-ffmpeg-local-editor'
        assert entry.resolve() == (home / 'skills/agent-ffmpeg-local-editor').resolve()
        launcher = entry / 'scripts/run.ps1'
        assert run('version', [*ps, launcher, 'version'], True)['cli_version'] == '0.1.42'
        caps=run('capabilities', [*ps, launcher, 'capabilities'], True)
        assert caps['capabilities']['hardware_acceleration']['float32_projection']['control']['protocol']=='owned-inherited-binary-pipes-v1'
        assert caps['capabilities']['procedural_particles']['emitter_animation']['protocol']=='source-anchored-emitter-keyframes-v1'
        properties=run('emitter-properties', [*ps,launcher,'vfx','animation-properties'],True)
        assert len(properties['properties'])==21
        run('emitter-animate-help', [*ps,launcher,'vfx','animate','--help'])
        assert len(caps['capabilities'])==81
        mouth=caps['capabilities']['native_lip_sync']
        assert mouth['protocol']=='agent-native-interpolation-v1' and mouth['engine']=='musetalk-v15-native-cuda-v1'
        assert mouth['CPU_fallback'] is False and mouth['model_downloads'] is False
        interpolation=caps['capabilities']['native_neural_interpolation']
        assert interpolation['engine']=='rife425-native-cuda-v1' and interpolation['protocol']=='agent-native-frame-interpolation-v1' and interpolation['CPU_fallback'] is False
        run('interpolation-generate-help',[*ps,launcher,'interpolate','generate','--help'])
        run('interpolation-register-help',[*ps,launcher,'interpolate','adapter','register','--help'])
        run('lipsync-generate-help',[*ps,launcher,'lipsync','generate','--help'])
        run('lipsync-register-help',[*ps,launcher,'lipsync','adapter','register','--help'])
        assert caps['capabilities']['native_hdr_display_pipeline']['protocol']=='explicit-display-nits-PQ-HLG-float32-v1'
        assert caps['capabilities']['optical_effects']['protocol']=='author-clock-linear-float32-optical-effects-v1'
        optical=run('optical-catalog', [*ps,launcher,'effects','list','--query','native:float32-optics'],True)
        assert optical['count']==3 and optical['catalog_version']=='0.11.0'
        for name in ('lens_flare','light_leak','rgb_split'):
            inspected=run('optical-'+name,[*ps,launcher,'effects','inspect','--name',name],True)
            assert inspected['effect']['backend']=='native:float32-optics'
        assert caps['capabilities']['highlight_glow']['protocol']=='highlight-derived-separable-float32-glow-v1'
        glow=run('glow-catalog',[*ps,launcher,'effects','list','--query','native:float32-glow'],True)
        assert glow['count']==2
        for name in ('highlight_bloom','film_halation'):
            item=run('glow-'+name,[*ps,launcher,'effects','inspect','--name',name],True)
            assert item['effect']['backend']=='native:float32-glow'
        generation=caps['capabilities']['generative_video_editing']['complete_video_generation']
        assert generation['protocol']=='local-vace-conditioned-video-generation-v1' and len(generation['modes'])==4
        assert caps['capabilities']['standard_native_float_render']['tracking']['visibility_protocol']=='native-transition-point-footprint-v1'
        assert caps['capabilities']['standard_native_float_render']['tracking']['interchange_bake']['protocol']=='native-PTS-tracking-frame-verified-bake-v1'
        assert generation['model_session']['status']=='implemented_with_limits'
        particle_list=run('particle-list', [*ps,launcher,'vfx','list'],True)
        assert particle_list['count']==6
        assert run('particle-inspect', [*ps,launcher,'vfx','inspect','--name','rain'],True)['preset']['version']=='1.0.0'
        run('particle-apply-help', [*ps,launcher,'vfx','apply','--help'])
        run('session-start-help',[*ps,launcher,'media','model-session','start','--help'])
        run('session-status-help',[*ps,launcher,'media','model-session','status','--help'])
        run('session-stop-help',[*ps,launcher,'media','model-session','stop','--help'])
        run('generation-help', [*ps, launcher, 'media', 'generate', '--help'])
        run('transition-help', [*ps, launcher, 'timeline', 'transition', '--help'])
        # Import into this verifier's own directory. A separate registered
        # Skill render must never change our dry-run byte-invariance fixture.
        project = home.parent / '独立验收 工程'
        package = ROOT / 'docs/assets/float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip'
        media = json.loads((package.parent / 'media-manifest.json').read_bytes())
        package_pin = next(row for row in media['files'] if row['path'].endswith('/'+package.name))
        assert sha(package) == package_pin['sha256']
        run('import-case', [*ps, launcher, 'convert', 'import', '--input', package, '--output', project], True)
        paths = [project / name for name in ('project.json', 'rights-ledger.json')]
        paths.extend(sorted((project / 'assets').rglob('*')))
        paths.extend(sorted((project / 'fonts').rglob('*')))
        paths = [path for path in paths if path.is_file()]
        before = {str(path): sha(path) for path in paths}
        planned = run('float-render-dry-run', [*ps, launcher, 'render', '--project', project,
            '--output', project / 'renders/isolated-plan.mkv', '--container', 'mkv',
            '--hardware-encode', 'off', '--dry-run'], True)
        transitions = planned['plan']['delivery']['pixel_pipeline']['timeline']['transitions']
        assert transitions['GPU'] is False and transitions['group_spatial_edges'] is True
        assert len(transitions['patterns']) == 59
        assert sum(len(plan['transitions']) for plan in transitions['source_handle_plans']) == 0
        text = planned['plan']['delivery']['pixel_pipeline']['timeline']['text']
        assert text['protocol']=='native-glyph-linear-float32-paint-v1' and len(text['plans'])==1
        assert text['native_snapshots']==0 and text['GPU'] is False
        assert not (project / 'renders/isolated-plan.mkv').exists()
        run('validate', [*ps, launcher, 'validate', '--project', project], True)
        assert before == {str(path): sha(path) for path in paths}
        tracking_project=home.parent/'跟踪剪辑 工程'
        run('import-tracking-edit-case',[*ps,launcher,'convert','import','--input',
            ROOT/'docs/assets/tracking-retime-20261026-r1/editable-tracking-retime.aevpkg.zip','--output',tracking_project],True)
        edit_paths=[p for p in tracking_project.rglob('*') if p.is_file()]
        edit_before={str(p):sha(p) for p in edit_paths}
        edit_input=home.parent/'tracking-edit.json'
        edit_input.write_text(json.dumps(dict(action='retime',clip_ids=['moving_source'],transform=dict(speed=.5))),encoding='utf8')
        edit_plan=run('tracking-visibility-dry-run',[*ps,launcher,'timeline','edit','--project',tracking_project,
            '--sequence-id','child','--input',edit_input,'--dry-run'],True)
        assert edit_plan['plan']['after_duration_tick']==270000
        context=edit_plan['plan']['steps'][0]['shared_author_context']
        assert context['protocol']=='shared-author-selected-output-v1'
        assert set(context['retimed_clip_ids'])=={'moving_source','follow_marker','child_sound'}
        assert len(edit_plan['plan']['created_sequences'])==1
        assert context['source_observations_preserved'] and not context['model_inference']
        run('validate-tracking-edit-case',[*ps,launcher,'validate','--project',tracking_project],True)
        assert edit_before=={str(p):sha(p) for p in edit_paths}
        save('tracking-edit-plan.json',edit_plan)
        visibility_project=home.parent/'遮罩转场 工程'
        run('import-visibility-case',[*ps,launcher,'convert','import','--input',
            ROOT/'docs/assets/tracking-visibility-20261026-r2/editable-tracking-visibility.aevpkg.zip','--output',visibility_project],True)
        visibility_paths=[p for p in visibility_project.rglob('*') if p.is_file()]
        visibility_before={str(p):sha(p) for p in visibility_paths}
        run('validate-visibility-case',[*ps,launcher,'validate','--project',visibility_project],True)
        visibility=run('visibility-render-plan',[*ps,launcher,'render','--project',visibility_project,'--sequence-id','child',
            '--output',visibility_project/'renders/planned.mkv','--dry-run'],True)
        tracking_visibility=visibility['plan']['delivery']['pixel_pipeline']['timeline']['tracking']
        assert tracking_visibility['visibility_protocol']=='native-transition-point-footprint-v1'
        assert tracking_visibility['bindings']==2 and tracking_visibility['evaluations']==0
        assert visibility_before=={str(p):sha(p) for p in visibility_paths}
        assert not (visibility_project/'renders/planned.mkv').exists()
        save('visibility-render-plan.json',visibility)
        bake_plan=run('bake-export-dry-run',[*ps,launcher,'convert','export','--project',visibility_project,
            '--target-format','package','--bake-tracking','--output',visibility_project/'exports/planned-bake.aevpkg.zip','--dry-run'],True)
        assert bake_plan['tracking_bake_requested'] and not bake_plan['tracking_bake_pixel_verification_executed']
        assert not (visibility_project/'exports/planned-bake.aevpkg.zip').exists()
        assert visibility_before=={str(p):sha(p) for p in visibility_paths}
        save('bake-export-plan.json',bake_plan)
        assert actual.resolve() == original_target
        report = dict(status='passed', kit=str(kit), kit_sha256=sha(kit), files=len(names) + 1,
            skill_files=sum(name.startswith('skills/') for name in names), cli_version='0.1.42',
            registered_skills=1, internal_modules=17, process_calls=len(calls),
            json_cli_calls=sum(row['json_cli'] for row in calls), real_discovery_changed=False,
            dry_run_metadata_unchanged=True, dry_run_assets_unchanged=True,
            scope='Actual native Float32 text/transition and shared-author native tracking retime planning/validation from a fresh isolated kit registration; dry-run does not render or perform inference.',
            new_model_forwards=0, new_renders=0,
            native_windows=True, virtualization=False, source_fallback=False, generator_sha256=sha(Path(__file__)))
        assert report['files'] == 130 and report['skill_files'] == 81
        report['visibility_case_bindings']=2
        report['visibility_author_assets_unchanged']=True
        report['tracking_edit_dry_run']=True
        report['tracking_retime_members']=len(context['retimed_clip_ids'])
        report['tracking_edit_author_assets_unchanged']=True
        report['installer_timeout_preserves_prior_configuration']=True
        report['integrity_checks_skipped']=False
        report['transition_plan'] = transitions
        report['text_plan'] = text
        adjustments=planned['plan']['delivery']['pixel_pipeline']['timeline']['adjustments']
        assert adjustments['active_plans']==0 and adjustments['applied_frames']==0 and not adjustments['GPU']
        tracking=planned['plan']['delivery']['pixel_pipeline']['timeline']['tracking']
        assert tracking['bindings']==1 and tracking['observations']==36 and tracking['evaluations']==0
        assert not tracking['display_keyframes_baked'] and not tracking['model_inference']
        report['tracking_plan']=tracking
        report['adjustment_plan']=adjustments
        save('verification.json', report)
        print(json.dumps({k:v for k,v in report.items() if k not in {'transition_plan','text_plan','adjustment_plan','tracking_plan'}}, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save('failure.json', dict(status='failed', error=repr(exc), calls=calls))
        raise


if __name__ == '__main__':
    main()
