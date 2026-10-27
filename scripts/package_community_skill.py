"""Package the current single Skill and native local installation helpers."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--archive-name', default='agent-editor-kit-community-unified-skill-r2.zip')
    a = p.parse_args()
    out = a.output.resolve()
    if out.exists() or not out.is_relative_to(ROOT):
        raise ValueError('Select a new owned output directory')
    if Path(a.archive_name).name != a.archive_name or not a.archive_name.endswith('.zip'):
        raise ValueError('Use a local ZIP basename')
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    files = {}
    for row in manifest['files']:
        data = (ROOT / row['path']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256'] and len(data) == row['bytes']
        files[row['path']] = data
    for name in ('agent-ffmpeg-local-install-manifest.json', 'register-agent-ffmpeg-local-skills.ps1',
                 'scripts/register_unified_skill.ps1', 'scripts/install_community_pack.py',
                 'scripts/activate_community_runtime.py', 'LICENSE'):
        files[name] = (ROOT / name).read_bytes()
    guide = ROOT / 'docs/product/COMMUNITY_LOCAL_DELIVERY.md'
    if not guide.exists():
        raise ValueError('Write the actual local package/installation guide before packaging')
    for name in ('COMMUNITY_LOCAL_DELIVERY.md', 'COMMUNITY_MATERIALS.md', 'COMMUNITY_MATERIALS.en.md',
                 'COMMUNITY_MATERIALS.zh-TW.md', 'COMMUNITY_MATERIAL_CATALOG.md', 'COMMUNITY_VOICES.md', 'COMMUNITY_ACCEPTANCE.md',
                 'SEMANTIC_RETRIEVAL.md', 'FOUR_STEM_SEPARATION.md', 'JOB_RECOVERY.md',
                 'CTC_ACTIVITY_ALIGNMENT.md', 'SUBTITLE_DUBBING.md', 'SEMANTIC_PROJECT_PACKAGE.md', 'FLOAT_TEXT.md', 'FLOAT_TEXT_COVERAGE.md', 'FLOAT_GPU.md', 'FLOAT_ADJUSTMENTS.md', 'FLOAT_TRACKING.md', 'TRACKING_EDITS.md', 'TRACKING_SOURCE_EDITS.md', 'TRACKING_MAGNETIC.md', 'TRACKING_RETIME.md',
                 'TRACKING_VISIBILITY.md', 'TRACKING_BAKE.md', 'VIDEO_GENERATION.md', 'MODEL_SESSIONS.md', 'PROCEDURAL_PARTICLES.md', 'EMITTER_ANIMATION.md', 'OPTICAL_EFFECTS.md', 'HIGHLIGHT_GLOW.md', 'HDR_DISPLAY.md', 'LIP_SYNC.md', 'GPU_DISPATCH.md', 'SEMANTIC_JOB_RECOVERY.md', 'AD_STORYBOARD.md', 'SEMANTIC_RUNTIME_UPGRADE.md', 'MOTION_PACKS.md', 'AFFINE_RENDERING.md', 'PROJECTION_RENDERING.md', 'OPENCL_PROJECTION.md', 'FLOAT_TRANSITIONS.md'):
        path = ROOT / 'docs/product' / name
        files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    # Keep the Skill inventory byte-identical; externalize only documentation
    # links to evidence/media that is intentionally outside the small kit.
    for name in list(files):
        if not name.startswith('docs/') or not name.endswith('.md'):
            continue
        def link(match):
            target = match[2]
            if re.match(r'^[a-z]+:', target) or target.startswith('#'):
                return match.group()
            plain, mark, fragment = target.partition('#')
            resolved = (ROOT / name).parent.joinpath(plain).resolve()
            if not resolved.is_relative_to(ROOT):
                raise ValueError('Documentation link outside the repository')
            relative = resolved.relative_to(ROOT).as_posix()
            if relative in files:
                return match.group()
            return match[1] + 'https://github.com/copypasteltd/agent-editor-kit/blob/main/' + relative + (mark + fragment if mark else '') + ')'
        files[name] = re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)', link, files[name].decode('utf8')).encode('utf8')
    files['KIT-FILES.json'] = (json.dumps(dict(format='agent-community-single-skill-v1',
        release=manifest['release'], cli_version=manifest['cli_version'], skill_count=1, module_count=17,
        files=[dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
               for name, data in sorted(files.items())]), ensure_ascii=False, indent=2) + '\n').encode('utf8')
    assert [name for name in files if Path(name).name == 'SKILL.md'] == ['skills/agent-ffmpeg-local-editor/SKILL.md']
    out.mkdir(parents=True)
    archive = out / a.archive_name
    with zipfile.ZipFile(archive, 'x') as zipped:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 25, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, data)
    report = dict(format='agent-community-single-skill-package-v1', release=manifest['release'], cli_version=manifest['cli_version'],
        archive=str(archive), bytes=archive.stat().st_size, sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
        files=len(files), skill_count=1, module_count=17, base_application_and_model_archives_separate=True)
    (out / 'package.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
