"""Synchronize current three-language summaries and actual installed capability fields."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def links(line, parent):
    def replace(match):
        target = match[2]
        if re.match(r'^[a-z]+:', target, re.I) or target.startswith('#'):
            return match.group()
        plain, mark, fragment = target.partition('#')
        local = ROOT/plain
        relative = Path(os.path.relpath(local, parent)).as_posix()
        return match[1] + relative + mark + fragment + ')'
    return re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)', replace, line)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capabilities', type=Path, required=True,
                        help='actual captured installed JSON envelope under docs/product')
    args = parser.parse_args()
    response_path = args.capabilities.resolve(strict=True)
    assert response_path.parent == ROOT/'docs/product'
    response = json.loads(response_path.read_bytes())
    assert response['ok'] and response['command'] == 'capabilities'
    entries = response['data']['capabilities']
    field_blocks = '\n\n'.join('### `'+key+'`\n\n```json\n'+
        json.dumps(value, ensure_ascii=False, indent=2)+'\n```' for key, value in entries.items())+'\n\n'
    records = []
    for suffix, readme in [('', 'README.md'), ('.zh-TW', 'README.zh-TW.md'), ('.en', 'README.en.md')]:
        path = ROOT/('docs/product/CAPABILITIES'+suffix+'.md')
        original = text = path.read_text('utf-8-sig')
        canonical = (ROOT/readme).read_text('utf-8-sig')
        current_block = ('<!-- community-current -->\n\n'
            '**CLI 0.1.24 / alpha.4-local.22 / r25 kit · 1 Skill / 17 modules.**\n\n'
            'Explicit native Float32 GPU affine/normal composition/text colors/word selection with owned worker cleanup; 4K text, reusable native byte coverage and linear composition; Float32 titles/inline captions/typewriter/word highlights/plain SRT and transitions/source handles/group edges, native OpenCL crop/affine/child-canvas projection, portable motion/capture, editable ad variants, semantic runtime relocation, '
            'joint subtitle dubbing, GPU voice/translation and the existing resource/quality modules.\n\n'
            '[Float32 GPU workflow](FLOAT_GPU.md) · [4K text/coverage workflow](FLOAT_TEXT_COVERAGE.md) · [Float32 text workflow](FLOAT_TEXT.md) · [Float32 transition workflow](FLOAT_TRANSITIONS.md) · [GPU projection workflow/preview](OPENCL_PROJECTION.md) · [Motion workflow](MOTION_PACKS.md) · [Ad workflow](AD_STORYBOARD.md) · '
            '[Runtime relocation](SEMANTIC_RUNTIME_UPGRADE.md) · [Current installation](COMMUNITY_LOCAL_DELIVERY.md) · '
            '[75 actual declarations]('+response_path.name+'). Full target conditions remain open.\n\n'
            '<!-- /community-current -->')
        text = re.sub(r'<!-- community-current -->.*?<!-- /community-current -->',
                      lambda _: current_block, text, count=1, flags=re.S)
        for prefix, count in [('F', 57), ('S', 20)]:
            old_rows = list(re.finditer(r'^\| '+prefix+r'\d{2}\s*\|.*$', text, re.M))
            rows = re.findall(r'^\| '+prefix+r'\d{2}\s*\|.*$', canonical, re.M)
            assert len(rows) == count and old_rows
            assert len(old_rows) == len(set(m.group().split('|')[1].strip() for m in old_rows))
            replacement = '\n'.join(links(line, path.parent) for line in rows)
            text = text[:old_rows[0].start()] + replacement + text[old_rows[-1].end():]
        first = re.search(r'^### `[^`]+`\s*$', text, re.M)
        assert first
        tail = re.search(r'^## [^\n]+', text[first.start():], re.M)
        end = first.start()+tail.start() if tail else len(text)
        text = text[:first.start()]+field_blocks+text[end:]
        text = re.sub(r'(\[(?:Machine response|机器响应|機器回應)\]\()[^)]+\)',
                      lambda m: m[1]+response_path.name+')', text)
        # Captured versioned evidence replaces only current fields; explanatory
        # workflow sections and historical failure references stay intact.
        path.write_text(text, encoding='utf-8', newline='\n')
        for prefix, count in [('F',57),('S',20)]:
            assert len(re.findall(r'^\| '+prefix+r'\d{2}\s*\|',text,re.M))==count
        assert len(re.findall(r'^### `[^`]+`\s*$',text,re.M))==len(entries)
        records.append(dict(path=path.relative_to(ROOT).as_posix(),functional_rows=57,service_rows=20,
                            actual_capability_fields=len(entries),changed=text!=original))
    print(json.dumps(records,ensure_ascii=False))


if __name__=='__main__': main()
