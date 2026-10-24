"""Publish each N002 preview in three-language manuals and connect the client-selection Skill."""
from pathlib import Path
import hashlib
import json
import re
from urllib.parse import quote

from build_look_profile_docs import traditional

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets/looks-n002-20261024-r1'
LOCAL = ROOT / 'docs/local'


def main():
    manifest = json.loads((ASSETS / 'manifest.json').read_bytes())
    records = manifest['records']
    folder = LOCAL / 'filter-gallery'
    folder.mkdir(exist_ok=True)
    notices = '''# N002 previews: source, transformation and separate rights

These files document actual `agent editor kit` v0.1.0-alpha.3 executions, dated 2026-10-24. The supplied image and the LUTs are separate resources.

## Supplied source image / 用户提供的母图

- Original filename: `N002.png`; 1672×940 RGB, 2,087,113 bytes, no embedded color profile.
- Original SHA-256: `babaa64ce3434a23133c41a1d2b4fad384a5e6707546b527508d4731ba83ab4b`.
- The user supplied this image and explicitly requested all 500 filtered examples in the project README and Skills. This is the recorded basis for this demonstration use. No broader copyright ownership or license grant is inferred.
- Source label: `LicenseRef-User-Supplied-Preview`. **Neither the original nor its filtered images are declared CC0 or covered wholesale by the application MIT license.** Reusing the image independently needs its own rights basis.
- [Unmodified original PNG](source.png), [same-pixel lossless WebP](source.webp), [complete output manifest](manifest.json).

## Actual processing / 实际处理

Each item was rendered with the installed CLI: `look preview --id ID --input source.png --output NEW.png --strength 1`. The interpolation is tetrahedral in encoded SDR RGB. No image-generation model, face processing, spatial retouch or new video rendering was used.

Every `full/*.webp` is a lossless encoding of the native PNG; all 500 decoded RGB arrays are exactly equal. `thumbs/*.webp` are 512×288, quality 90 browsing copies. Contact sheets and the board use resized images and labeled borders. `look-selection.gif` cycles actual still outputs; it is not newly generated video footage. The existing color descriptions are numerical guidance rather than acceptance of this image or all natural footage.

## LUT licenses / LUT 来源与许可

100 MIT (49 Striped Purple / Nixua, 51 t3mujinpack / João Matias), 267 Natron CC-BY-SA-4.0 and 133 FreshLUTs CC0-1.0. Exact per-item creators, original repositories, paths, pinned commits, upstream links, obligations and copied legal notices are in [manifest.json](manifest.json) and the [release notices](../../releases/v0.1.0-alpha.3/THIRD_PARTY.md).

Retain individual LUT notices, creator/source credits and conversion disclosures; the software MIT license does not replace resource terms. These credits record the LUT transformations and do not grant new rights to the underlying supplied image. Natron Hald-to-CUBE conversion/approximation and original curve variants remain disclosed in each measured profile. The gallery preserves the upstream title without implying manufacturer endorsement.

## Per-output attribution / 逐项署名

| # | Stable ID / actual output | LUT creator | LUT license | Pinned source |
|---|---|---|---|---|
'''
    for row in records:
        src = row['source']
        url = src.get('source_url') or f'https://github.com/{src["repository"]}/blob/{src["commit"]}/{quote(src["path"], safe="/")}'
        notices += f"| {row['number']:03} | [`{row['id']}`]({row['full']}) | {row['license']['creator'].replace('|',' / ')} | {row['license']['spdx']} | [Source]({url}) / `{src['commit']}` |\n"
    (ASSETS / 'SOURCE_AND_LICENSES.md').write_text(notices, encoding='utf-8', newline='\n')

    for locale, suffix in [('zh',''), ('tw','.zh-TW'), ('en','.en')]:
        en = locale == 'en'
        pick = lambda zh, english: english if en else zh
        convert = traditional if locale == 'tw' else lambda value: value
        page = '# '+pick('N002 母图 × 500 套滤镜：实际样例与客户选型','N002 supplied still × 500 looks: actual samples and client selection')+'\n\n'
        page += '[简体中文](FILTER_GALLERY.md) · [繁體中文](FILTER_GALLERY.zh-TW.md) · [English](FILTER_GALLERY.en.md)\n\n'
        page += '[Interactive gallery](../assets/looks-n002-20261024-r1/index.html) · [Filter workflow](FILTERS'+suffix+'.md) · [Measured profiles](LOOK_PRESETS'+suffix+'.md) · [Actual executions](../validation/evidence/looks-n002-20261024-r1/render-verification.json)\n\n'
        page += pick('500 套均实际运行安装版 CLI，统一使用本次用户提供的母图，强度 1.0、四面体插值。原图 1672×940；原尺寸无损 WebP 的 RGB 与 CLI PNG 逐像素一致，缩略图仅用于选择。原图无嵌入色彩配置，按编码 SDR RGB 试片。',
                     'Every look was actually executed in the installed CLI on the supplied 1672×940 still, using strength 1.0 and tetrahedral interpolation. Full-size lossless WebP RGB exactly equals CLI PNG RGB; thumbnails are browsing aids. With no embedded source profile this is an encoded-SDR-RGB trial.')+'\n\n'
        page += '![Original and eleven actual looks](../assets/looks-n002-20261024-r1/selection-board.jpg)\n\n'
        page += pick('## 每一套实际样例','## Every actual look sample')+'\n\n'
        page += '| # | '+pick('逐项样例、原尺寸图与 ID','Individual samples, full-size images and IDs')+' |\n|---|---|\n'
        for start in range(0,500,100):
            page += f'| {start+1:03}–{start+100:03} | [100 actual previews](filter-gallery/{start+1:03}-{start+100:03}{suffix}.md) |\n'
        page += '\n'+pick('## 50 套一张的速查总览','## Contact sheets: 50 looks each')+'\n\n'
        for start in range(0,500,50):
            page += f'- [{start+1:03}–{start+50:03}](../assets/looks-n002-20261024-r1/sheets/{start+1:03}-{start+50:03}.jpg)\n'
        page += '\n'+pick('## Agent 向客户展示与记录选择','## Presenting and recording client choices')+'\n\n'
        page += pick('1. 先根据需求选 3–6 套，展示原图与实际样例；附编号、名称、稳定 ID、当前强度和许可。\n2. 客户可报编号/ID，或本地打开交互页筛选、勾选并导出候选 JSON。GitHub 不执行仓库 HTML，下载后直接打开。\n3. 使用 Skill helper 导出客户专属对照板；100% 样例不能冒充 0.65 强度效果。\n4. 在客户实际目标帧上以候选 ID 和真实强度运行 look preview。确认最终 ID、强度、片段/全局作用域后再 apply，保留快照。\n5. 编码成片后检查实际输出与 warning；本图没有证明所有肤色、场景、HDR 或视频时序质量。',
                     '1. Select 3–6 looks for the brief and show the original with actual samples, numbers, names, stable IDs, strength and license.\n2. Clients can give a number/ID or open the offline gallery to filter, shortlist and export JSON. GitHub does not execute repository HTML; open a downloaded copy locally.\n3. Export a client-specific board with the Skill helper. A 100% sample must not be presented as strength 0.65.\n4. Run look preview on the actual target frame with the chosen ID/strength. Record final ID, strength and clip/global scope before application and retain snapshots.\n5. Inspect encoded output/warnings. This image does not establish all skin, scene, HDR or video-temporal quality.')+'\n\n'
        page += '''```powershell
$aekGallery = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --query '黑白' --limit 6
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
```

'''
        page += '[Example board](../assets/looks-n002-20261024-r1/client-shortlist-example/board.jpg) · [Returned selection](../assets/looks-n002-20261024-r1/client-shortlist-example/selection.json) · [Skill procedure](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md)\n\n'
        page += pick('## 来源、强度与展示边界','## Source, strength and display limits')+'\n\n'
        page += pick('母图使用依据是本次用户提供及明确要求展示，未标记为 MIT/CC0。滤镜保留每项 MIT/CC0/CC BY-SA 许可、作者和变更来源。原图权利与 LUT 权利分别记录；[完整说明及逐项署名](../assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md)。500 是不同数值变换，包含同系列曲线变体，不等于 500 个独立风格家族。',
                     'The user supplied the source and explicitly requested these demonstrations; the image is not labeled MIT/CC0. Every LUT retains its MIT/CC0/CC BY-SA license, creator and change/source record. Image and LUT rights are separate; see [complete notices and per-item credits](../assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md). The 500 distinct transforms include related curves rather than 500 unrelated families.')+'\n\n'
        page += '[Desktop screenshot](../assets/looks-n002-20261024-r1/gallery-desktop.png) · [Mobile screenshot](../assets/looks-n002-20261024-r1/gallery-mobile.png) · [Actual UI recording](../assets/looks-n002-20261024-r1/gallery-walkthrough.webm)\n'
        (LOCAL/('FILTER_GALLERY'+suffix+'.md')).write_text(convert(page),encoding='utf-8',newline='\n')
        for start in range(0,500,100):
            book = f'# {start+1:03}–{start+100:03} · N002 '+pick('实际滤镜样例','actual look samples')+'\n\n'
            book += '[Gallery index](../FILTER_GALLERY'+suffix+'.md) · [Original source](../../assets/looks-n002-20261024-r1/source.png) · [Interactive selection](../../assets/looks-n002-20261024-r1/index.html)\n\n'
            book += pick('统一为 100% 强度；点击原尺寸图检查细节。小图经过缩放/有损编码，原尺寸图无损保留 CLI RGB。',
                         'All previews are strength 100%. Open full-size files to inspect details; thumbnails are resized/lossy, while full-size files preserve CLI RGB losslessly.')+'\n\n'
            for row in records[start:start+100]:
                name = row['name'] if en else row['name_zh_tw'] if locale=='tw' else row['name_zh']
                summary = row['summary_en'] if en else row['summary_zh']
                book += f'<a id="preset-{row["id"]}"></a>\n\n## {row["number"]:03} · {name}\n\n'
                book += f'`{row["id"]}` · `{row["category"]}` · {row["license"]["spdx"]} · strength **1.0**\n\n'
                book += summary+'\n\n'
                book += f'![{row["number"]:03} {row["id"]}](../../assets/looks-n002-20261024-r1/{row["thumbnail"]})\n\n'
                book += f'[Full 1672×940 lossless preview](../../assets/looks-n002-20261024-r1/{row["full"]}) · [Original](../../assets/looks-n002-20261024-r1/source.png) · [Measured effect / source / license](../look-profiles/{start+1:03}-{start+100:03}{suffix}.md#preset-{row["id"]})\n\n'
            (folder/f'{start+1:03}-{start+100:03}{suffix}.md').write_text(convert(book).rstrip()+'\n',encoding='utf-8',newline='\n')
        filters = LOCAL / ('FILTERS'+suffix+'.md')
        text = filters.read_text('utf-8')
        begin, end = '<!-- N002-GALLERY-START -->', '<!-- N002-GALLERY-END -->'
        section = begin+'\n\n## '+pick('N002 母图：全部 500 套实际样例与客户选型','N002 supplied still: all 500 real samples and client selection')+'\n\n'
        section += '![Original and actual styles](../assets/looks-n002-20261024-r1/selection-board.jpg)\n\n'
        section += f'[All 500 supplied-image samples](FILTER_GALLERY{suffix}.md) · [Interactive gallery](../assets/looks-n002-20261024-r1/index.html) · [Client Skill workflow](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md)\n\n'
        section += pick('每套统一以用户提供的 1672×940 母图、强度 1.0 实际运行，提供原图、全尺寸无损图、小图与稳定 ID。Agent 可导出客户候选板和 JSON，再对目标素材重新预览选定强度，最后应用到明确片段或全局。原图与 LUT 各自权利分开记录。',
                        'Every look is actually executed on the supplied 1672×940 still at strength 1.0, with original, full-size lossless file, thumbnail and stable ID. Agents can export client boards/JSON, then preview chosen strengths on target media before explicit clip/global application. Source-image and LUT rights remain separate.')+'\n\n'+end
        section = convert(section)
        if begin in text:
            text=re.sub(re.escape(begin)+r'[\s\S]*?'+re.escape(end),lambda m:section,text)
        else:
            at=text.find('\n## ')
            text=text[:at]+'\n\n'+section+'\n'+text[at:]
        filters.write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'numbered_samples_per_language':500,'volumes':15,'gallery_guides':3,'source_notices':1}))


if __name__=='__main__':
    main()
