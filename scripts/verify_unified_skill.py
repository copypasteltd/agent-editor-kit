"""Exercise single-entry registration, migration, refusals and a real installed demo.

Native Windows only. Uses a new E-drive workspace and preserves every run/log.
The optional --activate migrates this project's actual Codex discovery junctions.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = 'agent-ffmpeg-local-editor'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit', type=Path, required=True)
    parser.add_argument('--runtime-archive', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--activate', action='store_true')
    args = parser.parse_args()
    work = args.work.resolve()
    evidence = args.evidence.resolve()
    if work.exists() or (evidence / 'verification.json').exists() or (evidence / 'logs').exists():
        raise ValueError('Existing verification output is preserved')
    if not work.is_relative_to(ROOT / 'local/agent-ffmpeg'):
        raise ValueError('Keep native verification artifacts in the owned E-drive local directory')
    work.mkdir(parents=True)
    logs = evidence / 'logs'
    logs.mkdir(parents=True)
    steps = []
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    python = [sys.executable, '-I', '-S', '-B', '-X', 'utf8']

    def run(label, command, *, expected=0, response=False, timeout=300):
        started = time.monotonic()
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, timeout=timeout,
                                creationflags=flags)
        (logs / (label + '.stdout.txt')).write_bytes(result.stdout)
        (logs / (label + '.stderr.txt')).write_bytes(result.stderr)
        row = {'id': label, 'argv': list(map(str, command)), 'exit_code': result.returncode,
               'expected_success': expected == 0, 'seconds': round(time.monotonic() - started, 3)}
        steps.append(row)
        save(evidence / 'commands.json', steps)
        if (expected == 0 and result.returncode != 0) or (expected != 0 and result.returncode == 0):
            raise RuntimeError(label + ': unexpected exit; see retained logs')
        print(json.dumps(row), flush=True)
        if response:
            data = json.loads(result.stdout)
            if expected == 0 and data.get('ok') is False:
                raise RuntimeError(label + ': returned ok=false')
            return data
        return result

    def register(home, discovery, label, *, expected=0):
        receipt = evidence / (label + '.json')
        run(label, ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    home / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
                    '-ReceiptPath', receipt], expected=expected)
        return json.loads(receipt.read_bytes()) if expected == 0 else None

    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    assert manifest['skill_count'] == 1 and manifest['module_count'] == 17
    run('quick-validate', [sys.executable, '-E', '-B', '-X', 'utf8',
        Path.home() / '.codex/skills/.system/skill-creator/scripts/quick_validate.py', ROOT / 'skills' / NAME])
    entry = ROOT / 'skills' / NAME
    assert len(list(entry.rglob('SKILL.md'))) == 1
    links = []
    for path in entry.rglob('*.md'):
        text = re.sub(r'```[\s\S]*?```', '', path.read_text('utf-8'))
        text = text.replace('`![滤镜候选](/absolute/path/to/board.jpg)`', '')
        for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', text):
            if re.match(r'^[a-z]+:', target) or target.startswith('#'):
                continue
            resolved = (path.parent / unquote(target.split('#')[0])).resolve()
            if not resolved.exists():
                raise ValueError('Broken reference: ' + str(path) + ' -> ' + target)
            links.append({'file': path.relative_to(ROOT).as_posix(), 'target': target})
    save(evidence / 'references.json', {'status': 'passed', 'checked': len(links), 'links': links})
    with zipfile.ZipFile(args.kit) as zipped:
        members = zipped.namelist()
        assert [p for p in members if Path(p).name == 'SKILL.md'] == ['skills/' + NAME + '/SKILL.md']
        assert zipped.testzip() is None
        portable = work / 'portable kit 中文'
        zipped.extractall(portable)
    # Actual fresh-directory offline install; no reused site or source fallback.
    run('portable-install', [sys.executable, '-I', '-B', '-X', 'utf8', portable / 'install.py',
                            '--archive', args.runtime_archive], response=True)
    portable_discovery = work / 'portable discovery'
    receipt = register(portable, portable_discovery, 'portable-registration')
    assert receipt['skill_count'] == 1 and receipt['module_count'] == 17 and receipt['created_entry']
    assert len(list(portable_discovery.glob('agent-ffmpeg-local-*'))) == 1
    repeat = register(portable, portable_discovery, 'portable-repeat')
    assert not repeat['created_entry'] and repeat['retired_junction_count'] == 0
    for label, argv in [('version', ['version']), ('doctor', ['doctor']), ('capabilities', ['capabilities']),
                         ('look', ['look', 'inspect', '--id', 't3-kodak-gold-200'])]:
        response = run('registered-' + label, ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                       portable_discovery / NAME / 'scripts/run.ps1', *argv], response=True)
        assert response['ok'] is True
        if label == 'version':
            assert response['data']['cli_version'] == '0.1.2'
    run('portable-demo', [sys.executable, '-I', '-B', '-X', 'utf8', portable / 'run-example.py',
                         '--output', work / 'demo'], response=True)
    demo = json.loads((work / 'demo/verification.json').read_bytes())
    assert demo['cli_commands'] == 20 and demo['frames'] == 180 and demo['full_decode_passed']
    save(evidence / 'demo-verification.json', demo)
    shutil.copyfile(work / 'demo/commands.json', evidence / 'demo-commands.json')

    def fixture(name, *, legacy=False):
        home = work / name
        home.mkdir()
        for source in portable.iterdir():
            if source.name in {'local', 'demo'}:
                continue
            if source.is_dir():
                shutil.copytree(source, home / source.name)
            else:
                shutil.copyfile(source, home / source.name)
        config = home / 'local/agent-ffmpeg/runtime.json'
        config.parent.mkdir(parents=True)
        shutil.copyfile(ROOT / 'local/agent-ffmpeg/runtime.json', config)
        discovery = home / 'discovery'
        discovery.mkdir()
        if legacy:
            plans = []
            for old in manifest['retired_skills']:
                directory = home / 'skills' / old['name']
                directory.mkdir()
                shutil.copyfile(ROOT / 'skills' / old['name'] / 'SKILL.md', directory / 'SKILL.md')
                plans.append({'path': str(discovery / old['name']), 'target': str(directory)})
            plans.append({'path': str(discovery / NAME), 'target': str(home / 'skills' / NAME)})
            plan = home / 'junction-plan.json'
            save(plan, plans)
            initializer = home / 'create-junctions.ps1'
            initializer.write_text("$ErrorActionPreference='Stop'\n"
                "$plan=Get-Content -LiteralPath $args[0] -Raw -Encoding utf8 | ConvertFrom-Json\n"
                "foreach($p in $plan){ New-Item -ItemType Junction -Path $p.path -Target $p.target | Out-Null }\n",
                encoding='utf-8')
            run(name + '-fixture', ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', initializer, plan])
        return home, discovery

    home, discovery = fixture('migration', legacy=True)
    before = {p.name: sha(p / 'SKILL.md') for p in (home / 'skills').iterdir()}
    migrated = register(home, discovery, 'migrate-17-to-1')
    assert migrated['retired_junction_count'] == 16 and not migrated['created_entry']
    assert len(list(discovery.iterdir())) == 1
    assert before == {p.name: sha(p / 'SKILL.md') for p in (home / 'skills').iterdir()}
    stable = register(home, discovery, 'migrate-repeat')
    assert stable['retired_junction_count'] == 0

    # Conflict at a retired name must leave even earlier owned junctions alone.
    home, discovery = fixture('foreign-conflict')
    conflict = discovery / manifest['retired_skills'][-1]['name']
    conflict.mkdir()
    sentinel = conflict / 'sentinel.txt'
    sentinel.write_text('Unrelated content must survive.', encoding='utf-8')
    register(home, discovery, 'refuse-foreign-conflict', expected=1)
    assert sentinel.read_text('utf-8') == 'Unrelated content must survive.'
    assert not (discovery / NAME).exists() and list(discovery.iterdir()) == [conflict]

    home, discovery = fixture('tampered-reference')
    changed = home / 'skills' / NAME / manifest['modules'][1]['reference']
    changed.write_bytes(changed.read_bytes() + b'\nTampered instruction.\n')
    register(home, discovery, 'refuse-tampered-reference', expected=1)
    assert not list(discovery.iterdir())

    home, discovery = fixture('wrong-runtime')
    config = home / 'local/agent-ffmpeg/runtime.json'
    value = json.loads(config.read_bytes())
    value['release'] = 'v0.0.0-invalid'
    save(config, value)
    register(home, discovery, 'refuse-wrong-runtime', expected=1)
    assert not list(discovery.iterdir())

    home, discovery = fixture('edited-specialist', legacy=True)
    changed = home / 'skills' / manifest['retired_skills'][0]['name'] / 'SKILL.md'
    changed.write_bytes(changed.read_bytes() + b'\nLocal customization.\n')
    register(home, discovery, 'refuse-edited-specialist', expected=1)
    assert len(list(discovery.iterdir())) == 17 and changed.read_bytes().endswith(b'Local customization.\n')

    # Exercise a relocated non-editor helper using known arithmetic, not benchmarks.
    campaign = work / 'campaign.json'
    save(campaign, {'campaigns': [{'name': 'Synthetic arithmetic check', 'channel': 'paid_social',
         'spend': 100, 'revenue': 400, 'impressions': 10000, 'clicks': 100, 'leads': 20, 'customers': 10}]})
    helper = portable / 'skills' / NAME / 'references/modules/campaign-analytics/references/upstream/scripts/campaign_roi_calculator.py'
    roi = run('relocated-campaign-helper', [*python, helper, campaign, '--format', 'json'], response=True)
    assert roi['campaigns'][0]['metrics']['roas'] == 4 and roi['campaigns'][0]['metrics']['cpa'] == 10
    live = None
    if args.activate:
        skills_directory = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))) / 'skills'
        source_before = {r['name']: sha(ROOT / 'skills' / r['name'] / 'SKILL.md') for r in manifest['retired_skills']}
        live = register(ROOT, skills_directory, 'host-registration')
        assert live['skill_count'] == 1 and live['module_count'] == 17
        actual = sorted(p.name for p in skills_directory.glob('agent-ffmpeg-local-*'))
        assert actual == [NAME], actual
        assert source_before == {r['name']: sha(ROOT / 'skills' / r['name'] / 'SKILL.md') for r in manifest['retired_skills']}
        run('host-registered-version', ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            skills_directory / NAME / 'scripts/run.ps1', 'version'], response=True)
    report = {'status': 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'runtime_release': 'v0.1.0-alpha.3', 'runtime_cli': '0.1.2',
              'registered_skills': 1, 'internal_modules': 17, 'local_reference_links_checked': len(links),
              'top_level_commands': len(steps), 'demo_cli_commands': 20, 'demo_encoded_frames': 180,
              'expected_refusals': len([s for s in steps if not s['expected_success']]),
              'original_specialist_source_files_preserved': True, 'host_migrated': live is not None,
              'host_retired_junctions': live['retired_junction_count'] if live else None,
              'kit_sha256': sha(args.kit), 'runtime_archive_sha256': sha(args.runtime_archive),
              'demo': demo, 'model_inferences': 0, 'browser_tabs_opened': 0,
              'virtual_environments_used': 0, 'human_listening_review': False,
              'independent_agent_behavior_benchmark': False, 'complete_capcut_parity': False}
    save(evidence / 'verification.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
