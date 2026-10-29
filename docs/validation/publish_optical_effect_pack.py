"""Publish editable optical content and synchronized docs after real GPU/replay gates."""
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'docs/content/effect-packs/optical-v1'
PUBLIC = ROOT / 'docs/assets/optical-pack-20261029-r1'
EVIDENCE = ROOT / 'docs/validation/evidence/optical-pack-20261029-r1'
FORMAL = ROOT / 'docs/validation/evidence/optical-pack-20261029-registered59-r1'


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    missing = [str(p.relative_to(ROOT)) for p in (EVIDENCE / 'verification.json', FORMAL / 'verification.json') if not p.is_file()]
    if missing:
        print(json.dumps(dict(status='pending', missing=missing, mutated=False)))
        return 2
    report, formal = load(EVIDENCE / 'verification.json'), load(FORMAL / 'verification.json')
    assert report['status'] == formal['status'] == 'passed'
    assert report['cli_version'] == '0.1.63' and formal['cli_version'] == '0.1.59'
    assert report['actual_templates'] == report['actual_package_replays'] == 8
    assert report['full_RGBA_PCM_equal'] and formal['actual_C_drive_Skill_entry']
    assert formal['actual_template_reselection'] == 'OP01-to-OP08'
    assert report['formal_files_unchanged'] == formal['formal_files_unchanged'] == 95
    assert not report['natural_footage_quality_accepted'] and not formal['natural_quality_accepted']
    catalog = load(PACK / 'catalog.json')
    assert sha(PACK / 'catalog.json') == report['catalog_sha256']
    assert len(catalog['items']) == len(report['cases']) == 8
    namespace = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT / 'local/agent-ffmpeg/runtime.json'
    manifest = load(namespace)
    assert manifest['cli_version'] == '0.1.59'
    guard = {namespace: sha(namespace), runtime: sha(runtime)}
    guard.update({ROOT / r['path']: r['sha256'] for r in manifest['files']})
    gpu_results = []
    for item, case in zip(catalog['items'], report['cases']):
        assert item['id'] == case['id'] and sha(PACK / item['template']) == item['sha256'] == case['template_sha256']
        assert case['frames'] == 48 and case['full_RGBA_bytes'] == 24883200 and case['full_PCM_bytes'] == 768000
        assert case['animation_observed'] and case['changed_from_original'] and case['full_project_package_RGBA_PCM_equal']
        for name, pin in case['public_files'].items():
            assert sha(PUBLIC / name) == pin['sha256'] and (PUBLIC / name).stat().st_size == pin['bytes']
        expected_optics = 48 * sum(t in ('lens_flare', 'light_leak', 'chromatic_aberration') for t in item['effects'])
        expected_glow = 48 * sum(t in ('bloom', 'halation') for t in item['effects'])
        for phase in ('render', 'replay-render'):
            gpu = load(EVIDENCE / (item['id'] + '-' + phase + '.stdout'))['data']['delivery']['pixel_pipeline']['projection_acceleration']
            assert gpu['status'] == 'verified' and gpu['request']['mode'] == 'require'
            assert gpu['operations'].get('optics', 0) == expected_optics
            assert gpu['operations'].get('glow', 0) == expected_glow
            assert gpu['native']['device']['name'] == 'NVIDIA GeForce RTX 3060'
            assert gpu['worker_closed'] and gpu['shared_handles_closed'] and not gpu['runtime_failure_CPU_fallback']
            assert gpu['control']['threads_closed'] and gpu['control']['streams_closed']
            assert gpu['render_exit_code'] == gpu['worker_returncode'] == 0
        gpu_results.append(dict(id=item['id'], edited_optics=expected_optics, edited_glow=expected_glow,
                                replay_same=True, owned_GPU_resources_closed=True))
    last = report['cases'][-1]
    assert formal['full_RGBA_sha256'] == last['full_RGBA_sha256']
    assert formal['full_PCM_sha256'] == last['full_PCM_sha256']
    ffprobe=shutil.which('ffprobe');assert ffprobe
    media_probes={}
    for item in catalog['items']:
        for suffix,expected_frames in (('.mp4',48),('.gif',32)):
            p=PUBLIC/(item['id']+suffix)
            result=subprocess.run([ffprobe,'-v','error','-count_frames','-show_streams','-show_format','-of','json',str(p)],
                                  capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            assert result.returncode==0,(p,result.stderr)
            data=json.loads(result.stdout);video=next(s for s in data['streams'] if s['codec_type']=='video')
            assert int(video['nb_read_frames'])==expected_frames
            media_probes[p.name]=dict(width=video['width'],height=video['height'],frames=expected_frames,
                                      average_frame_rate=video['avg_frame_rate'],
                                      stream_duration_seconds=video.get('duration'),
                                      container_duration_seconds=data['format'].get('duration'))
    out = ROOT / 'docs/validation/evidence/optical-pack-publication-20261029-r1'
    out.mkdir(exist_ok=False)
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    acceptance = dict(status='real-template-GPU-and-package-replay-passed', version='1.0.0',
                      candidate_cli='0.1.63', unchanged_registered_cli='0.1.59', templates=8,
                      actual_registered_template_reselection='OP01-to-OP08', complete_registered_candidate_RGBA_PCM_equal=True,
                      frames_per_template=48, duration_seconds=4, width=480, height=270,
                      actual_GPU='NVIDIA GeForce RTX 3060 / OpenCL', neural_forwards=0,
                      source_proof_sha256=sha(EVIDENCE / 'verification.json'),
                      formal_proof_sha256=sha(FORMAL / 'verification.json'), GPU_cases=gpu_results,
                      natural_footage_quality_accepted=False, human_listening_accepted=False,
                      commercial_brand_result_accepted=False, full_goal_closed=False)
    save(PACK / 'ACCEPTANCE.json', acceptance)
    intro = '''# Optical template pack v1 / 可编辑复合光效模板

Eight MIT templates built from existing native optical operators, not eight new kernels or AI models. Each replaces the target clip's complete effects array after review. Preserve existing effects separately or explicitly merge them before applying. Source pixels, Float32 linear working/output signals and the original author clock must be explicit.

Current registered CLI59 actually imported the OP01 project and reselected OP08. All eight templates passed installed CLI63 GPU rendering and full-frame/PCM editable-package replay. This is a 480x270 original product study, not natural-footage aesthetic acceptance.

Use the single `$agent-ffmpeg-local-editor` launcher, inspect the real clip's author duration, then provide `clip_id`, `middle_tick`, `end_tick` in a UTF-8 JSON variables file. For the four-second 90000-tick/s study: `{"clip_id":"hero","middle_tick":180000,"end_tick":360000}`. Radius/shift are source-pixel values; no automatic resolution, crop, slip or duration adaptation.

```powershell
& $entry template apply --project PROJECT --input TEMPLATE_JSON --variables VARIABLES_JSON --dry-run
& $entry template apply --project PROJECT --input TEMPLATE_JSON --variables VARIABLES_JSON
& $entry validate --project PROJECT
& $entry preview frame --project PROJECT --frame 24
```

Dry-run substitutes variables but does not decode or establish final rendering quality. Validate and render before delivery. CPU uses projection acceleration `off`; actual tests used `require`/device `0.0`. Encoding and audio remain their explicitly selected CPU paths. Aesthetic selection does not approve audio, source rights or all uses.

See the repository's `docs/product/OPTICAL_EFFECT_PACK.md` for every parameter, preview, real project package and test boundary. `catalog.json` pins each template; `ACCEPTANCE.json` records actual test scope. The original source PNG/WAV and all previews are distributed separately under the documented media licenses. Templates use MIT; no external weights or assets are required.
'''
    (PACK / 'README.md').write_text(intro, encoding='utf-8', newline='\n')
    archive = PACK.parent / 'optical-v1.zip'
    assert not archive.exists()
    members = [PACK / 'catalog.json', PACK / 'ACCEPTANCE.json', PACK / 'LICENSE', PACK / 'README.md']
    members += [PACK / item['template'] for item in catalog['items']]
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in members:
            z.write(p, 'optical-v1/' + p.name)
    save(PACK.parent / 'optical-v1.sha256.json', dict(archive='optical-v1.zip', bytes=archive.stat().st_size,
         sha256=sha(archive), entries=12, templates=8, license_spdx='MIT', runtime_and_previews_bundled=False))
    cards = []
    selection = {}
    for item in catalog['items']:
        code, name = item['id'], html.escape(item['name_zh'] + ' / ' + item['name_en'])
        description = html.escape(item['description_zh'])
        cards.append(f'''<article><video controls playsinline preload="none" poster="{code}.png" src="{code}.mp4"></video>
<h2>{code} · {name}</h2><p>{description}</p><p class="muted">{html.escape(item['use_cases_zh'])} · 4s · 12fps · MIT</p>
<button type="button" data-id="{code}">选择 {code} / Select</button>
<nav><a href="{code}.gif">GIF</a><a href="{code}.aevpkg.zip">可编辑工程</a><a href="../../content/effect-packs/optical-v1/{item['template']}">完整参数</a></nav></article>''')
        selection[code] = dict(pack='agent-optical-template-pack-v1', pack_version='1.0.0',
                               id=code, template_id=item['template_id'], template_sha256=item['sha256'],
                               selection_scope='visual-direction-only; review on actual client footage',
                               author_clock_example=dict(ticks_per_second=90000, middle_tick=180000, end_tick=360000))
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>8套可编辑复合光效 · agent editor kit</title><style>
:root{color-scheme:dark;background:#101725;color:#e8edf5;font:16px/1.65 system-ui,sans-serif}body{max-width:1280px;margin:auto;padding:32px 24px}a{color:#b8dfff}h1{font-size:clamp(28px,5vw,48px);line-height:1.2;margin:12px 0}h2{font-size:18px}.lead{max-width:850px;color:#b9c7d8}header{margin-bottom:36px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:20px}article{background:#1a2435;border:1px solid #344155;border-radius:14px;overflow:hidden}article h2,article p,article nav{margin:14px 18px}video{display:block;width:100%;aspect-ratio:16/9;background:#0a101d}button{margin:0 18px 6px;padding:10px 16px;border:1px solid #a5bfe8;background:#dceaff;color:#13223b;border-radius:8px;font:inherit;cursor:pointer}button[aria-pressed=true]{background:#f2d597;color:#29210b;border-color:#f2d597}.muted{font-size:13px;color:#a6b6cc}nav{display:flex;gap:18px;flex-wrap:wrap}details{margin:24px 0}details img{max-width:720px;width:100%}textarea{box-sizing:border-box;width:100%;min-height:210px;background:#0b1220;color:#d4e4fc;border:1px solid #4c6283;border-radius:10px;padding:14px;font:14px/1.5 monospace}footer{margin:32px 0;color:#a6b6cc}summary{cursor:pointer}label{display:block;margin:20px 0 8px;font-weight:600}</style>
<header><p>agent editor kit · Optical pack v1</p><h1>8套可编辑复合光效</h1><p class="lead">先播放真实样片，再记录候选ID交给Agent。光效、位置和强度仍可编辑；这里的方向选择需要在客户实际镜头上复核。</p>
<nav><a href="../../product/OPTICAL_EFFECT_PACK.md">完整说明</a><a href="../../content/effect-packs/optical-v1.zip">下载模板包</a><a href="source.png">原始母图</a></nav>
<details><summary>查看原图与8款实际中间帧对照</summary><img src="contact.png" alt="原始产品图与OP01至OP08实际输出对照"></details></header>
<main><div class="grid">''' + '\n'.join(cards) + '''</div><label for="selection">已选方向 / Selection JSON</label><textarea id="selection" readonly placeholder="点击任一模板的选择按钮"></textarea></main>
<footer>8套样片均为4秒、480×270、12fps，使用原创几何产品图与轻声诊断双音。实际RTX3060 OpenCL渲染与完整工程包重放通过；不是自然实拍审美或人类听审结论。模板MIT；原始诊断PNG/WAV为CC0，详见SOURCE.txt。页面无外部资源，视频按需加载。</footer>
<script>const choices=''' + json.dumps(selection, ensure_ascii=False) + ''';
document.querySelectorAll('button[data-id]').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('button[data-id]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));document.querySelector('#selection').value=JSON.stringify(choices[button.dataset.id],null,2);}));
document.querySelectorAll('video').forEach(video=>video.addEventListener('play',()=>document.querySelectorAll('video').forEach(other=>{if(other!==video)other.pause();})));</script></html>
'''
    (PUBLIC / 'index.html').write_text(page, encoding='utf-8', newline='\n')
    # Freeze all public files, excluding the manifest being written.
    save(PUBLIC / 'media-manifest.json', dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
         source='original programmatic study; no natural footage', fps=12, duration_seconds=4, frames=48,
         templates_license='MIT', source_image_and_audio_license='CC0-1.0',
         files={p.name: dict(bytes=p.stat().st_size, sha256=sha(p),
                            measured_media=media_probes.get(p.name)) for p in PUBLIC.iterdir() if p.is_file()}))
    table, details = [], []
    for item in catalog['items']:
        code = item['id']
        table.append(f"| {code} | {item['name_zh']} / {item['name_en']} | {item['description_zh']} | {item['use_cases_zh']} | [MP4](../assets/optical-pack-20261029-r1/{code}.mp4) · [GIF](../assets/optical-pack-20261029-r1/{code}.gif) · [工程包](../assets/optical-pack-20261029-r1/{code}.aevpkg.zip) |")
        template = load(PACK / item['template'])
        details.append(f"### {code} {item['name_zh']}\n\n{item['description_en']}\n\n实际替换的效果参数及作者时钟关键帧：\n\n```json\n" + json.dumps(template['operations'][0]['patch'], ensure_ascii=False, indent=2) + '\n```\n')
    doc = '''# 首批8套可编辑复合光效模板

这是一套可直接调用的MIT内容模板包，复用已有光学内核；没有增加8个新算子或神经模型。每套保留独立效果参数和动画键，可先展示样片，再由Agent应用到明确片段。

[实际选型页](../assets/optical-pack-20261029-r1/index.html) · [模板ZIP](../content/effect-packs/optical-v1.zip) · [摘要](../content/effect-packs/optical-v1.sha256.json) · [逐模板目录](../content/effect-packs/optical-v1/catalog.json)

![原始母图与8款实际输出](../assets/optical-pack-20261029-r1/contact.png)

## 模板清单

| 编号 | 名称 | 实际效果 | 建议选型方向 | 真实样片与可编辑工程 |
| --- | --- | --- | --- | --- |
''' + '\n'.join(table) + '''

## Agent使用流程

1. 用唯一`$agent-ffmpeg-local-editor`入口运行`version`。本轮当前正式入口CLI59已实际导入OP01工程并改选OP08；8套完整案例由独立安装CLI63执行。不能把后者写成已正式注册CLI63。
2. 从客户现有工程读取目标`clip_id`、原作者时钟和来源／工作／输出信号。模板要求`float32-native-v1`；本轮采用线性BT.709、显式sRGB输入／输出，不自动猜色彩。
3. 先显示原素材、真实MP4／GIF与模板ID。选型页仅记录视觉方向；需要在客户素材上再次预览，不自动通过权利、音乐或人物质量审核。
4. 读取该模板JSON。应用会**替换目标片段整条effects数组**，所以必须先审阅既有效果；需要共存时保留原数组并明确合并，不能静默删除。不会覆盖原素材、其他轨或声音。
5. 提供`clip_id`、`middle_tick`、`end_tick`变量。示例为90000 ticks/s、4秒作者时钟；剪裁／滑移／倒放及其他原作者范围需重新核对，不自动适配。半径／色差使用源像素，其他分辨率需要调整参数并验收。
6. dry-run确认替换计划，再实际应用、validate、preview、render并导出可编辑工程。dry-run只替换变量，不证明最终渲染或视听质量。

```powershell
$entry = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$project = 'E:/video-work/optical-demo' # 新空目录
$template = 'E:/dev/sandbox/AI广告剪辑/docs/content/effect-packs/optical-v1/OP08-sunset-halo.json'
$variables = 'E:/video-work/optical-variables.json'
'{"clip_id":"hero","middle_tick":180000,"end_tick":360000}' | Set-Content -LiteralPath $variables -Encoding utf8
& $entry convert import --input 'E:/dev/sandbox/AI广告剪辑/docs/assets/optical-pack-20261029-r1/OP01.aevpkg.zip' --output $project
& $entry template apply --project $project --input $template --variables $variables --dry-run
& $entry template apply --project $project --input $template --variables $variables
& $entry validate --project $project
& $entry preview frame --project $project --frame 24
& $entry render --project $project --output "$project/renders/selected.mp4" --projection-acceleration require --projection-device 0.0
```

## 实际验收和边界

8套各4秒／12fps／48帧、480×270，实际RTX3060 OpenCL操作而非仅探测编码器。每套完整24883200字节RGBA及768000字节PCM在工程导出／导入后相同；8套输出摘要互不相同，首帧与中间帧不同，原始图与效果图不同。GPU操作、进程、控制线程和共享句柄均检查关闭，没有运行时CPU回退。硬件编码关闭；H.264交付编码、颜色转换及音频仍CPU。

真实C盘统一Skill CLI59导入OP01后改选OP08；全部RGBA／PCM与独立安装CLI63的OP08相同。这里只验证一套正式入口改选，不冒充8套均经正式入口独立重跑。完整406-r2、正式Skill63及r58工具包有各自门禁，不被本内容库验证替代。

[8套真实执行及包重放](../validation/evidence/optical-pack-20261029-r1/verification.json) · [正式CLI59改选](../validation/evidence/optical-pack-20261029-registered59-r1/verification.json) · [GPU逐项与跨入口对照](../content/effect-packs/optical-v1/ACCEPTANCE.json) · [媒体摘要](../assets/optical-pack-20261029-r1/media-manifest.json)。样片为项目原创几何产品图与诊断双音；PNG／WAV为CC0、模板MIT，没有外部影像／权重或真实品牌素材。

这是G06／G29首批可用复合内容，不是成熟全品类库、AI语义效果、3D镜头模拟、美颜、重打光、自然实拍审美／连续听审或完整剪映等价验收。全部38项原关闭条件保持。

## 每项完整参数

下列`middle_tick`和`end_tick`由显式变量替换；参数未列字段采用版本化内核默认值。光色为线性工作域RGB倍率，不是可直接等同的sRGB十六进制颜色。源像素和信号说明见[光学算子](OPTICAL_EFFECTS.md)／[高光扩散](HIGHLIGHT_GLOW.md)。

''' + '\n'.join(details)
    doc+='\n\n公开MP4视频轨各48帧／12fps；GIF各32帧，制作目标8fps，实际GIF时间基和容器时长逐文件记录在媒体清单。MP4／GIF是分发预览，工程重放比较使用项目渲染的完整MKV解码音画，不将有损MP4视作原始PCM。\n'
    note = ROOT / 'docs/product/OPTICAL_EFFECT_PACK.md'
    assert not note.exists()
    note.write_text(doc, encoding='utf-8', newline='\n')
    case_index=ROOT/'docs/product/CASES.md'
    history=case_index.read_text(encoding='utf-8')
    assert 'c77-editable-optical-pack' not in history
    history+='''\n\n<a id="c77-editable-optical-pack"></a>
## C77：8套可编辑复合光效内容包

[逐项完整参数、真实MP4／GIF与工程包](OPTICAL_EFFECT_PACK.md) · [选型页](../assets/optical-pack-20261029-r1/index.html) · [模板ZIP](../content/effect-packs/optical-v1.zip)。

8套MIT模板复用已有光学内核，各48帧／4秒／480×270实际RTX3060 OpenCL渲染；每套完整24883200字节RGBA及768000字节PCM工程包重放相同。当前真实C盘统一Skill59导入OP01后改选OP08，完整音画与安装63的OP08相同；没有把一套正式改选写成八套正式入口验收。

![原始图与8套实际中间帧](../assets/optical-pack-20261029-r1/contact.png)

样片为原创几何产品图与诊断双音，输入PNG／WAV为CC0。不是自然素材审美、真实品牌成片、人类听审、新神经模型或完整效果库验收。模板替换目标整条effects数组，需审阅原效果、原作者时钟与源像素尺度；完整406-r2及Skill63交付另验。
'''
    case_index.write_text(history,encoding='utf-8',newline='\n')
    texts = {
        'README.md': ('**新增8套可编辑复合光效内容包。** 每套含完整参数、实际MP4／GIF、原始图和可编辑工程；8套安装版GPU渲染及完整音画包重放通过，正式Skill59实际改选OP08通过。', '8套各48帧／4秒，RTX3060 OpenCL；全部RGBA／PCM工程包重放一致，正式C盘CLI59改选OP08与候选63完整音画一致。原创诊断图／双音，非自然素材审美或人类听审；没有8个新内核。'),
        'README.zh-TW.md': ('**新增8套可編輯複合光效內容包。** 每套有完整參數、實際MP4／GIF、原圖與可編輯專案；8套安裝版GPU渲染及完整音畫專案重播通過，正式Skill59實際改選OP08通過。', '8套各48幀／4秒，RTX3060 OpenCL；全部RGBA／PCM專案重播相同，真實C盤CLI59改選OP08與候選63完整音畫相同。原創診斷圖／雙音，非自然素材審美或人類聽審；沒有8個新內核。'),
        'README.en.md': ('**Eight editable composite optical templates are available.** Each includes full parameters, actual MP4/GIF, original input and an editable project. All eight passed installed GPU/full-AV replay; registered Skill59 actually reselected OP08.', 'Eight4s/48-frame templates used RTX3060 OpenCL and passed full RGBA/PCM package replay. Actual C-discovered CLI59 OP08 reselection matches candidate63 completely. Original diagnostic study/tones; no natural-footage or listening acceptance, no eight new kernels.')}
    row_counts = set()
    for name, (top, description) in texts.items():
        p = ROOT / name
        old = p.read_text(encoding='utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', old, re.M)
        n = len(old_rows)
        assert n >= 523
        title = old.splitlines()[0]
        banner = top + ' [Preview / 完整选型](docs/product/OPTICAL_EFFECT_PACK.md)\n\n![Actual editable optical templates](docs/assets/optical-pack-20261029-r1/contact.png)'
        new = old.replace(title, title + '\n\n' + banner, 1)
        row = f'| R{n + 1} | Optical template pack v1 | ' + description + ' [Evidence](docs/product/OPTICAL_EFFECT_PACK.md) |'
        new = new.replace(old_rows[-1], old_rows[-1] + '\n' + row, 1)
        assert re.findall(r'^\| R\d+ \|.*$', new, re.M)[:n] == old_rows
        p.write_text(new, encoding='utf-8', newline='\n')
        row_counts.add(n + 1)
    assert len(row_counts) == 1
    goal = ROOT / 'docs/product/GOAL_GAPS_20261025.md'
    old = goal.read_text(encoding='utf-8')
    original_rows = re.findall(r'^\| G\d\d \|.*$', old, re.M)
    title = old.splitlines()[0]
    new = old.replace(title, title + '\n\n2026-10-29 G06/G29：[首批8套可编辑复合光效](OPTICAL_EFFECT_PACK.md)实装为MIT内容模板，8套安装版GPU／完整RGBA_PCM工程重放及正式Skill59单项改选通过。属于内容库，非8新算子或自然素材审美验收；原38项关闭条件不变。', 1)
    assert len(original_rows) == 38 and re.findall(r'^\| G\d\d \|.*$', new, re.M) == original_rows
    goal.write_text(new, encoding='utf-8', newline='\n')
    assert all(sha(p) == h for p, h in guard.items())
    result = dict(status='published-and-documented', templates=8, archive_sha256=sha(archive),
                  candidate_cli='0.1.63', actual_registered_cli='0.1.59',
                  registered_candidate_complete_RGBA_PCM_equal=True, README_rows=row_counts.pop(),
                  formal_files_unchanged=95, original_goal_rows_preserved=38, full_goal_closed=False)
    save(out / 'verification.json', result)
    print(json.dumps(result), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
