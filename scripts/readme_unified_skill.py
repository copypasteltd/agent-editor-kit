"""Keep current three-language manuals consistent with single-entry registration.

Called after the full README generator as well as directly. Historical release
receipts and their 17-Skill counts remain dated evidence, not current registration.
"""
from pathlib import Path
import json
import re

from build_look_profile_docs import traditional

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = 'docs/validation/evidence/unified-skill-20261024-r1/verification.json'
ZIP = 'https://github.com/copypasteltd/agent-editor-kit/raw/refs/heads/main/docs/skills/agent-editor-kit-unified-skill-r1.zip'
MARKER = '<!-- unified-skill-registration -->'


def update():
    path = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    manifest = json.loads(path.read_bytes())
    if manifest.get('registration_mode') != 'single':
        return
    verification = ROOT / EVIDENCE
    checked = json.loads(verification.read_bytes()) if verification.exists() else None
    for locale, name, suffix in [('zh', 'README.md', ''), ('tw', 'README.zh-TW.md', '.zh-TW'), ('en', 'README.en.md', '.en')]:
        pick = lambda zh, en: en if locale == 'en' else traditional(zh) if locale == 'tw' else zh
        root = ROOT / name
        text = root.read_text('utf-8')
        from readme_release_workflow import quickstart
        heading = re.search(r'^## (?:下载并跑通第一条视频|下載並跑通第一條影片|Download and render your first video).*$', text, re.M)
        if heading:
            end = text.index('\n## ', heading.end())
            quick = quickstart(lambda zh, en: en if locale == 'en' else zh, suffix)
            if locale == 'tw':
                quick = traditional(quick)
            text = text[:heading.start()] + quick + text[end + 1:]
        text = text.replace('E:/tools/agent-editor-kit-alpha3', 'E:/tools/agent-editor-kit-unified')
        text = text.replace('17 个本地 Skill。**', '1 个统一 Skill / 17 项内部模块。**')
        text = text.replace('17 個本地 Skill。**', '1 個統一 Skill / 17 項內部模組。**')
        text = text.replace('17 local Skills.**', '1 unified Skill / 17 internal modules.**')
        block = MARKER + '\n\n'
        block += pick('**当前注册入口已合并：只需 `$agent-ffmpeg-local-editor`。** 时间线、滤镜、模型、质检、创意和分析等 17 项能力按需读取内部说明。',
                      '**Registration is consolidated: use only `$agent-ffmpeg-local-editor`.** Its 17 internal modules cover editing, looks, models, quality, creative planning and supplied data, loading details as needed.') + '\n\n'
        block += pick('本机已迁移为 1 个入口；[统一 Skill kit](', 'This host uses one entry; [unified Skill kit](') + ZIP + ') · [' + pick('安装/迁移/调用说明', 'Install, migrate and invoke') + '](docs/skills/UNIFIED_SKILL' + suffix + '.md)。'
        if locale == 'en':
            block = block[:-1] + '.'
        block += ' ' + pick('原 alpha.3 Release 附件保留原 17 个入口，新 kit 继续使用相同的已验证内核。',
                            'Original alpha.3 attachments retain the split 17-entry layout; the new kit uses the same verified runtime.') + '\n\n<!-- /unified-skill-registration -->\n\n'
        if MARKER in text:
            text = re.sub(re.escape(MARKER) + r'[\s\S]*?<!-- /unified-skill-registration -->\n*', lambda _: block, text, count=1)
        else:
            first_heading = text.index('\n## ')
            text = text[:first_heading] + '\n\n' + block + text[first_heading + 1:]
        text = text.replace('## 17 个本地 Skill：职责、输入输出与使用边界', '## 一个 Skill、17 项内部模块：职责、输入输出与使用边界')
        text = text.replace('## 17 個本地 Skill：職責、輸入輸出與使用邊界', '## 一個 Skill、17 項內部模組：職責、輸入輸出與使用邊界')
        text = text.replace('## 17 local Skills: responsibility, inputs/outputs and limits', '## One Skill, 17 internal modules: responsibility, inputs/outputs and limits')
        text = text.replace('| 编号 | Skill | 职责 |', '| 编号 | 内部模块 | 职责 |')
        text = text.replace('| 編號 | Skill | 職責 |', '| 編號 | 內部模組 | 職責 |')
        text = text.replace('| ID | Skill | Responsibility |', '| ID | Internal module | Responsibility |')
        text = text.replace('17 个 Skill 的正文/脚本在仓库 `skills/`，Codex 的 `C:/Users/carzy/.codex/skills/` 对应项为联接。',
                            '唯一入口正文/脚本及 17 项模块位于 `skills/agent-ffmpeg-local-editor/`，Codex 仅注册该目录的联接。')
        text = text.replace('17 個 Skill 的正文/腳本在倉庫 `skills/`，Codex 的 `C:/Users/carzy/.codex/skills/` 對應項為聯接。',
                            '唯一入口正文/腳本及 17 項模組位於 `skills/agent-ffmpeg-local-editor/`，Codex 僅註冊該目錄的聯接。')
        text = text.replace('The 17 Skills’ bodies/scripts live in `skills/`, with Codex discovery junctions under `C:/Users/carzy/.codex/skills/`.',
                            'The one entry, scripts and 17 task modules live in `skills/agent-ffmpeg-local-editor/`; Codex registers only that directory junction.')
        for module in manifest['modules']:
            if module['key'] == 'editor':
                continue
            old = module['previous_skill']
            destination = 'skills/agent-ffmpeg-local-editor/' + module['reference']
            text = text.replace(f'[`\u0024{old}`](skills/{old}/SKILL.md)', f'[`{module["key"]}`]({destination})')
            # Invocation examples use the single entry; historical counts/receipts remain intact.
            text = text.replace('$' + old + ' ', '$agent-ffmpeg-local-editor ')
        before = pick('常用组合：', 'Typical composition:')
        routing = pick('以下 K01–K17 均为统一入口内部模块，不需要另行注册。你只需描述目标，入口会读取相关模块，再按需组合创意、分析、时间线、模板、质检和交付。',
                       'K01–K17 are internal modules, not separate registrations. Describe the outcome; the entry selects the relevant planning, analysis, timeline, template, quality and delivery references.')
        if before in text:
            text = re.sub(r'(?m)^' + re.escape(before) + r'.*$', lambda _: routing, text, count=1)
        elif routing not in text:
            heading = re.search(r'(?m)^## (?:一个 Skill|一個 Skill|One Skill).*$', text)
            if heading:
                text = text[:heading.end()] + '\n\n' + routing + text[heading.end():]
        if checked and checked['status'] == 'passed':
            result = pick('**1 个入口 / 17 项模块；原生新目录安装、17→1 迁移、重复注册和 4 项预期拒绝通过；实际示例 20 次 CLI、180 帧完整解码。**',
                          '**One entry / 17 modules; native fresh-directory installation, 17→1 migration, repeat registration and four expected refusals pass; the demo runs 20 CLI calls and fully decodes 180 frames.**')
            bounds = pick('2026-10-24；0 新模型推理；非独立 Agent 行为评测，未做人工听审；历史 17 Skill 收据保留。',
                          '2026-10-24; zero new model inference, no independent Agent behavior benchmark or listening review; historical 17-Skill receipts are retained.')
            row = '| R32 | ' + pick('统一 Skill 与真实注册迁移', 'Unified Skill and actual registration migration') + ' | ' + result + ' | [Verification](' + EVIDENCE + ') · [Guide](docs/skills/UNIFIED_SKILL' + suffix + '.md) · ' + bounds + ' |'
            if re.search(r'^\| R32 \|', text, re.M):
                text = re.sub(r'^\| R32 \|.*$', lambda _: row, text, flags=re.M)
            else:
                text = re.sub(r'(^\| R31 \|.*$)', lambda m: m.group(1) + '\n' + row, text, count=1, flags=re.M)
            case_marker = '<!-- unified-skill-demo -->'
            if case_marker not in text:
                case = case_marker + '\n\n'
                case += pick('### C09：统一 Skill 的新目录实际交付', '### C09: actual delivery through the unified Skill kit') + '\n\n'
                case += pick('本轮从统一 kit 在 E 盘中文/空格路径离线安装，只注册一个入口，实际执行 20 次 CLI，完成 6 秒/360×640/30 fps/180 帧含音轨视频、质检及工程包往返。4 项预期拒绝、17→1 迁移和重复注册另有原始回执；0 新模型推理。下面 GIF 为本轮实际 MP4 的缩小无声预览，48 帧/6.01 秒，非剪辑 GUI 录像；检查过静态帧，未做连续播放和人工听审。',
                             'This update installs the unified kit offline in a fresh E-drive path with Chinese characters/spaces, registers one entry, then runs 20 real CLI calls for a six-second 360×640/30 fps/180-frame video with audio, quality checks and package recovery. Separate receipts cover four expected refusals, 17→1 migration and repeat registration; there is no new model inference. The GIF is a reduced silent preview of the new MP4 (48 frames/6.01 seconds), not an editing-GUI recording. A still was reviewed; continuous playback and listening were not reviewed.') + '\n\n'
                case += '[MP4](docs/assets/unified-skill-20261024-r1/demo.mp4) · [GIF](docs/assets/unified-skill-20261024-r1/demo.gif) · [Inputs](docs/assets/release-v0.1.0-alpha.1-r2/input/) · [Commands](docs/validation/evidence/unified-skill-20261024-r1/native-r2/demo-commands.json) · [Verification](' + EVIDENCE + ') · [Media hashes](docs/assets/unified-skill-20261024-r1/manifest.json)\n\n'
                case += '![Actual unified Skill kit demo](docs/assets/unified-skill-20261024-r1/demo.gif)\n\n<!-- /unified-skill-demo -->\n\n'
                anchor = re.search(r'^### C08[：:].*$', text, re.M)
                if anchor:
                    text = text[:anchor.start()] + case + text[anchor.start():]
        root.write_text(text.rstrip() + '\n', encoding='utf-8', newline='\n')

        manual = ROOT / ('docs/product/SKILLS' + suffix + '.md')
        text = manual.read_text('utf-8')
        text = re.sub(r'^# [^\n]+', '# ' + pick('一个本地 Skill、17 项内部模块详情', 'One local Skill: 17 internal task modules'), text, count=1)
        text = text.replace('| 编号 | Skill | 职责 |', '| 编号 | 内部模块 | 职责 |')
        text = text.replace('| 編號 | Skill | 職責 |', '| 編號 | 內部模組 | 職責 |')
        text = text.replace('| ID | Skill | Responsibility |', '| ID | Internal module | Responsibility |')
        for module in manifest['modules']:
            if module['key'] == 'editor':
                continue
            old = module['previous_skill']
            destination = '../../skills/agent-ffmpeg-local-editor/' + module['reference']
            text = text.replace(f'[`\u0024{old}`](../../skills/{old}/SKILL.md)', f'[`{module["key"]}`]({destination})')
            text = text.replace(f'`\u0024{old}`', '`' + module['key'] + '`')
            text = text.replace(f'../../skills/{old}/SKILL.md', destination)
        note = pick('只注册 `$agent-ffmpeg-local-editor`。K01–K17 是按需读取的内部模块，原独立名称只用于追溯，调用时无需再指定。',
                    'Register only `$agent-ffmpeg-local-editor`. K01–K17 load as internal references; previous specialist names are provenance, not additional invocation names.')
        if MARKER not in text:
            first = text.index('\n\n')
            text = text[:first] + '\n\n' + MARKER + '\n\n' + note + ' [Guide](../skills/UNIFIED_SKILL' + suffix + '.md)\n\n<!-- /unified-skill-registration -->' + text[first:]
        text = text.replace('本机 17 个目录均为 E 盘源文件到 Codex 发现路径的联接。', '本机只注册一个指向统一 Skill 的目录联接；17 项模块在目录内按需读取。')
        text = text.replace('本機 17 個目錄均為 E 盤源文件到 Codex 發現路徑的聯接。', '本機只註冊一個指向統一 Skill 的目錄聯接；17 項模組在目錄內按需讀取。')
        text = text.replace('All 17 local registrations are junctions to E-drive canonical files.', 'A single discovery junction points to the unified E-drive Skill; its 17 modules are internal references.')
        manual.write_text(text.rstrip() + '\n', encoding='utf-8', newline='\n')
    catalog_path = ROOT / 'docs/product/module-catalog.json'
    catalog = json.loads(catalog_path.read_bytes())
    catalog['skill_registration'] = {'mode': 'single', 'entry': 'agent-ffmpeg-local-editor',
                                    'registered_skill_count': 1, 'internal_module_count': 17,
                                    'manifest': 'agent-ffmpeg-local-install-manifest.json'}
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    update()
