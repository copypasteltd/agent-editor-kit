"""Package the single registered Skill, native installer and working alpha.3 demo.

This is a new Skill-layout kit, never a replacement alpha.3 release attachment.
Only the reviewed unified inventory is included; legacy sibling Skills are omitted.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

from package_alpha3_public import archive

ROOT = Path(__file__).resolve().parents[1]
NAME = 'agent-editor-kit-unified-skill-r1.zip'


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New package-output directory')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Existing package output is preserved')
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    if manifest['format'] != 'agent-ffmpeg-local-skills-v2' or manifest['skill_count'] != 1:
        raise ValueError('Expected the single-entry Skill manifest')
    content = {}
    for row in manifest['files']:
        path = ROOT / row['path']
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Skill inventory changed: ' + row['path'])
        content[row['path']] = data
    for name in ('agent-ffmpeg-local-install-manifest.json', 'register-agent-ffmpeg-local-skills.ps1',
                 'scripts/register_unified_skill.ps1', 'LICENSE'):
        content[name] = (ROOT / name).read_bytes()
    for name in ('install.py', 'run-example.py'):
        content[name] = (ROOT / 'scripts/release_alpha3' / name).read_bytes()
    for suffix in ('', '.en', '.zh-TW'):
        source = ROOT / ('docs/skills/UNIFIED_SKILL' + suffix + '.md')
        def externalize(match):
            target = match.group(2)
            if re.match(r'^[a-z]+:', target) or target.startswith('#'):
                return match.group()
            if target.startswith('UNIFIED_SKILL'):
                return match.group(1) + target.replace('UNIFIED_SKILL', 'QUICKSTART') + ')'
            plain, marker, fragment = target.partition('#')
            resolved = (source.parent / plain).resolve()
            if not resolved.is_relative_to(ROOT):
                raise ValueError('Guide link outside the repository')
            url = 'https://github.com/copypasteltd/agent-editor-kit/blob/main/' + resolved.relative_to(ROOT).as_posix()
            return match.group(1) + url + (marker + fragment if marker else '') + ')'
        text = re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)', externalize, source.read_text('utf-8'))
        content['QUICKSTART' + suffix + '.md'] = text.encode('utf-8')
    inputs = ROOT / 'docs/assets/release-v0.1.0-alpha.1-r2'
    for name in ('card-1.png', 'card-2.png', 'pulse.wav'):
        content['demo/input/' + name] = (inputs / 'input' / name).read_bytes()
    content['demo/input/LICENSE.txt'] = (inputs / 'LICENSE.txt').read_bytes()
    entries = [n for n in content if Path(n).name == 'SKILL.md']
    if entries != ['skills/agent-ffmpeg-local-editor/SKILL.md']:
        raise ValueError('The kit must contain exactly one Skill entry')
    inventory = {'release': manifest['release'], 'skill_layout': 'single-r1',
                 'registered_skill_count': 1, 'internal_module_count': manifest['module_count'],
                 'files': [{'path': n, 'bytes': len(d), 'sha256': hashlib.sha256(d).hexdigest()}
                           for n, d in sorted(content.items())]}
    content['KIT-FILES.json'] = encoded(inventory)
    output.mkdir(parents=True)
    destination = output / NAME
    archive(destination, list(content.items()))
    report = {'format': 'agent-editor-kit-unified-skill-package-v1', 'skill_layout': 'single-r1',
              'runtime_release': manifest['release'], 'runtime_cli_version': '0.1.2',
              'runtime_archive_unchanged': True, 'registered_skill_count': 1,
              'internal_module_count': manifest['module_count'], 'files': len(content),
              'name': NAME, 'bytes': destination.stat().st_size,
              'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'source_inventory_sha256': hashlib.sha256((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes()).hexdigest()}
    (output / 'unified-skill-package.json').write_bytes(encoded(report))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
