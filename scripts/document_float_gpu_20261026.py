"""Record installed GPU delivery without replacing historical acceptance rows."""
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/float-gpu-20261026-r1'
BASELINE = '2fab08e5403ecb41ef09f7bc4fdd7609a5addbfc'
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def load(p): return json.loads(Path(p).read_bytes())
def write(p, s): Path(p).write_text(s, encoding='utf8', newline='\n')
def rows(s, prefix): return {m[1]: m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$', s, re.M)}
def before(name): return subprocess.check_output([GIT, 'show', BASELINE+':'+name], cwd=ROOT).decode('utf-8-sig')


def main():
    install = load(BASE/'installation-final-r4/verification.json')
    case, four, bench = [load(BASE/(s+'/verification.json')) for s in ('case-r1', '4k-r1', 'benchmark-r1')]
    tests = {g: load(BASE/(g+'-installed-final-r1/verification.json')) for g in ('gpu', 'text', 'float', 'audio', 'render', 'legacy', 'text-legacy')}
    assert all(v['status'] == 'passed' and v['skipped'] == 0 for v in tests.values())
    assert case['status'] == four['status'] == bench['status'] == 'passed'
    assert install['source_file_count'] == 217 and install['source_and_installed_equal']
    cpu, gpu, speed = bench['CPU_seconds'], bench['GPU_seconds'], bench['observed_speedup']
    code_error = bench['maximum_decoded_8bit_code_error']
    kit_path = ROOT/'docs/skills/community-unified-skill-package-0.1.24-r25.json'
    kit = load(kit_path) if kit_path.exists() else None
    intro = [
        f'原生 Windows 浮点 GPU 执行层已接入正式渲染、预览、队列和恢复：仿射投影、普通叠加、文字颜色与逐词选择。已安装 CLI 完成6秒/72帧混剪；注册的统一 Skill 完成4K/8帧动画与混剪包重新导入预览。相同4K工程单次成对实测 CPU {cpu:.3f}秒 → GPU {gpu:.3f}秒（{speed:.3f}×）；全部帧时钟/完整PCM相同，解码码差≤1。',
        f'原生 Windows 浮點 GPU 執行層已接入正式算繪、預覽、佇列及恢復：仿射投影、一般疊加、文字顏色與逐詞選擇。已安裝 CLI 完成6秒／72影格混剪；註冊的統一 Skill 完成4K／8影格動畫及混剪包重新匯入預覽。同一4K專案單次成對實測 CPU {cpu:.3f}秒 → GPU {gpu:.3f}秒（{speed:.3f}×）；全部影格時鐘／完整PCM相同，解碼碼差≤1。',
        f'Native Windows Float32 GPU execution now drives render, preview, queue and resume: affine sampling, normal source-over, text colors and word selection. The installed CLI delivers a 6s/72-frame edit; the registered Skill renders 4K/8-frame animation and reimports the edit for preview. One paired render of the same 4K project: CPU {cpu:.3f}s → GPU {gpu:.3f}s ({speed:.3f}×); all frame clocks/full decoded PCM match, decoded code error≤1.'
    ]
    limits = [
        '本机RTX3060；单对实测、非独占主机，不是中位数或通用速度承诺。字形栅格、转场/效果/crop/其他混合等仍在CPU；覆盖率8bit/颜色Float32。准入配额不等于峰值RSS或可用显存预留，完整目标继续开放。',
        '本機RTX3060；單對實測、非獨占主機，非中位數或一般速度承諾。字形柵格、轉場／效果／crop／其他混合等仍在CPU；覆蓋率8bit／顏色Float32。准入配額非峰值RSS或可用顯存預留，完整目標持續開放。',
        'RTX3060, one nonexclusive-host pair, not a median or general speed guarantee. Glyph rasterization, transitions/effects/crop/other blends remain CPU;8bit coverage/Float32 colors. Admission is not peak RSS or reserved free VRAM. Full target conditions remain open.'
    ]
    f57 = [
        '| F57 | 原生浮点GPU执行层 | 明确GPU策略 → 线性Float32仿射、普通叠加、文字组件/段落与逐词选择；正式渲染/预览/队列/恢复。 | `projection_acceleration; render; preview; queue` | off/prefer/require；实际binary64/次正规探测；任务独占进程和共享段；其余算子CPU，非全部GPU化。 |',
        '| F57 | 原生浮點GPU執行層 | 明確GPU策略 → 線性Float32仿射、一般疊加、文字元件／段落與逐詞選擇；正式算繪／預覽／佇列／恢復。 | `projection_acceleration; render; preview; queue` | off/prefer/require；實際binary64／次正規探測；任務專屬程序與共用段；其餘算子CPU，非全部GPU化。 |',
        '| F57 | Native Float32 GPU execution | Explicit policy → linear Float32 affine, normal over, text components/paragraphs and word selection; real render/preview/queue/resume. | `projection_acceleration; render; preview; queue` | off/prefer/require;actual binary64/subnormal probes;owned process/shared buffers;other operators CPU,not all-GPU editing. |'
    ]
    descriptions = [
        ['离线ZIP安装，217产品文件逐字节一致，CLI0.1.24/local.22-final-r4；统一Skill/17模块/71文件',
         f"{tests['gpu']['tests']}项实际GPU/控制/编码/取消恢复检查，0skip；65,536级灰阶、次正规alpha位值、120次控制替换、异常/预算与已有目录保护",
         '分别26文字/98浮点/64音频句柄嵌套/44预览渲染/191CLI队列Schema/72默认文字；各组0skip，不合并历史计数',
         f"实际安装CLI6秒/72帧：GPU字色/投影/逐词、转场/倒放/SRT与关联音轨；288000双声道采样误差{case['max_pcm_error']:.12g}；取消恢复/队列全帧与PCM相同",
         '实际统一Skill3840×2160/4fps/2秒/8帧、三字层/四组件/逐词打字机；GPU实际算子与清理、完整解码/质检/MP4/GIF/可编辑包',
         f'同4K工程完整成片单对 CPU {cpu:.3f}→GPU {gpu:.3f}秒（{speed:.3f}×）；4逻辑CPU亲和、空工程缓存、全部帧时钟/PCM相同，最大8bit码差≤1，非独占/非中位数',
         '可编辑包实际导入，三帧RGBA64解码相同；字体许可保留；r25独立kit注册/计划/验证',
         '三语57功能/20服务/17模块/75能力；170历史核验行和38原关闭条件保持；最终安装/Skill/文档字节核验'],
        ['離線ZIP安裝，217產品檔案逐位元組相同，CLI0.1.24/local.22-final-r4；統一Skill／17模組／71檔案',
         f"{tests['gpu']['tests']}項實際GPU／控制／編碼／取消恢復檢查，零略過；65,536級灰階、次正規alpha位元、120次控制替換、異常／預算及既有目錄保護",
         '分別26文字／98浮點／64音訊句柄巢狀／44預覽算繪／191CLI佇列Schema／72預設文字；各組零略過，未合併歷史計數',
         f"實際安裝CLI6秒／72影格：GPU字色／投影／逐詞、轉場／倒放／SRT與關聯音軌；288000雙聲道取樣誤差{case['max_pcm_error']:.12g}；取消恢復／佇列全影格及PCM相同",
         '實際統一Skill3840×2160／4fps／2秒／8影格、三字層／四元件／逐詞打字機；GPU實際算子及清理、完整解碼／質檢／MP4／GIF／可編輯包',
         f'同4K專案完整成片單對 CPU {cpu:.3f}→GPU {gpu:.3f}秒（{speed:.3f}×）；4邏輯CPU親和、空專案快取、全影格時鐘／PCM相同，最大8bit碼差≤1，非獨占／非中位數',
         '可編輯包實際匯入，三影格RGBA64解碼相同；字型授權保留；r25獨立kit註冊／計畫／驗證',
         '三語57功能／20服務／17模組／75能力；170歷史核驗列及38原關閉條件保持；最終安裝／Skill／文件位元組核驗'],
        ['Offline ZIP installed;217 source files byte-match CLI0.1.24/local.22-final-r4;one Skill/17modules/71files',
         f"{tests['gpu']['tests']} actual GPU/control/encode/cancel-resume tests,zero skips;65,536levels,subnormal alpha bits,120 control replacements,failure/budget/existing-directory protection",
         'Separate26 text/98 float/64 audio-handles-nesting/44 preview-render/191 CLI-queue-schema/72 default-text;zero skips,not combined with history',
         f"Installed CLI,6s/72frames:GPU text/affine/word selection,transitions/reverse/SRT/linked audio;288000stereo sample oracle error={case['max_pcm_error']:.12g};resume/queue frames and PCM equal",
         'Registered Skill3840x2160/4fps/2s/8frames,three text layers/four components/word-typewriter;actual GPU operations/cleanup,full decode/quality/MP4/GIF/editable package',
         f'One complete paired4K render CPU {cpu:.3f}->GPU {gpu:.3f}s ({speed:.3f}x);4logicalCPU affinity,fresh project caches,all clocks/fullPCM equal,max8bitcodeerror<=1;nonexclusive,not a median',
         'Actual editable package import,three RGBA64 previews equal,font license retained;r25 isolated kit registration/planning/validation',
         'Three languages57functions/20services/17modules/75declarations;170historical rows and38original closure conditions retained;final installed/Skill/docs byte audit']]
    targets = ['installation-final-r4/verification.json', 'gpu-installed-final-r1/verification.json',
               'render-installed-final-r1/verification.json', 'case-r1/verification.json', '4k-r1/verification.json',
               'benchmark-r1/verification.json', 'package-r1/verification.json', 'final-delivery-r3/verification.json']
    for i, name in enumerate(('README.md', 'README.zh-TW.md', 'README.en.md')):
        text = (ROOT/name).read_text('utf-8-sig')
        text = text.replace('<!-- float-text-coverage-current -->', '<!-- float-text-coverage-history -->').replace('<!-- /float-text-coverage-current -->', '<!-- /float-text-coverage-history -->')
        text = text.replace('**CLI0.1.23 / alpha.4-local.21 / r24 kit', '**Historical / 历史 / 歷史：CLI0.1.23 / alpha.4-local.21 / r24 kit')
        block = '<!-- float-gpu-current -->\n\n**CLI0.1.24 / alpha.4-local.22 / r25 kit · 1 Skill / 17 modules.**\n\n'+intro[i]+'\n\n'
        block += '[Workflow](docs/product/FLOAT_GPU.md) · [C33/C34](docs/product/CASES.md#c33-float-gpu) · [Local install](docs/releases/CLI_0.1.24_LOCAL.md) · [Evidence](docs/validation/浮点GPU执行层实测_2026-10-26.md)\n\n'
        actual_error = [f'完整解码最大8bit码差为 {code_error}（门槛≤1）。', f'完整解碼最大8bit碼差為 {code_error}（門檻≤1）。', f'Actual maximum decoded 8-bit code error: {code_error} (limit: 1).'][i]
        block += '![Actual installed GPU 4K animation / silent GIF](docs/assets/float-gpu-20261026-4k-r1/4k-native-text.gif)\n\n'+actual_error+' '+limits[i]+'\n\n<!-- /float-gpu-current -->\n\n'
        if '<!-- float-gpu-current -->' in text:
            text = re.sub(r'<!-- float-gpu-current -->.*?<!-- /float-gpu-current -->\n\n', lambda _: block, text, count=1, flags=re.S)
        else: text = text.replace('<!-- float-text-coverage-history -->', block+'<!-- float-text-coverage-history -->', 1)
        if not rows(text, 'F').get('F57'):
            match = re.search(r'^\| F56\s*\|.*$', text, re.M); assert match
            text = text[:match.end()]+'\n'+f57[i]+text[match.end():]
        for number, (detail, target) in enumerate(zip(descriptions[i], targets), 171):
            if number == 177:
                detail += ' · [r25 kit](docs/validation/evidence/float-gpu-20261026-r1/kit-r1/verification.json)'
            row = f'| R{number} | 2026-10-26 Float32 GPU | {detail} | [Evidence](docs/validation/evidence/float-gpu-20261026-r1/{target}) |'
            if f'R{number}' in rows(text, 'R'): text = re.sub(r'^\| R'+str(number)+r'\s*\|.*$', lambda _: row, text, flags=re.M)
            else:
                last = re.search(r'^\| R'+str(number-1)+r'\s*\|.*$', text, re.M); assert last
                text = text[:last.end()]+'\n'+row+text[last.end():]
        lines = []
        for line in text.splitlines():
            if not line.startswith('| R'):
                if 'local.21/final-r2/installed' in line:
                    line = line.replace('local.21/final-r2/installed', 'local.22/final-r4/installed').replace('0.1.23', '0.1.24')
                if 'unified-skill-r24.zip' in line and line.startswith('**'):
                    line = line.replace('unified-skill-r24.zip', 'unified-skill-r25.zip').replace('r24 Skill kit', 'r25 Skill kit')
                if line.startswith('| F56 '):
                    replacement = ('；CPU/显式GPU；', '；CPU／明確GPU；', ';CPU/explicit GPU;')[i]
                    line = line.replace('；CPU；', replacement).replace(';CPU;', replacement)
                    line = line.replace('富ASS/Bidi/GPU文字/自然质量未闭', '富ASS/Bidi/自然质量未闭').replace('富ASS／Bidi／GPU文字／自然品質未閉', '富ASS／Bidi／自然品質未閉').replace('rich ASS/Bidi/GPU text/natural quality open', 'rich ASS/Bidi/natural quality open')
                if line.startswith('| S16 '):
                    line = [
                        '| S16 | GPU兼容服务 | 已有原生OpenCL ICD / NVIDIA模型库 | 默认图投影及独立Float32仿射/普通叠加/字色/逐词；off/prefer/require，模型auto/cpu/cuda；实际探测/预算/清理 | `render --projection-acceleration; gpu inspect; --device` | RTX3060实测；字形/效果/转场等CPU，非全部算子GPU化，系统库许可另列。 |',
                        '| S16 | GPU相容服務 | 既有原生OpenCL ICD / NVIDIA模型庫 | 預設圖投影及獨立Float32仿射／一般疊加／字色／逐詞；off/prefer/require，模型auto/cpu/cuda；實際探測／預算／清理 | `render --projection-acceleration; gpu inspect; --device` | RTX3060實測；字形／效果／轉場等CPU，非全部算子GPU化，系統庫授權另列。 |',
                        '| S16 | GPU compatibility | Existing native OpenCL ICD / NVIDIA model libraries | Graph projection and independent Float32 affine/normal over/text colors/word selection;off/prefer/require,model auto/cpu/cuda;actual probes/budgets/cleanup | `render --projection-acceleration; gpu inspect; --device` | RTX3060 tested;glyphs/effects/transitions remain CPU,not all-GPU;system-library licenses separate. |'][i]
            lines.append(line)
        text = '\n'.join(lines)+'\n'
        historical = rows(before(name), 'R'); assert len(historical) == 170
        assert all(rows(text, 'R')[k] == v for k, v in historical.items())
        assert len(rows(text, 'F')) == 57 and len(rows(text, 'R')) == 178
        write(ROOT/name, text)
    old_install = load(ROOT/'docs/validation/evidence/float-text-coverage-20261026-r1/installation-final-r2/verification.json')
    guide = ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md'; text = guide.read_text('utf-8-sig')
    for old, new in [('local.21', 'local.22'), ('0.1.23', '0.1.24'), ('r24', 'r25'),
                     ('local.22/final-r2', 'local.22/final-r4'), ('local.22/candidate-r2', 'local.22/candidate-r4'),
                     (old_install['archive_sha256'], install['archive_sha256']),
                     (old_install['manifest_sha256'].removeprefix('sha256:'), install['manifest_sha256'].removeprefix('sha256:')),
                     ('214产品Python文件', '217产品Python文件')]: text = text.replace(old, new)
    text = text.replace('float-text-coverage-capabilities-cli-0.1.24.json', 'float-gpu-capabilities-cli-0.1.24.json')
    text = text.replace('GPU文字仍开放', '当前可显式选择GPU字色合成，字形栅格仍在CPU')
    note = '\n当前[原生浮点GPU执行层](FLOAT_GPU.md)支持仿射、普通叠加、字色和逐词选择；实际设备/探测/取消清理均保留。其余算子与完整目标边界见契约。\n'
    if note not in text: text += note
    write(guide, text)
    for prefix in ('docs/product/SKILLS', 'docs/skills/UNIFIED_SKILL'):
        for suffix in ('', '.zh-TW', '.en'):
            path = ROOT/(prefix+suffix+'.md'); text = path.read_text('utf-8-sig')
            text = text.replace('0.1.23 / alpha.4-local.21 / r24 kit', '0.1.24 / alpha.4-local.22 / r25 kit').replace('float-text-coverage-capabilities-cli-0.1.23.json', 'float-gpu-capabilities-cli-0.1.24.json')
            text = re.sub(r'(?<!Historical )CLI0\.1\.23:\[4K', 'Historical CLI0.1.23:[4K', text)
            link = '../product/FLOAT_GPU.md' if prefix.startswith('docs/skills') else 'FLOAT_GPU.md'
            note = '\nCLI0.1.24:[native Float32 GPU workflow]('+link+'). Explicit geometry/normal composition/text colors/word selection;owned worker cleanup;CPU glyph rasterization and remaining operators retained. Full original target conditions remain open.\n'
            if note not in text: text += note
            write(path, text)
    for name in ('GOAL_GAPS_20261025.md', 'IMPLEMENTATION_PLAN_20261025.md'):
        path = ROOT/'docs/product'/name; text = path.read_text('utf-8-sig').replace('当前本地 **CLI0.1.23', '此前本地 **CLI0.1.23')
        note = '\n当前本地 **CLI0.1.24 / alpha.4-local.22 / r25 kit**：[浮点GPU执行层](FLOAT_GPU.md)实装，实际4K成片、同源CPU/GPU单对性能、完整混剪与取消恢复留证。全部38原关闭条件保持。\n'
        if note not in text: at = text.index('\n\n')+2; text = text[:at]+note+'\n'+text[at:]
        if name.startswith('GOAL'):
            text = text.replace('local.21-final-r2 / CLI0.1.23，1Skill/17模块、71文件、r24 kit；[214文件固定安装](../validation/evidence/float-text-coverage-20261026-r1/installation-final-r2/verification.json)',
                'local.22-final-r4 / CLI0.1.24，1Skill/17模块、71文件、r25 kit；[217文件固定安装](../validation/evidence/float-gpu-20261026-r1/installation-final-r4/verification.json)')
            text = text.replace('[当前全部字段](float-text-coverage-capabilities-cli-0.1.23.json)', '[当前全部字段](float-gpu-capabilities-cli-0.1.24.json)')
            def release(m):
                cells = m[0].split('|'); cells[3] = ' 公开alpha.3/CLI0.1.2保持；本地local.22-final-r4/CLI0.1.24/r25已安装注册核验，浮点GPU成片/完整音轨/取消恢复和同源性能留证 '
                return '|'.join(cells)
            text = re.sub(r'^\| G38\s*\|.*$', release, text, flags=re.M)
            def performance(m):
                cells = m[0].split('|')
                marker = '；CLI0.1.24增加GPU文字4K/8帧成片与同工程完整CPU/GPU单对实测'
                if marker not in cells[3]: cells[3] = cells[3].rstrip()+marker+' '
                cells[4] = cells[4].replace('GPU4K验证为单帧像素/小目标缩小', '旧图投影GPU4K证据为单帧；当前浮点GPU另有8帧完整交付，仍非自然长片或实时验收')
                return '|'.join(cells)
            text = re.sub(r'^\| G32\s*\|.*$', performance, text, flags=re.M)
            old, new = rows(before('docs/product/'+name), 'G'), rows(text, 'G')
            assert len(new) == 38 and all(new[k].split('|')[5] == v.split('|')[5] for k, v in old.items())
        else:
            text = re.sub(r'^\| W07 色彩与GPU性能\s*\|.*$',
                '| W07 色彩与GPU性能 | G08、G32 | 完整颜色管理、目标算子、GPU/CPU选择、资源预算、模型复用与4K/长片 | 既有图投影和独立Float32仿射/普通叠加/文字颜色/逐词选择已交付，实际4K/8帧与同工程单对性能留证；字形栅格/转场/效果/其他混合仍CPU，全进程预算、自然质量、长片继续开放 |',
                text, flags=re.M)
        write(path, text)
    cases = ROOT/'docs/product/CASES.md'; text = cases.read_text('utf-8-sig')
    for cid, title, folder, movie, archive, description in [
        ('c33-float-gpu', 'C33 Float32 GPU mixed edit / 浮点GPU混剪', 'float-gpu-20261026-r1', 'native-text', 'editable-native-text',
         '6秒/72帧/12fps；实际GPU字色/投影/逐词，转场、父倒放、SRT、真实句柄和完整关联音轨；取消恢复/队列逐帧与PCM一致。'),
        ('c34-4k-gpu', 'C34 Actual 4K GPU titles / 实际4K GPU字层', 'float-gpu-20261026-4k-r1', '4k-native-text', 'editable-4k-text',
         f'3840×2160/4fps/2秒/8帧、三层文字。独立同工程成对成片 CPU {cpu:.3f}秒→GPU {gpu:.3f}秒（{speed:.3f}×）；单对非独占主机，不代表中位数、实时或通用保证。')]:
        if f'id="{cid}"' not in text:
            text += f'\n<a id="{cid}"></a>\n\n## {title}\n\n{description}\n\n[Workflow](FLOAT_GPU.md) · [Original](../assets/{folder}/original.png) · [MP4](../assets/{folder}/{movie}.mp4) · [Editable package](../assets/{folder}/{archive}.aevpkg.zip)\n\n![Actual installed GPU render / silent GIF](../assets/{folder}/{movie}.gif)\n\n原生Windows/RTX3060，CC0自制内容、Noto字型OFL保留；覆盖率8bit、颜色Float32、binary64内核。其余算子CPU，静帧观察与完整解码分列；未进行连续播放、人工听审或自然质量验收。\n'
    write(cases, text)
    table = '\n'.join(f"| {g} | {r['tests']} passed / 0 skip | [receipt](evidence/float-gpu-20261026-r1/{g}-installed-final-r1/verification.json) |" for g, r in tests.items())
    write(ROOT/'docs/validation/浮点GPU执行层实测_2026-10-26.md', f'''# 原生浮点GPU执行层实测（2026-10-26）

CLI0.1.24/local.22-final-r4，217产品Python文件与ZIP安装版逐字节一致。ZIP {install['archive_bytes']}bytes，SHA-256 `{install['archive_sha256']}`；[安装记录](evidence/float-gpu-20261026-r1/installation-final-r4/verification.json)。单一Skill/17模块/71文件；没有模型推理、虚拟化或常驻服务。

| 独立组 | 结果 | 证据 |
|---|---|---|
{table}

各组与历史测试不合并计数。GPU组实际执行原生OpenCL，检查65,536级原值、亚像素/透明边缘/扩展RGB、次正规alpha位值、四组件有序颜色、整段选择、120次控制替换及扩容、取消/超时/worker死亡、预算、已有目录保护、真实编码和取消恢复。探测操作与编辑帧算子分列，GPU范围见[契约](../product/FLOAT_GPU.md)。RTX3060/驱动595.95为实测设备，其他机器未验收。

[C33已安装CLI](evidence/float-gpu-20261026-r1/case-r1/verification.json)：6秒/72帧工程，实际GPU文字/投影/逐词，与CPU转场/真实句柄/关联音轨共同执行。全部288000双声道采样独立公式误差 `{case['max_pcm_error']:.12g}`；取消恢复与队列的全部帧/时钟/PCM相同。注册的统一Skill另完成[包导入](evidence/float-gpu-20261026-r1/package-r1/verification.json)，核验三帧RGBA64相同及字体许可。

[C34实际4K](evidence/float-gpu-20261026-r1/4k-r1/verification.json)：3840×2160/4fps/2秒/8帧，三层文字、四组件、淡入及逐词打字机；实际算子数、完整解码/质检/可编辑包/MP4/GIF留存。预览及成片均从注册的单一Skill调用已安装CLI，未回落源码。

[同工程完整成片单对性能](evidence/float-gpu-20261026-r1/benchmark-r1/verification.json)：旧CLI0.1.23 CPU {cpu:.3f}秒，新CLI0.1.24 GPU {gpu:.3f}秒，观察值{speed:.3f}倍。两次都是完整4K/8帧，相同作者数据/字体/编码，只有明确GPU策略不同；4逻辑CPU亲和，每次全新工程及空缓存。全部8帧时钟和完整解码PCM相同，最大YUV420 8bit码差 `{bench['maximum_decoded_8bit_code_error']}`，不同码数量 `{bench['different_codes']}`。单对CPU先/GPU后，非独占主机，OS页缓存不受控，未测峰值RSS，不作为中位数、通用吞吐或实时保证。

[r25独立工具包实测](evidence/float-gpu-20261026-r1/kit-r1/verification.json)使用独立中文/空格目录展开、配置及注册；实际调用版本、能力、转换导入、浮点计划和验证共8次。102个ZIP条目、71个Skill文件/17模块；只做计划与验证，没有新增模型推理或成片，实际Codex注册目录未改动。

source-gpu-r2保留空NumPy标记文件准入及测试读取计划路径的失败；r3保留一次worker提前退出；随后稳定快照读取、错误响应留证及120次消息/扩容回归补齐。r4/r5源码结果和最终安装组分别记录，未用后续成功追改旧失败。候选安装r2/r3保留，正式启用final-r4新增次正规精度探测和已存在任务目录保护。

交付审计r1发现自引用的结果文件尚未创建，已修正为先写running、检查完成后写passed；r2的待交付清单曾包含本地生成工程，随后加入本轮workspace忽略规则并撤销这些文件的暂存。原工程与解码数据留在本地，仓库保留案例包、媒体和证据；最终以r3审计及逐字节暂存核对为准。

字形覆盖率8bit，GPU颜色/采样中间binary64并在明确位置回到Float32。其余算子仍CPU；预算是单池准入估算，非合并峰值RSS或空闲显存预留。没有连续播放、人工听音、自然质量/长片/HDR/实时或完整剪映等价验收。全部38原关闭条件保持。
''')
    kit_desc = f"{kit['files']}files/{kit['bytes']}bytes/SHA-256 `{kit['sha256']}`" if kit else 'r25独立kit摘要见版本化metadata'
    write(ROOT/'docs/releases/CLI_0.1.24_LOCAL.md', f'''# CLI0.1.24 本地交付 / Local delivery

agent editor kit / `v0.1.0-alpha.4-local.22` / final-r4；217产品Python文件、71 Skill文件、单入口17模块。[原生浮点GPU使用](../product/FLOAT_GPU.md)。

| 内容 | E:/dev/sandbox/AI广告剪辑/下路径 | SHA-256 |
|---|---|---|
| Application ZIP / {install['archive_bytes']}bytes | `local/agent-ffmpeg/v0.1.0-alpha.4-local.22/candidate-r4/bundle.zip` | `{install['archive_sha256']}` |
| Manifest | ZIP内`manifest.json` | `{install['manifest_sha256'].removeprefix('sha256:')}` |
| Installed | `local/agent-ffmpeg/v0.1.0-alpha.4-local.22/final-r4/installed/` | [217-file proof](../validation/evidence/float-gpu-20261026-r1/installation-final-r4/verification.json) |
| r25 unified Skill / {kit_desc} | [r25 ZIP](../skills/agent-editor-kit-community-unified-skill-r25.zip) | [metadata](../skills/community-unified-skill-package-0.1.24-r25.json) |

[离线安装/注册](../product/COMMUNITY_LOCAL_DELIVERY.md) · [75实际能力](../product/float-gpu-capabilities-cli-0.1.24.json) · [核验与性能](../validation/浮点GPU执行层实测_2026-10-26.md) · [17模块](../product/SKILLS.md)。四个原CPU/GPU模型包和配置保留，没有新模型推理。原生Windows，无Docker/WSL/虚拟环境或全局安装。

GPU明确选择off/prefer/require；语音/翻译独立auto/cpu/cuda。实际GPU支持范围为仿射、普通合成、字色和逐词选择，字形栅格/转场/其他算子CPU。单对4K实测CPU {cpu:.3f}→GPU {gpu:.3f}秒，不作实时或通用速度保证。当前包为本地交付；公开alpha.3/CLI0.1.2标签、附件及摘要保持。完整目标继续开放。
''')
    for name in ('FLOAT_TEXT.md', 'FLOAT_TEXT_COVERAGE.md', 'OPENCL_PROJECTION.md'):
        path = ROOT/'docs/product'/name; text = path.read_text('utf-8-sig')
        note = '\n当前CLI0.1.24另有[独立原生Float32 GPU执行层](FLOAT_GPU.md)：明确GPU策略、字色/普通叠加/仿射/逐词选择，保留CPU字形和其他算子；上文历史版本边界不追改。\n'
        if note not in text: write(path, text+note)
    path = ROOT/'docs/README.md'; text = path.read_text('utf-8-sig')
    text = text.replace('Current local / 当前本地 / 目前本地：**CLI0.1.23', 'Historical / 历史 / 歷史：**CLI0.1.23')
    note = '\nCurrent local / 当前本地 / 目前本地：**CLI0.1.24 / local.22 / r25 kit** · [Float32 GPU](product/FLOAT_GPU.md) · [Local bundle](releases/CLI_0.1.24_LOCAL.md) · [C33/C34](product/CASES.md#c33-float-gpu).\n'
    if note not in text: at = text.index('\n\n')+2; write(path, text[:at]+note+'\n'+text[at:])
    print(json.dumps(dict(status='documented', functions=57, services=20, history_preserved=170, rows=178, closures_preserved=38)))


if __name__ == '__main__': main()
