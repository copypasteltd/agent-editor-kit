"""Generate the complete numbered, measured 500-look manual in three languages."""
from pathlib import Path
from collections import Counter
import json
from urllib.parse import quote

from build_look_profile_docs import traditional

ROOT=Path(__file__).resolve().parents[1]
LOCAL=ROOT/'docs/local'


def escape(text):
    return str(text).replace('|',' / ').replace('\n',' ')


def main():
    value=json.loads((ROOT/'product/src/ai_ad_editor/look_data/catalog.json').read_bytes())
    rows=value['records'];assert len(rows)==500
    folder=LOCAL/'look-profiles';folder.mkdir(exist_ok=True)
    categories=Counter(r['category'] for r in rows)
    for locale,suffix in (('zh',''),('tw','.zh-TW'),('en','.en')):
        english=locale=='en'
        convert=traditional if locale=='tw' else lambda s:s
        parts=[('# 500 built-in looks: numbered catalog and actual effects' if english else '# 500 套内置风格：编号、实际作用与完整说明')+'\n',
            '[简体中文](LOOK_PRESETS.md) · [繁體中文](LOOK_PRESETS.zh-TW.md) · [English](LOOK_PRESETS.en.md)\n',
            ('Installed release **v0.1.0-alpha.3**, CLI **0.1.2**, catalog **2.0.0**. Each entry has a stable ID, an original title, source-qualified naming, 13 measured swatches, use suggestions, trial strength, preview/video and an individual license. The first 100 LUT bytes and IDs are preserved.' if english else
             '安装版 **v0.1.0-alpha.3**、CLI **0.1.2**、目录 **2.0.0**。每项包含稳定 ID、原名与来源区分、13 个真实色块测量、场景建议、试用强度、实际预览/视频和独立许可。原 001–100 保留 ID 与 LUT 字节。')+'\n',
            ('**Counting:** 500 distinct numeric transforms, including related upstream curve variants. These are not 500 unrelated style families. Runtime intensity variations and alternate file formats are not counted as additional looks. Six duplicate source transforms were excluded.' if english else
             '**计数口径：500 个不同的数值色彩变换，包含同系列的上游曲线变体；不是 500 个互不相关的风格家族。** 同一 LUT 的运行强度档位和不同文件格式不重复计数；构建时已剔除 6 份重复变换。')+'\n',
            '[Filter workflow](FILTERS'+suffix+'.md) · [Installation](INSTALLATION.md) · [Validation](../validation/LOOK500_20261024.md) · [Catalog JSON](../../product/src/ai_ad_editor/look_data/catalog.json)\n',
            ('## Naming and measurement' if english else '## 命名与测量规则')+'\n',
            ('`sp-` = Striped Purple (49); `t3-` = t3mujinpack (51); `nt-` = Natron (267); `fl-` = FreshLUTs (133). Numbering 001–500 is for reading; commands always use the ID. Natron `curve-plus-N` / `curve-minus-N` preserves the original +/- curve suffix; it does not specify EV or a runtime intensity setting. Film/product names identify community approximations, without manufacturer endorsement.' if english else
             '`sp-` 为 Striped Purple（49），`t3-` 为 t3mujinpack（51），`nt-` 为 Natron（267），`fl-` 为 FreshLUTs（133）。编号 001–500 便于阅读，命令始终使用 ID。`curve-plus-N / curve-minus-N` 保留上游的 +/- 曲线标记，不代表 EV 或运行时强度。胶片/产品原名用于识别社区近似风格，不代表厂商授权或官方算法。')+'\n',
            ('Measurements use full strength, tetrahedral interpolation and encoded SDR RGB, with output clipped to 0..1. Y′ = 0.2126 R′ + 0.7152 G′ + 0.0722 B′, expressed in 0–255 code values; it is not linear luminance or exposure. Span = (Y′75% − Y′25%) / 127.5. Swatches do not establish skin protection. Suggested scenes/intensity are selection starting points, with no natural-footage acceptance. LUTs do not generate grain, glow, vignettes, haze or beauty effects.' if english else
             '测量使用强度 1、四面体插值和编码 SDR RGB，输出截断到 0..1。Y′ = 0.2126 R′ + 0.7152 G′ + 0.0722 B′，以 0–255 码值表示，不是线性亮度或曝光。跨度比 = (Y′75% − Y′25%) / 127.5。肤色色块不代表人脸识别/肤色保护。场景/强度建议只是试片起点，尚无自然画质验收。LUT 不生成颗粒、光晕、暗角、空间雾或美颜。')+'\n',
            ('## Licenses and categories' if english else '## 许可与类别')+'\n',
            '| License | Count | Resource obligation |\n|---|---:|---|',
            '| MIT | 100 | Retain copyright and license notice |',
            '| CC-BY-SA-4.0 | 267 | Credit author/source, state changes; adapted LUT data/previews share alike |',
            '| CC0-1.0 | 133 | No attribution condition; provenance retained |',
            '\n[Original source notices and legal codes](../releases/v0.1.0-alpha.3/THIRD_PARTY.md). Application code remains MIT.\n',
            '| Category | Count |\n|---|---:|']
        parts += [f'| `{k}` | {n} |' for k,n in sorted(categories.items())]
        parts += ['\n'+('Categories follow source collections. Instant and negative-film groups also contain monochrome variants; inspect the measured per-look summary for actual color behavior.' if english else '类别沿用来源分组；拍立得与负片组也含黑白变体。是否去色、中灰偏向和跨度以每套实测说明为准。')+'\n']
        parts += ['\n'+('Uploader input labels are not camera calibration. `fl-0000228-science-fiction-for-flog` is labeled Rec.709 in the frozen source but its title mentions FLog. Its input domain is ambiguous: compare only as an experimental creative look on prepared SDR; do not use it as a verified FLog conversion.' if english else '上传者输入标签不等于相机校准。`fl-0000228-science-fiction-for-flog` 的锁定来源标为 Rec.709，标题却提到 FLog，输入域存在歧义；仅在已准备的 SDR 素材上作为实验创意风格比较，不作为已验证的 FLog 转换。')+'\n']
        parts += ['\n'+('## Detailed profiles, previews and videos' if english else '## 分册：逐项详情、预览与视频')+'\n']
        for start in range(0,500,100):
            end=start+100;name=f'{start+1:03}-{end:03}{suffix}.md'
            parts.append(f'- [{start+1:03}–{end:03}](look-profiles/{name})')
        parts+=['\n'+('## Complete numbered table' if english else '## 完整编号表')+'\n',
            ('| # | Name / stable ID | Actual effect | Suggested use | Trial strength | License |' if english else '| # | 名称 / 稳定 ID | 实际效果 | 建议试片场景 | 试用强度 | 许可 |'),
            '|---|---|---|---|---|---|']
        for row in rows:
            num=row['number'];start=(num-1)//100*100+1;end=start+99
            name=row['name'] if english else row['name_zh']
            effect=row['summary_en'] if english else row['summary_zh']
            scene=row['suggested_use_en'] if english else row['suggested_use_zh']
            strength='–'.join(f'{v:g}' for v in row['suggested_strength_range'])
            parts.append(f'| {num:03} | [{escape(name)}](look-profiles/{start:03}-{end:03}{suffix}.md#preset-{row["id"]})<br>`{row["id"]}` | {escape(effect)} | {escape(scene)} | {strength} | {row["license"]["spdx"]} |')
        (LOCAL/('LOOK_PRESETS'+suffix+'.md')).write_text(convert('\n'.join(parts)+'\n'),encoding='utf-8',newline='\n')
        for start in range(0,500,100):
            end=start+100
            book=[f'# {start+1:03}–{end:03} '+('actual look profiles' if english else '风格实际效果详情')+'\n',
                f'[500-look index](../LOOK_PRESETS{suffix}.md) · [Functional guide](../FILTERS{suffix}.md)\n']
            for row in rows[start:end]:
                m=row['metrics'];look=row['id'];src=row['source']
                url=src.get('source_url') or f'https://github.com/{src["repository"]}/blob/{src["commit"]}/{quote(src["path"],safe="/")}'
                prefix='../../assets/look500-20261024-r1/'
                book += [f'<a id="preset-{look}"></a>\n',f'## {row["number"]:03} · '+escape(row['name'] if english else row['name_zh'])+'\n',
                    f'`{look}` · `{row["category"]}` · {row["license"]["spdx"]} · {row["grid_size"]}³\n',
                    (row['description_en'] if english else row['description_zh'])+'\n',
                    ('Suggested use: '+row['suggested_use_en'] if english else '建议试片：'+row['suggested_use_zh'])+'\n',
                    ('Trial strength: ' if english else '试用强度：')+'–'.join(f'{v:g}' for v in row['suggested_strength_range'])+'; default 1.0.\n',
                    (row['cautions_en'] if english else row['cautions_zh'])+'\n']
                if not english and row.get('editorial_notes_zh'):book+=['补充选型说明：'+row['editorial_notes_zh']+'\n']
                if look=='fl-0000228-science-fiction-for-flog':
                    book += [('Input-domain ambiguity: the uploader label is Rec.709 while the title mentions FLog. Use only as an experimental creative comparison on prepared SDR, not a verified camera-log conversion.' if english else '输入域歧义：上传者标签为 Rec.709，但标题提及 FLog；仅在已准备的 SDR 素材上做实验创意比较，不能作为已验证的相机 Log 转换。')+'\n']
                book+=['| Input swatch | Input RGB | Actual output RGB |\n|---|---|---|']
                for key,s in m['samples'].items():book.append(f'| `{key}` | `{s["input"]}` | `{s["output"]}` |')
                norm=row['normalization']
                book+=['\n'+f'Creator: **{escape(row["license"]["creator"])}** · [Source]({url}) · commit `{src["commit"]}`.\n',
                    f'Conversion: `{norm["method"]}`; 8,192 sampled RGB points; max error {norm["sampled_max_abs_rgb_error"]:.7f}; mean {norm["sampled_mean_abs_rgb_error"]:.7f}. This is numerical approximation, not a perceptual quality score.\n',
                    'License obligations: '+' '.join(row['license']['obligations'])+'\n',
                    f'[License](../../../product/src/ai_ad_editor/look_data/{row["license"]["file"]}) · LUT SHA-256 `{row["sha256"]}`.\n',
                    f'[Actual preview PNG]({prefix}previews/{look}.png) · [Actual video]({prefix}videos/{look}.mp4)\n',
                    f'![{look}]({prefix}previews/{look}.png)\n']
            (folder/f'{start+1:03}-{end:03}{suffix}.md').write_text(convert('\n'.join(book).rstrip()+'\n'),encoding='utf-8',newline='\n')
    print(json.dumps({'status':'generated','profiles_per_language':500,'languages':3,'profile_volumes':15,'categories':dict(categories)},ensure_ascii=False))


if __name__=='__main__':main()
