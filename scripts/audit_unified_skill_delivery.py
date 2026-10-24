"""Audit the delivered one-entry kit, source preservation and three-language manuals."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import zipfile
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence/unified-skill-20261024-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Existing audit is preserved')
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    verify = json.loads((EVIDENCE / 'verification.json').read_bytes())
    package = json.loads((ROOT / 'docs/skills/unified-skill-package.json').read_bytes())
    kit = ROOT / 'docs/skills' / package['name']
    assert verify['status'] == 'passed' and verify['host_migrated']
    assert verify['initial_host_migration']['retired_junctions'] == 16
    assert json.loads((EVIDENCE / 'native-r2/host-registration.json').read_bytes())['retired_junction_count'] == 16
    assert manifest['skill_count'] == 1 and manifest['module_count'] == 17
    assert sha(kit) == package['sha256'] == verify['kit_sha256']
    assert len({r['id'] for r in manifest['modules']}) == 17
    assert len({r['reference'] for r in manifest['modules']}) == 17
    original = json.loads((EVIDENCE / 'before-manifest.json').read_bytes())
    assert len(original['skills']) == 17
    for row in manifest['retired_skills']:
        assert sha(ROOT / 'skills' / row['name'] / 'SKILL.md') == row['skill_md_sha256']
    for row in manifest['files']:
        path = ROOT / row['path']
        assert sha(path) == row['sha256'] and path.stat().st_size == row['bytes'], row['path']
    with zipfile.ZipFile(kit) as zipped:
        names = zipped.namelist()
        assert [n for n in names if Path(n).name == 'SKILL.md'] == ['skills/agent-ffmpeg-local-editor/SKILL.md']
        assert not any(n.startswith('skills/agent-ffmpeg-local-') and not n.startswith('skills/agent-ffmpeg-local-editor/') for n in names)
        inventory = json.loads(zipped.read('KIT-FILES.json'))
        for row in inventory['files']:
            data = zipped.read(row['path'])
            assert hashlib.sha256(data).hexdigest() == row['sha256'] and len(data) == row['bytes']
        for row in manifest['files']:
            assert zipped.read(row['path']) == (ROOT / row['path']).read_bytes(), row['path']
        assert json.loads(zipped.read('agent-ffmpeg-local-install-manifest.json')) == manifest
    paths = [ROOT / n for n in ['README.md', 'README.zh-TW.md', 'README.en.md',
             'docs/README.md', 'docs/local/INSTALLATION.md']]
    paths += list((ROOT / 'docs/skills').glob('*.md'))
    paths += list((ROOT / 'docs/product').glob('SKILLS*.md'))
    links = 0
    command_sets = []
    docs = []
    for path in paths:
        text = path.read_text('utf-8')
        if path.name.startswith('README') and path.parent == ROOT:
            counts = {c: len(re.findall(r'^\| ' + c + r'\d\d \|', text, re.M)) for c in 'FSKR'}
            assert counts == {'F': 43, 'S': 12, 'K': 17, 'R': 32}, counts
            assert 'agent-editor-kit-unified-skill-r1.zip' in text
            assert '<!-- unified-skill-demo -->' in text and 'demo.gif' in text
            command_sets.append(re.findall(r'```powershell\n(.*?)```', text, re.S))
            assert not re.search(r'\[\x60\$agent-ffmpeg-local-(?!editor)[^\x60]+\x60\]', text)
        plain = re.sub(r'```[\s\S]*?```', '', text)
        for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', plain):
            if re.match(r'^[a-z]+:', target) or target.startswith('#'):
                continue
            resolved = (path.parent / unquote(target.split('#')[0])).resolve()
            assert resolved.exists(), (path, target)
            links += 1
        docs.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    assert command_sets[0] == command_sets[1] == command_sets[2], 'Three README command blocks differ'
    guides = [ROOT / ('docs/skills/UNIFIED_SKILL' + s + '.md') for s in ['', '.zh-TW', '.en']]
    blocks = [re.findall(r'```powershell\n(.*?)```', p.read_text('utf-8'), re.S) for p in guides]
    assert blocks[0] == blocks[1] == blocks[2], 'Three unified guide command blocks differ'
    media = ROOT / 'docs/assets/unified-skill-20261024-r1'
    for row in json.loads((media / 'manifest.json').read_bytes())['files']:
        assert sha(media / row['path']) == row['sha256']
    compiled = []
    for name in ['consolidate_agent_ffmpeg_skills.py', 'package_unified_skill.py', 'verify_unified_skill.py',
                 'readme_unified_skill.py', 'audit_unified_skill_delivery.py', 'readme_release_workflow.py',
                 'build_product_readmes.py', 'update_agent_ffmpeg_local_skills.py']:
        p = ROOT / 'scripts' / name
        compile(p.read_text('utf-8'), str(p), 'exec')
        compiled.append(name)
    report = {'status': 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'registered_skills': 1, 'internal_modules': 17, 'kit_files': len(names),
              'kit_sha256': sha(kit), 'preserved_specialist_sources': len(manifest['retired_skills']),
              'local_document_links_checked': links, 'readme_command_blocks_match': True,
              'guide_command_blocks_match': True, 'readme_functional_groups': 43,
              'readme_service_groups': 12, 'readme_verification_rows': 32,
              'documents': docs, 'compiled_scripts': compiled,
              'independent_agent_behavior_test': False, 'new_inference': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k: v for k, v in report.items() if k not in {'documents', 'compiled_scripts'}}))


if __name__ == '__main__':
    main()
