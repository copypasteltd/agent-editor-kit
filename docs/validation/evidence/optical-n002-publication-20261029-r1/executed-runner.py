"""Document real N002 optical stills and an offline stable-ID selection page."""
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
PUBLIC = ROOT / 'docs/assets/optical-n002-20261029-r1'


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    proof = ROOT / 'docs/validation/evidence/optical-n002-20261029-r1/verification.json'
    if not proof.is_file():
        print(json.dumps(dict(status='pending', mutated=False)))
        return 2
    r = load(proof)
    assert r['status'] == 'passed' and len(r['templates']) == 8 and r['all8_distinct']
    assert r['source_and_formal_files_unchanged'] and r['model_forwards'] == 0
    catalog = load(ROOT / 'docs/content/effect-packs/optical-v1/catalog.json')
    for item in r['templates']:
        assert sha(ROOT / item['output']) == item['PNG_sha256']
    document = ROOT / 'docs/product/OPTICAL_N002_PREVIEWS.md'
    assert not document.exists()
    lines = ['# N002母图的8套复合光效实际预览', '',
             '与[现有500套LUT滤镜](../assets/looks-n002-20261024-r1/index.html)使用同一张用户提供的N002母图。这8套是额外的可编辑复合光效模板，不改变500套LUT的数量。这里的PNG由独立安装CLI0.1.63实际预览生成，不是示意图或新生成的照片。', '',
             '[离线选型页](../assets/optical-n002-20261029-r1/index.html) · [原始N002](../assets/looks-n002-20261024-r1/source.png) · [逐帧实际证据](../validation/evidence/optical-n002-20261029-r1/verification.json) · [动态样片与完整参数](OPTICAL_EFFECT_PACK.md)', '',
             '![原图与8套实际光效预览](../assets/optical-n002-20261029-r1/contact.png)', '',
             '统一条件：原图1672×940先用Lanczos缩至480×270，无内嵌色彩配置的原图在本例显式按sRGB解释；线性BT.709工作域，再输出sRGB。每项都在12fps的第24帧（2秒／作者时钟180000tick）取样，使用同一套原始参数。半径和色差仍按该480×270来源像素，未声称已自动适配其他分辨率。', '',
             '| 编号 | 名称 | 具体效果 | 本母图实际预览 |', '| --- | --- | --- | --- |']
    cards, choices = [], {}
    for item, actual in zip(catalog['items'], r['templates']):
        ident = item['id']
        assert actual['id'] == ident and actual['template_sha256'] == item['sha256']
        lines.append(f'| {ident} | {item["name_zh"]} / {item["name_en"]} | {item["description_zh"]} | [实际PNG](../assets/optical-n002-20261029-r1/{ident}.png) |')
        choices[ident] = dict(pack=catalog['format'], pack_version=catalog['version'], id=ident,
            template_id=item['template_id'], template_sha256=item['sha256'],
            preview_source='N002-user-supplied', preview_frame=24, preview_seconds=2,
            selection_scope='visual-direction-only; preview again on client footage',
            author_clock_example=dict(ticks_per_second=90000, middle_tick=180000, end_tick=360000))
        cards.append(f'''<article><a href="{ident}.png"><img src="{ident}.png" alt="N002 {ident} actual frame24" loading="lazy" width="480" height="270"></a><h2>{ident} · {html.escape(item['name_zh'])} / {html.escape(item['name_en'])}</h2><p>{html.escape(item['description_zh'])}</p><button type="button" data-id="{ident}" aria-pressed="false">选择 {ident} / Select</button><nav><a href="{ident}.png">实际PNG</a><a href="../../content/effect-packs/optical-v1/{item['template']}">完整参数</a></nav></article>''')
    lines += ['', '## Agent如何接续', '',
              '1. 让客户比较本母图静帧、原图和已有动态MP4／GIF，记录明确模板ID。静帧仅对应2秒时刻，不代表整段动画。',
              '2. 将页面输出的模板ID、版本、SHA256和作者时钟示例交给Agent；核对本地模板文件后，再读取客户实际片段。',
              '3. 审阅既有效果数组。`template apply`替换目标片段完整`effects`数组；需要与LUT或其他效果并存时，先明确合并，不能静默覆盖。',
              '4. 按客户分辨率、原作者时钟和实际素材调整参数，预检后应用、预览、渲染并导出可编辑工程。完整命令见[模板说明](OPTICAL_EFFECT_PACK.md)。', '',
              '## 来源与范围', '',
              'N002与衍生预览使用`LicenseRef-User-Supplied-Preview`；展示依据是用户提供母图并要求在README／Skill中制作预览，未推断更广的版权归属、独立再利用许可或CC0授权。模板参数本身是MIT，与母图的权利分开。[完整来源记录](../assets/optical-n002-20261029-r1/SOURCE.md)。', '',
              '8项完整RGB摘要各不相同，均与同管线无效果基准不同。当前验证的是实际单帧预览、明确参数与同图选型；没有新增模型推理，不是自动打光、美颜、整段自然视频审美或人类质量验收。', '',
              'These eight real CLI63 stills use the same user-supplied N002 image as the 500 LUT examples. They show frame24 at12fps with explicit sRGB interpretation and a480×270 reference size. Template IDs/hashes remain selectable; source-image rights are separate from MIT template parameters. They are still previews, not new video footage or human quality approval.', '']
    document.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
    style = (ROOT / 'docs/assets/optical-pack-20261029-r1/index.html').read_text(encoding='utf-8').split('<style>', 1)[1].split('</style>', 1)[0]
    text = f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>N002 · 8套实际光效选型 · agent editor kit</title><style>{style}article>a>img{{display:block;width:100%;height:auto}}article nav{{margin-bottom:18px}}.baseline{{width:100%;max-width:720px;height:auto}}</style>
<header><p>agent editor kit · N002 optical previews</p><h1>同一母图，8套实际光效</h1><p class="lead">对照原图再选择模板ID。全部来自实际CLI预览：480×270、12fps第24帧（2秒），线性BT.709处理／sRGB输出。下方是静帧；动态效果另看MP4／GIF。</p><nav><a href="../../product/OPTICAL_N002_PREVIEWS.md">完整说明</a><a href="../optical-pack-20261029-r1/index.html">动态样片</a><a href="../looks-n002-20261024-r1/index.html">500套LUT</a><a href="SOURCE.md">来源与使用范围</a></nav><details><summary>查看同管线无效果基准与全部对照</summary><img class="baseline" src="contact.png" alt="N002 original and eight actual optical previews"></details></header>
<main><div class="grid">{''.join(cards)}</div><label for="selection">已选方向 / Selection JSON</label><textarea id="selection" readonly placeholder="点击明确模板ID"></textarea></main><footer>模板参数MIT；母图与衍生预览为LicenseRef-User-Supplied-Preview，未声明CC0或额外再授权。选择只是视觉方向，需要在客户素材上重新预览；应用前审阅完整effects数组替换。</footer>
<script>const choices={json.dumps(choices, ensure_ascii=False)};
document.querySelectorAll('button[data-id]').forEach(button=>button.addEventListener('click',()=>{{document.querySelectorAll('button[data-id]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelector('#selection').value=JSON.stringify(choices[button.dataset.id],null,2);}}));</script></html>'''
    (PUBLIC / 'index.html').write_text(text, encoding='utf-8', newline='\n')
    save = lambda p, v: p.write_text(json.dumps(v, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    save(PUBLIC / 'manifest.json', dict(files=[dict(path=p.name, bytes=p.stat().st_size, sha256=sha(p))
         for p in sorted(PUBLIC.iterdir()) if p.is_file() and p.name != 'manifest.json']))
    for name, sentence in [
        ('README.md', '**N002母图也已补齐8套实际光效静帧。** 同一母图、同一时刻与明确模板ID，方便客户比较人物和室内镜头的方向；与500套LUT数量分开。'),
        ('README.zh-TW.md', '**N002母圖也已補齊8套實際光效靜幀。** 同一母圖、同一時刻與明確模板ID，方便客戶比較人物與室內鏡頭的方向；與500套LUT數量分開。'),
        ('README.en.md', '**Eight real optical stills are now available on the original N002 image.** The same input/time and stable template IDs support client selection for portrait/interior footage; these templates are separate from the500 LUT count.'),
    ]:
        p = ROOT / name
        old = p.read_text(encoding='utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', old, re.M)
        assert len(old_rows) == 525
        title, sep, rest = old.partition('\n\n')
        added = sentence + ' [Actual N002 previews](docs/product/OPTICAL_N002_PREVIEWS.md) · [N002 selection gallery](docs/assets/optical-n002-20261029-r1/index.html)\n\n![Actual N002 optical comparison](docs/assets/optical-n002-20261029-r1/contact.png)\n\n'
        new = title + sep + added + rest
        assert re.findall(r'^\| R\d+ \|.*$', new, re.M) == old_rows
        p.write_text(new, encoding='utf-8', newline='\n')
    out = ROOT / 'docs/validation/evidence/optical-n002-publication-20261029-r1'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    save(out / 'verification.json', dict(status='published-and-documented', templates=8,
        complete_preview_evidence_sha256=sha(proof), actual_gallery_html_sha256=sha(PUBLIC / 'index.html'),
        README_rows_preserved=525, human_quality_accepted=False, new_model_forwards=0, full_goal_closed=False))
    print(json.dumps(dict(status='published-and-documented', templates=8, README_rows=525)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
