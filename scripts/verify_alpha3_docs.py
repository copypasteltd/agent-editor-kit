"""Check complete release READMEs, actual evidence and portable Skill documentation."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote, urlsplit
import argparse
import hashlib
import json
import re
import yaml
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--portable-home', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--published', action='store_true')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Existing evidence is preserved')
    md = MarkdownIt()
    count = 0

    def check_links(path):
        nonlocal count
        for token in md.parse(path.read_text('utf-8-sig')):
            for child in token.children or []:
                value = child.attrGet('href') if child.type == 'link_open' else child.attrGet('src') if child.type == 'image' else None
                if not value or value.startswith('#') or urlsplit(value).scheme or value.startswith('//'):
                    continue
                target = path.parent / unquote(urlsplit(value).path)
                assert target.exists(), f'Missing local link: {path}: {value}'
                count += 1

    readmes = []
    command_sets = []
    for name in ('README.md', 'README.zh-TW.md', 'README.en.md'):
        path = ROOT / name
        text = path.read_text('utf-8')
        groups = {letter: len(re.findall(r'^\| ' + letter + r'\d\d \|', text, re.M)) for letter in ('F', 'S', 'K', 'R')}
        assert groups == {'F': 43, 'S': 12, 'K': 17, 'R': 31 if args.published else 30}, groups
        assert 'without a separate new GitHub Release' not in text and '尚未另建 GitHub Release' not in text
        assert 'releases/tag/v0.1.0-alpha.3' in text and 'run-example.py' in text
        assert text.index('run-example.py') < text.index('| F01 |')
        assert len(re.findall(r'!\[', text)) >= 6
        command_sets.append(re.findall(r'```powershell\n(.*?)```', text, re.S))
        check_links(path)
        readmes.append({'path': name, 'bytes': path.stat().st_size, 'sha256': sha(path), **groups})
    assert command_sets[0] == command_sets[1] == command_sets[2], 'README commands must match in all languages'
    release = ROOT / 'docs/releases/v0.1.0-alpha.3'
    guide_commands = []
    for name in ('QUICKSTART.md', 'QUICKSTART.zh-TW.md', 'QUICKSTART.en.md'):
        path = release / name
        guide_commands.append(re.findall(r'```powershell\n(.*?)```', path.read_text('utf-8'), re.S))
        check_links(path)
    assert guide_commands[0] == guide_commands[1] == guide_commands[2]
    for path in (ROOT / 'docs/README.md', ROOT / 'docs/product/CASES.md', release / 'RELEASE.md', release / 'RELEASE-NOTES.md', release / 'USAGE.md'):
        check_links(path)
    portable_links_before = count
    archived = []
    for path in sorted((args.portable_home / 'skills').rglob('*.md')):
        if 'upstream' in path.relative_to(args.portable_home / 'skills').parts:
            archived.append(path.relative_to(args.portable_home).as_posix())
            continue
        check_links(path)
    portable_links = count - portable_links_before
    workflow = yaml.load((ROOT / '.github/workflows/release-alpha3.yml').read_text('utf-8'), Loader=yaml.BaseLoader)
    assert workflow['on']['push']['tags'] == ['v0.1.0-alpha.3']
    assert workflow['jobs']['publish']['runs-on'] == 'windows-latest' and 'container' not in workflow['jobs']['publish']
    assert workflow['permissions']['contents'] == 'write'
    compiled = []
    paths = list((ROOT / 'scripts/release_alpha3').glob('*.py'))
    paths += [ROOT / 'scripts' / name for name in ('package_alpha3_public.py', 'publish_alpha3_release.py',
              'verify_alpha3_publication.py', 'verify_alpha3_native.py', 'verify_alpha3_gallery_portable.py',
              'verify_alpha3_docs.py', 'readme_release_workflow.py', 'build_product_readmes.py')]
    for path in paths:
        compile(path.read_text('utf-8-sig'), str(path), 'exec')
        compiled.append(path.relative_to(ROOT).as_posix())
    native = json.loads((ROOT / 'docs/validation/evidence/release-v0.1.0-alpha.3-r1/verification.json').read_bytes())
    gallery = json.loads((ROOT / 'docs/validation/evidence/release-v0.1.0-alpha.3-r1/gallery-portable/verification.json').read_bytes())
    assert native['actual_cli_calls'] == 20 and len(native['skills']) == 17 and gallery['full_previews_verified'] == 500
    assets = ROOT / 'docs/assets/release-v0.1.0-alpha.3-r1'
    media = json.loads((assets / 'manifest.json').read_bytes())
    for row in media['assets']:
        assert sha(assets / row['path']) == row['sha256']
    lock = json.loads((release / 'public/assets.lock.json').read_bytes())
    assert len(lock['assets']) == 10
    if args.published:
        publication = json.loads((ROOT / 'docs/validation/evidence/release-v0.1.0-alpha.3-r1/publication.json').read_bytes())
        assert publication['status'] == 'published-and-download-verified' and len(publication['assets']) == 10
    report = {'status': 'passed', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'readmes': readmes, 'local_markdown_links_checked': count,
              'portable_skill_links_resolve_with_optional_gallery': portable_links,
              'upstream_archives_excluded_from_portable_link_claim': archived,
              'upstream_archive_limit': 'Verbatim historical references retain their original relative-path context. Current installed-release contracts take precedence. An initial broader link check found an inherited ../../docs/specs policy link that does not resolve from the relocated upstream archive.',
              'powershell_blocks_identical_across_three_readmes': True,
              'powershell_blocks_identical_across_three_guides': True,
              'workflow_native_windows_and_exact_tag': True, 'python_sources_compiled': compiled,
              'native_receipt_and_demo_media_verified': True, 'published': args.published,
              'historical_receipts_rewritten': False, 'historical_kernel_suite_rerun': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': 'passed', 'readmes': 3, 'local_links': count, 'portable_skill_links': portable_links,
                      'public_assets': 10, 'published': args.published}))


if __name__ == '__main__':
    main()
