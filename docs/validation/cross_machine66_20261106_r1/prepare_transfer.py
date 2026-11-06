"""Freeze the entire second-host batch; require primary acceptance before real execution."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
CODE = ('case.py','remote_baseline.py','remote_control.py','transfer_server.py','prepare_transfer.py')
DOCS = PROJECT / 'docs/validation/cross_machine66_20261106_r1'
EVIDENCE = PROJECT / 'docs/validation/evidence/delivery66-cross-machine-20261106-r1'
ROUND = PROJECT / 'docs/validation/evidence/delivery66-20261106-r1'
HANDOFF = PROJECT / 'docs/validation/evidence/delivery66-handoff-20261106-r1'
EMBEDDED = Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/python.exe')
TOOLS = Path('C:/Users/carzy/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1-full_build/bin')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def freeze():
    assert not DOCS.exists()
    for name in CODE:
        compile((ROOT / name).read_bytes(), name, 'exec')
    DOCS.mkdir(parents=True)
    for name in CODE:
        shutil.copyfile(ROOT / name, DOCS / name)
    records = [dict(path=(DOCS / name).relative_to(PROJECT).as_posix(),
        bytes=(DOCS / name).stat().st_size, sha256=sha(DOCS / name)) for name in CODE]
    output = EVIDENCE / 'upgrade66-code-phase-r1'
    output.mkdir(parents=True, exist_ok=False)
    value = dict(status='complete-operational-code-frozen-before-functional-validation',
        observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), files=records,
        cli_version='0.1.66', baseline_cli_version='0.1.63', code_completed_before_functional_validation=True,
        functional_tests_executed=False, cross_machine_acceptance=False, model_inference=False,
        global_registration_modified=False, generic_delivery_controller_tested=False,
        actual_execution_requires=['source-whole-r6-passed','installed-whole-r6-passed',
            'primary-cli66-media-reference','primary-cli66-portable-kit-passed'],
        full_G34_accepted=False, full_goal_closed=False, virtualization=False)
    save(output / 'verification.json', value)
    print(json.dumps(value, ensure_ascii=False))


def assert_frozen():
    report = load(EVIDENCE / 'upgrade66-code-phase-r1/verification.json')
    assert report['code_completed_before_functional_validation'] and len(report['files']) == len(CODE)
    for row in report['files']:
        assert sha(PROJECT / row['path']) == row['sha256']
        assert sha(ROOT / Path(row['path']).name) == row['sha256']


def ready():
    assert_frozen()
    freeze = load(ROUND / 'freeze-r6/verification.json')
    for key in ('file_hashes','delivery_tool_files','packaging_source_files'):
        for name, pin in freeze[key].items():
            assert sha(PROJECT / name) == pin, name
    for mode in ('source-all','installed-all'):
        report = load(ROUND / (mode + '-r6/verification.json'))
        assert report['status'] == 'passed' and report['cli_version'] == '0.1.66'
        assert report['tests'] == report['discovered_tests'] == 4124
        assert report['failures'] == report['errors'] == report['skipped'] == 0
        assert report['file_hashes'] == freeze['file_hashes'] and report['frozen_equal']
        if mode == 'installed-all':
            assert report['source_fallback'] is False
    built = load(ROUND / 'candidate-r1/verification.json')
    assert built['status'] == 'installed-and-byte-verified' and built['cli_version'] == '0.1.66'
    assert sha(built['archive']) == built['archive_sha256']
    application = {p.name: sha(p) for p in (Path(built['installed']) / 'site/ai_ad_editor').glob('*.py')}
    assert application == built['application_files'] and len(application) == 289
    return freeze, built


def primary():
    _, built = ready()
    assert Path(sys.executable).resolve() == EMBEDDED.resolve(), 'Use the already-tested native interpreter'
    temporary = ROOT / 'primary-temp'
    temporary.mkdir()
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
        PYTHONDONTWRITEBYTECODE='1')
    with (ROOT / 'primary.stdout').open('xb') as stdout, (ROOT / 'primary.stderr').open('xb') as stderr:
        result = subprocess.run([sys.executable, '-I', '-B', '-u', '-X', 'utf8', ROOT / 'case.py',
            'prepare', '--cli-version', '0.1.66', '--root', ROOT / 'primary',
            '--installed', built['installed'], '--tools', TOOLS], cwd=PROJECT, env=env,
            stdout=stdout, stderr=stderr, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, 'Preserve the complete primary logs and failed case'
    report = load(ROOT / 'primary/verification.json')
    assert report['status'] == 'primary-baseline-passed' and report['cli_version'] == '0.1.66'
    assert report['application_files'] == built['application_files']
    assert_frozen()
    print(json.dumps(dict(status='primary-cli66-media-reference-passed',
        package_sha256=report['package_sha256'], application_modules=289,
        complete_RGBA_PCM_equal=True, natural_quality_accepted=False), ensure_ascii=False))


def parcels():
    freeze, built = ready()
    expected = ROOT / 'primary/expected.json'
    accepted = load(ROOT / 'primary/verification.json')
    assert accepted['status'] == 'primary-baseline-passed' and accepted['cli_version'] == '0.1.66'
    assert accepted['application_files'] == built['application_files']
    kit = load(HANDOFF / 'kit-r1/verification.json')
    portable = load(HANDOFF / 'portable-kit-r1/verification.json')
    assert portable['status'] == 'passed' and portable['actual_base_only_configuration']
    assert portable['application_files'] == built['application_files'] and portable['source_fallback'] is False
    assert kit['archive'] == portable['kit_archive'] and kit['archive_sha256'] == portable['kit_sha256']
    assert kit['packaging_source_files'] == portable['packaging_source_files'] == freeze['packaging_source_files']
    assert sha(kit['archive']) == kit['archive_sha256']
    old_private = PROJECT / 'local/agent-ffmpeg/cross-machine63-20261106-r2'
    owner = load(old_private / 'start-intent.json')
    previous = EVIDENCE / 'baseline-remote-r2'
    old = load(previous / 'verification.json')
    assert old['status'] == 'cross-machine-cli63-baseline-passed' and old['actual_offline_install']
    assert old['cli_version'] == '0.1.63' and old['accepted']['complete_RGBA_PCM_equal']
    old_expected = old_private / 'primary/expected.json'
    assert sha(old_expected) == old['downloads_verified']['expected.json']
    paths = [('application.zip', Path(built['archive'])), ('skill.zip', Path(kit['archive'])),
        ('baseline.aevpkg.zip', ROOT / 'primary/baseline.aevpkg.zip'), ('expected.json', expected),
        ('case.py', ROOT / 'case.py'), ('remote_baseline.py', ROOT / 'remote_baseline.py')]
    value = dict(remote_ip='192.168.196.209', remote_hostname='DESKTOP-TE44HE1', cli_version='0.1.66',
        manifest_sha256=built['manifest_sha256'], primary_installed_whole_passed=True,
        primary_portable_kit_passed=True, packaging_source_files=freeze['packaging_source_files'],
        previous=dict(remote_root='C:/dev/agent-editor-kit-validation-20261106-r2', owner_id=owner['owner_id'],
            remote_verification_sha256=sha(previous / 'verification.json'),
            expected_sha256=sha(old_expected), package_sha256=old['downloads_verified']['baseline.aevpkg.zip']),
        files=[dict(name=name, path=str(path), bytes=path.stat().st_size, sha256=sha(path)) for name, path in paths])
    save(ROOT / 'parcels.json', value)
    assert_frozen()
    print(json.dumps(dict(status='six-pinned-upgrade-transfer-roles-prepared', files=len(paths),
        total_bytes=sum(row['bytes'] for row in value['files']), model_inference=False), ensure_ascii=False))


if __name__ == '__main__':
    assert os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('freeze','primary','parcels'))
    {'freeze':freeze,'primary':primary,'parcels':parcels}[parser.parse_args().action]()
