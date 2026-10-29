"""Activate reviewed CLI60 Skill/runtime together, preserving native discovery and rollback."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/music-loop-20261029-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf-8')


def atomic(path, content):
    temporary = path.with_name(path.name+'.cli60-activation-'+uuid.uuid4().hex+'.tmp')
    created = False
    try:
        with temporary.open('xb') as stream:
            created = True
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--stage-run', default='r1')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    assert all(v.replace('-', '').isalnum() for v in [args.run, args.stage_run])
    gates = {'installation':BASE/'installation-candidate-r1/verification.json',
        'candidate':BASE/'staged-actual-case-r1/verification.json',
        'staged_gpu':BASE/'staged60-gpu-r1/verification.json',
        'source_gpu':BASE/'source60-gpu-r1/verification.json',
        'installed_gpu':BASE/'installed60-gpu-r1/verification.json',
        'source_loop':BASE/'actual-case-r1/verification.json',
        'installed_loop':BASE/'installed-actual-case-r1/verification.json',
        'source_loop_tests':BASE/'targeted-r1/verification.json',
        'installed_loop_tests':BASE/'installed60-loop-r1/verification.json'}
    for mode in ['source60', 'installed60']:
        for group in ['bootstrap', 'control', 'selection', 'semantic', 'contracts']:
            gates[mode+'_'+group] = BASE/(mode+'-'+group+'-r1/verification.json')
    missing = [name for name,path in gates.items() if not path.is_file()]
    if missing:
        print(json.dumps(dict(status='pending',ready=False,missing=missing,mutated=False,activated=False)))
        return 2
    reports = {name:load(path) for name,path in gates.items()}
    for name,report in reports.items():
        assert report['status'] == ('installed-and-byte-verified' if name == 'installation' else 'passed'),name
    installation = reports['installation']
    installed = Path(installation['installed']).resolve()
    assert installation['cli_version'] == '0.1.60'
    assert installed.is_relative_to((ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.58').resolve())
    for mode in ['source60','installed60']:
        for group,count in [('bootstrap',31),('control',19),('selection',57),('semantic',104),('contracts',400)]:
            report = reports[mode+'_'+group]
            assert report['cli_version']=='0.1.60' and report['tests']==count and report['frozen_equal']
            assert report['failures']==report['errors']==report['skipped']==0
            for name,digest in report['file_hashes'].items():
                assert sha(ROOT/name)==digest,name
            if mode == 'installed60':
                assert report['source_fallback'] is False and report['source_and_installed_equal']
                assert Path(report['installed']).resolve() == installed
    for name in ['source_gpu','installed_gpu','staged_gpu']:
        report = reports[name]
        assert report['cli_version']=='0.1.60' and report['actual_CUDA_model'] and report['frozen_equal']
        assert report['complete_PCM_replay_equal'] and report['complete_PCM_bytes']==1124160
        assert report['complete_PCM_sha256']==reports['source_gpu']['complete_PCM_sha256']
        if name != 'source_gpu':
            assert report['complete_source_installed_PCM_equal'] and report['source_fallback'] is False
            assert Path(report['installed']).resolve()==installed
    assert reports['staged_gpu']['actual_PowerShell_entry'] and reports['staged_gpu']['candidate_files_unchanged']
    for name in ['source_loop','installed_loop','candidate']:
        report=reports[name]
        assert report['status']=='passed' and report['cli_version']=='0.1.60'
        assert report['complete_package_recipe_repair_PCM_equal'] and report['complete_repeated_PCM_equal']
        assert report['complete_repaired_PCM_bytes']==2557440
        assert report['complete_repaired_PCM_sha256']==reports['source_loop']['complete_repaired_PCM_sha256']
    for name in ['installed_loop','candidate']:
        report=reports[name]
        assert report['complete_source_installed_PCM_equal'] and report['source_fallback'] is False
        assert Path(report['installed']).resolve()==installed
    for name in ['source_loop_tests','installed_loop_tests']:
        report=reports[name]
        assert report['tests']==37 and report['frozen_equal']
        assert report['failures']==report['errors']==report['skipped']==0
        assert all(sha(ROOT/path)==pin for path,pin in report['file_hashes'].items())
    candidate = reports['candidate']
    assert candidate['actual_PowerShell_entry'] and candidate['cli_version']=='0.1.60'
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT/'local/agent-ffmpeg/runtime.json'
    assert all(sha(Path(path))==pin for path,pin in installation['registered_skill_file_hashes'].items())
    manifest = load(namespace)
    assert manifest['cli_version']=='0.1.59' and manifest['skill_count']==1 and manifest['module_count']==17
    folder = ROOT/'skills/agent-ffmpeg-local-editor'
    assert args.stage_run=='r1'
    stage = ROOT/'local/agent-ffmpeg/music60-skill-stage-r1/skills/agent-ffmpeg-local-editor'
    files = {p.relative_to(stage).as_posix():sha(p) for p in stage.rglob('*') if p.is_file()}
    assert files==candidate['candidate_files'] and len(files)==93
    assert sum(Path(n).name=='SKILL.md' for n in files)==1
    assert len(list((stage/'references/modules').glob('*/module.md')))==17
    for row in manifest['files']:
        assert sha(ROOT/row['path'])==row['sha256']
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert discovery.resolve(strict=True)==folder.resolve()
    source_pins = {p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    assert len(source_pins)==283 and source_pins=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
    if not args.apply:
        print(json.dumps(dict(status='ready',ready=True,mutated=False,activated=False,files=93,public_entries=1,modules=17)))
        return 0
    out = BASE/('skill60-activation-'+args.run)
    out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    old_namespace,old_runtime=namespace.read_bytes(),runtime.read_bytes()
    old_files={name:(folder/name).read_bytes() for name in files}
    (out/'previous-namespace.json').write_bytes(old_namespace)
    (out/'previous-runtime.json').write_bytes(old_runtime)
    for name,content in old_files.items():
        backup=out/'previous-skill'/name
        backup.parent.mkdir(parents=True,exist_ok=True)
        backup.write_bytes(content)
    config=load(runtime)
    next_config=copy.deepcopy(config)
    next_config.update(release='v0.1.0-alpha.4-local.58',installed_directory=str(installed),
        manifest_sha256=installation['manifest_sha256'],launcher_sha256=sha(installed/'run.py'))
    transition=copy.deepcopy(config)
    transition['release']='transition-cli60-not-ready'
    gate_pins={name:dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for name,p in gates.items()}
    journal=dict(status='prepared',cli_version='0.1.60',gates=gate_pins,
                 crash_recovery='restore previous-skill,previous-namespace.json,previous-runtime.json;backup retained on E')
    (out/'journal.json').write_bytes(encoded(journal))
    calls=[]
    try:
        # Fail closed during the short multi-file transition. Preserve the
        # existing C junction; all new writes remain on E.
        atomic(runtime,encoded(transition))
        for name in files:
            target=folder/name
            content=(stage/name).read_bytes()
            if content!=old_files[name]:
                atomic(target,content)
        manifest.update(release=next_config['release'],cli_version='0.1.60',manifest_sha256=installation['manifest_sha256'])
        manifest['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
        manifest['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
            for p in sorted(folder.rglob('*')) if p.is_file()]
        assert len(manifest['files'])==93
        atomic(namespace,encoded(manifest))
        atomic(runtime,encoded(next_config))
        for command in ['version','capabilities']:
            argv=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(discovery/'scripts/run.ps1'),command]
            result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
            (out/(command+'.stdout')).write_bytes(result.stdout)
            (out/(command+'.stderr')).write_bytes(result.stderr)
            calls.append(dict(argv=argv,exit_code=result.returncode))
            assert result.returncode==0,(command,result.stderr[-1000:])
            value=json.loads(result.stdout)
            assert value['ok'] and value['provenance']['cli_version']=='0.1.60'
        assert files=={p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}
        assert discovery.resolve(strict=True)==folder.resolve()
        assert all(sha(ROOT/row['path'])==row['sha256'] for row in manifest['files'])
        assert all(sha(gates[name])==pin['sha256'] for name,pin in gate_pins.items())
    except BaseException as exc:
        atomic(runtime,encoded(transition))
        for name,content in old_files.items():
            if (folder/name).read_bytes()!=content:
                atomic(folder/name,content)
        atomic(namespace,old_namespace)
        atomic(runtime,old_runtime)
        journal.update(status='rolled-back',error=repr(exc),calls=calls)
        (out/'verification.json').write_bytes(encoded(journal))
        raise
    report=dict(status='activated-and-entry-verified',cli_version='0.1.60',release=next_config['release'],
        public_entries=1,modules=17,skill_files=93,discovery_unchanged=True,native_windows=True,
        virtual_environment=False,source_fallback=False,actual_C_drive_entry=True,calls=calls,gates=gate_pins,
        namespace_sha256=sha(namespace),runtime_sha256=sha(runtime),registered_model_case_pending=True,
        natural_quality_accepted=False,full_product_goal_closed=False)
    journal.update(status='committed')
    (out/'journal.json').write_bytes(encoded(journal))
    (out/'verification.json').write_bytes(encoded(report))
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
