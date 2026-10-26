"""Verify the single-entry r30 kit without changing actual Codex discovery."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/tracking-magnetic-20261026-r1'


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
    def save(name, value):
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r30.zip'
    home = ROOT / 'local/agent-ffmpeg' / ('tracking-magnetic-kit-' + args.run) / '独立工具 包'
    home.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(kit) as archive:
        inventory = json.loads(archive.read('KIT-FILES.json'))
        assert inventory['cli_version'] == '0.1.29'
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
    def run(name, command, cli=False):
        command = list(map(str, command))
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=900, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = OUT / (name + '.stdout.txt'), OUT / (name + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        calls.append(dict(id=name, argv=command, exit_code=result.returncode, json_cli=cli,
                          stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save('calls.json', calls)
        assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')[-3000:]
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
            '--semantic-config', runtime['semantic_config']])
        discovery = home.parent / 'isolated-discovery'
        run('register', [*ps, home / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
                         '-ReceiptPath', OUT / 'registration.json'])
        entry = discovery / 'agent-ffmpeg-local-editor'
        assert entry.resolve() == (home / 'skills/agent-ffmpeg-local-editor').resolve()
        launcher = entry / 'scripts/run.ps1'
        assert run('version', [*ps, launcher, 'version'], True)['cli_version'] == '0.1.29'
        run('capabilities', [*ps, launcher, 'capabilities'], True)
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
            ROOT/'docs/assets/tracking-magnetic-20261026-r1/editable-tracking-magnetic.aevpkg.zip','--output',tracking_project],True)
        edit_paths=[p for p in tracking_project.rglob('*') if p.is_file()]
        edit_before={str(p):sha(p) for p in edit_paths}
        edit_input=home.parent/'tracking-edit.json'
        edit_input.write_text(json.dumps(dict(action='reorder',clip_ids=['shot_c'],before_clip_id=None,
            options=dict(sync=True),sync_span_policy='split')),encoding='utf8')
        edit_plan=run('tracking-magnetic-dry-run',[*ps,launcher,'timeline','edit','--project',tracking_project,
            '--sequence-id','child','--input',edit_input,'--dry-run'],True)
        assert edit_plan['plan']['after_main_order']==['shot_a','shot_b','shot_c']
        changes=edit_plan['plan']['tracking_binding_changes'];assert len(changes)==3
        for change in changes:
            assert change['before']['observations']==change['after']['observations']
            assert change['before']['reference_output_tick']==change['after']['reference_output_tick']
            assert len(change['after']['source_fragments'])==3
        run('validate-tracking-edit-case',[*ps,launcher,'validate','--project',tracking_project],True)
        assert edit_before=={str(p):sha(p) for p in edit_paths}
        save('tracking-edit-plan.json',edit_plan)
        assert actual.resolve() == original_target
        report = dict(status='passed', kit=str(kit), kit_sha256=sha(kit), files=len(names) + 1,
            skill_files=sum(name.startswith('skills/') for name in names), cli_version='0.1.29',
            registered_skills=1, internal_modules=17, process_calls=len(calls),
            json_cli_calls=sum(row['json_cli'] for row in calls), real_discovery_changed=False,
            dry_run_metadata_unchanged=True, dry_run_assets_unchanged=True,
            scope='Actual native Float32 text/transition and magnetic synchronized native tracking reorder planning/validation from a fresh isolated kit registration; dry-run does not render or perform inference.',
            new_model_forwards=0, new_renders=0,
            native_windows=True, virtualization=False, source_fallback=False, generator_sha256=sha(Path(__file__)))
        assert report['files'] == 109 and report['skill_files'] == 73
        report['tracking_edit_dry_run']=True
        report['tracking_edit_binding_changes']=len(changes)
        report['tracking_edit_author_assets_unchanged']=True
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
