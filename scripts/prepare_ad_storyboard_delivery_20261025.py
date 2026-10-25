"""Update the existing unified Skill only after final installed case verification."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/ad-storyboard-20261025-r1'


def load(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(value, encoding='utf8', newline='\n')


def main():
    installation = load(BASE / 'installation-r2/verification.json')
    assert installation['status'] == 'installed-and-byte-verified' and installation['source_file_count'] == 205
    for name in ('setup-finalize-r1', 'render-continue-r1', 'revision-r1', 'roundtrip-r1'):
        assert load(BASE / name / 'verification.json')['status'] == 'passed', name
    for name, count in (('development-r4', 226), ('installed-r2', 55), ('installed-cli-r2', 122)):
        report = load(BASE / 'tests' / name / 'verification.json')
        assert report['status'] == 'passed' and report['result'] == dict(methods=count, skipped=0, failures=0, errors=0, success=True)
    canonical = ROOT / 'skills/agent-ffmpeg-local-editor'
    draft = ROOT / 'local/agent-ffmpeg/ad-storyboard-skill-draft-r1/references/ad-storyboard.md'
    (canonical / 'references/ad-storyboard.md').write_bytes(draft.read_bytes())
    for relative in ('SKILL.md', 'references/runtime.md'):
        path = canonical / relative
        content = path.read_text('utf8').replace('v0.1.0-alpha.4-local.11', 'v0.1.0-alpha.4-local.12').replace('CLI `0.1.13`', 'CLI `0.1.14`').replace('CLI 0.1.13', 'CLI 0.1.14')
        if relative == 'SKILL.md':
            marker = '- Product ad: ad-creative or content strategy → editor → timeline/template → quality.'
            assert marker in content
            content = content.replace(marker, marker + '\n  For reviewed briefs and local assets, read [ad-storyboard.md](references/ad-storyboard.md)\n  to build multiple editable canvases/durations and revise selected shots.', 1)
        else:
            content += '\n## Editable ad storyboards\n\nRead [ad-storyboard.md](ad-storyboard.md) for `ad storyboard/build/revise`, complete same-language GPU voice batches, separate editable tracks and exact selected-shot changes. Plans bind actual project/media bytes; preview each variant and retain quality/rights review.\n'
        write(path, content)
    path = canonical / 'references/modules/ad-creative/module.md'
    content = path.read_text('utf8').replace('Commands: `advisory; ad plan`.', 'Commands: `advisory; ad plan; ad storyboard; ad build; ad revise`.')
    content += '\nFor actual editable production, read [ad-storyboard.md](../../ad-storyboard.md): a reviewed brief plus actual assets becomes multiple canvases/durations, followed by selected-shot revision. Keep creative claims/evidence explicit and inspect every actual render.\n'
    write(path, content)
    path = canonical / 'references/subtitle-dubbing.md'
    content = path.read_text('utf8').replace('Only Chinese ↔ English is supported.',
        'Translation supports Chinese ↔ English. Matching source/target languages preserve reviewed text and initialize only the voice model; no translation pack or glossary is used.')
    content = content.replace('Prefer configured `--device auto`; inspect both actual providers.',
        'Prefer configured `--device auto`; inspect the actual providers used. Same-language mode has only a voice provider.')
    write(path, content)
    guide = ROOT / 'docs/product/COMMUNITY_LOCAL_DELIVERY.md'
    content = guide.read_text('utf8')
    split = content.index('## CLI 0.1.12')
    head, history = content[:split], content[split:]
    head = head.replace('v0.1.0-alpha.4-local.11/final-r1', 'v0.1.0-alpha.4-local.12/final-r2')
    head = head.replace('v0.1.0-alpha.4-local.11/candidate-r1', 'v0.1.0-alpha.4-local.12/candidate-r2')
    head = head.replace('v0.1.0-alpha.4-local.11', 'v0.1.0-alpha.4-local.12').replace('CLI 0.1.13', 'CLI 0.1.14')
    head = head.replace('ec2edda498a297eb04cc205f929abedfa395ad96eb83710ca5f53cd211cfecd1', installation['archive_sha256'])
    head = head.replace('sha256:37b8cd1ab04ff5d00d0c68d74cdbf98bacaa9e2d042da8e2d61ea6d657391488', installation['manifest_sha256'])
    head = head.replace('unified-skill-r12.zip', 'unified-skill-r13.zip').replace('community-unified-skill-package-0.1.13.json', 'community-unified-skill-package-0.1.14.json')
    history = history.replace('## CLI 0.1.13 当前交付 / Current delivery', '## CLI 0.1.13 历史交付 / Historical delivery')
    content = head + history + '\n## CLI 0.1.14 当前交付 / Current delivery\n\n' + str(installation['archive_bytes']) + ' bytes、205 个产品 Python 文件。新增[可编辑广告分镜/变体/返工](AD_STORYBOARD.md)和保留原文的同语种批量 GPU 配音；[实际案例、失败和边界](../validation/可编辑广告分镜与返工实测_2026-10-25.md)。旧 local.11/r12 和候选 r1 收据保留。公开仍 alpha.3；自然质量和完整原目标继续开放。\n'
    write(guide, content)
    guide = ROOT / 'docs/product/SUBTITLE_DUBBING.md'
    content = guide.read_text('utf8')
    first = content.index('\n')
    content = content[:first] + '\n\n**CLI 0.1.14 新增：** 同语种 en/en、zh-Hans/zh-Hans 或 zh-Hant/zh-Hant 批量配音保持原文，只初始化配音模型，不加载翻译包、重复字幕或应用译后术语表。语音保持完整，仍检查实际时窗。用于[广告分镜流程](AD_STORYBOARD.md)。下文早期翻译/配音记录继续保留。\n' + content[first:]
    write(guide, content)
    target = ROOT / 'docs/product/ad-storyboard-capabilities-cli-0.1.14.json'
    target.write_bytes((BASE / 'installation-r2/capabilities.stdout.json').read_bytes())
    print(json.dumps(dict(status='prepared', cli_version='0.1.14', local_release='v0.1.0-alpha.4-local.12', product_files=205)))


if __name__ == '__main__':
    main()
