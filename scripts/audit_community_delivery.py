"""Audit real installed evidence, packaged Skill bytes and current documentation."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import argparse
import ast
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence/community-materials-20261025-r1'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('Preserve earlier audit reports')
    checks = {}
    for name, count in [('cpu', 46), ('gpu', 15), ('portable', 8), ('skill', 11), ('cpu/presentation-correction', 8)]:
        data = json.loads((EVIDENCE / name / 'verification.json').read_bytes())
        assert data['status'].startswith('passed') and data['commands'] == count, (name, data)
        checks[name] = count
    public = ROOT / 'docs/assets/community-materials-20261025-r2'
    media = json.loads((public / 'verification.json').read_bytes())
    assert media['full_decode'] and media['publish_gate_passed'] and media['generated_speech_in_public_media'] is False
    for record in media['files']:
        assert sha(ROOT / record['path']) == record['sha256']
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    assert manifest['release'] == runtime['release'] == 'v0.1.0-alpha.4-local.1'
    assert manifest['manifest_sha256'] == runtime['manifest_sha256']
    assert manifest['skill_count'] == 1 and manifest['module_count'] == 17
    assert len({r['id'] for r in manifest['modules']}) == 17
    for record in manifest['files']:
        path = ROOT / record['path']
        assert path.stat().st_size == record['bytes'] and sha(path) == record['sha256'], record['path']
    package = json.loads((ROOT / 'docs/skills/community-unified-skill-package.json').read_bytes())
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r2.zip'
    assert sha(kit) == package['sha256']
    with zipfile.ZipFile(kit) as z:
        assert [n for n in z.namelist() if Path(n).name == 'SKILL.md'] == ['skills/agent-ffmpeg-local-editor/SKILL.md']
        inventory = json.loads(z.read('KIT-FILES.json'))
        for row in inventory['files']:
            data = z.read(row['path'])
            assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
        for row in manifest['files']:
            assert z.read(row['path']) == (ROOT / row['path']).read_bytes()
    # Published/historical artifacts retain their already recorded digests.
    old = json.loads((ROOT / 'docs/skills/unified-skill-package.json').read_bytes())
    assert sha(ROOT / 'docs/skills' / old['name']) == old['sha256'] == '0650e83b2ac23004a631347ab2ea54ec819e338faa2d191c9e307da91ae4d950'
    bundle = ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.1/agent-editor-kit-v0.1.0-alpha.4-local.1-cp313-win_amd64.zip'
    assert sha(bundle) == 'cf4e55f410582547d7fe56549d4594b4d8f0ee6aff8be24f77408c035fd74ead'
    paths = [ROOT / n for n in ('README.md', 'README.en.md', 'README.zh-TW.md', 'docs/README.md',
        'docs/local/INSTALLATION.md', 'docs/product/CASES.md', 'docs/product/GOAL_GAPS_20261024.md')]
    paths += list((ROOT / 'docs/product').glob('COMMUNITY*.md'))
    paths += list((ROOT / 'docs/product').glob('SKILLS*.md'))
    paths += list((ROOT / 'docs/product').glob('CAPABILITIES*.md'))
    paths += list((ROOT / 'docs/skills').glob('UNIFIED_SKILL*.md'))
    paths += list((ROOT / 'skills/agent-ffmpeg-local-editor').rglob('*.md'))
    links, broken, docs = 0, [], []
    readme_code = []
    for path in paths:
        text = path.read_text('utf8')
        if path.parent == ROOT:
            ids = {c: re.findall(r'^\| (' + c + r'\d\d)(?: /| \|)', text, flags=re.M) for c in 'FSKR'}
            assert {c: len(v) for c, v in ids.items()} == {'F': 48, 'S': 16, 'K': 17, 'R': 37}, (path, ids)
            assert all(len(v) == len(set(v)) for v in ids.values())
            readme_code.append(re.findall(r'```powershell\n(.*?)```', text, re.S))
            assert len(text) > 35000, 'Do not truncate restored full manuals'
        plain = re.sub(r'```[\s\S]*?```', '', text)
        plain = re.sub(r'`[^`\n]+`', '', plain)
        for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', plain):
            if re.match(r'^[a-z]+:', target) or target.startswith('#'):
                continue
            resolved = (path.parent / unquote(target.split('#')[0])).resolve()
            if not resolved.exists():
                broken.append([path.relative_to(ROOT).as_posix(), target])
            links += 1
        docs.append(dict(path=path.relative_to(ROOT).as_posix(), bytes=path.stat().st_size, sha256=sha(path)))
    assert readme_code[0] == readme_code[1] == readme_code[2], 'README command blocks must be identical'
    assert not broken, broken
    catalog = json.loads((ROOT / 'product/src/ai_ad_editor/material_data/catalog.json').read_bytes())
    records = catalog['records']
    assert len(records) == 359 and len({r['id'] for r in records}) == 359
    for r in records:
        source = ROOT / 'product/src/ai_ad_editor/material_data' / r['path']
        assert source.stat().st_size == r['bytes'] and sha(source) == r['sha256'], r['id']
    compiled = []
    for path in list((ROOT / 'scripts').glob('*community*.py')) + list((ROOT / 'scripts').glob('*material*.py')) + list((ROOT / 'product/src/ai_ad_editor').glob('community*.py')) + list((ROOT / 'product/src/ai_ad_editor').glob('material*.py')):
        ast.parse(path.read_text('utf8'), filename=str(path))
        compiled.append(path.relative_to(ROOT).as_posix())
    report = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(), local_links=links,
        readme_commands_identical=True, functional_modules=48, service_modules=16, internal_modules=17,
        registered_skills=1, readme_verification_rows=37, kit_files=package['files'],
        material_files=359, source_fallback=False, original_public_artifacts_unchanged=True,
        actual_tests_separate=checks, new_inference_in_audit=False, documents=docs, parsed_python_scripts=sorted(set(compiled)))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps({k: v for k, v in report.items() if k not in {'documents', 'parsed_python_scripts'}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
