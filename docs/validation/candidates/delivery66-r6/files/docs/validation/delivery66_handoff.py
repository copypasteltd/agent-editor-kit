"""Finish a frozen delivery: independent kit replay, reversible activation, assets.

Uses the existing offline installer, single-Skill packager and product delivery
controller. A running/partial regression cannot authorize any of these actions.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import time
import zipfile
import delivery66 as round_runner

ROOT = Path(__file__).resolve().parents[2]
ROUND = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
BASE = ROOT / 'docs/validation/evidence/delivery66-handoff-20261106-r1'
LOCAL = ROOT / 'local/agent-ffmpeg/delivery66-handoff'
VERSION, RELEASE, TAG = '0.1.66', 'v0.1.0-alpha.4-local.64', 'v0.1.0-alpha.4'
SKILL = 'skills/agent-ffmpeg-local-editor/'
CONFIG, MANIFEST = 'local/agent-ffmpeg/runtime.json', 'agent-ffmpeg-local-install-manifest.json'
RESERVED = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}
RELEASE_LOCK_FORMAT = 'agent-editor-reviewed-release-v2'
SOURCE_BINDING_FORMAT = 'agent-editor-release-source-v2'
SOURCE_READMES = ('README.md', 'README.zh-TW.md', 'README.en.md')
SOURCE_TOOLS = frozenset((
    'docs/validation/delivery66.py', 'docs/validation/run_delivery66_native.py',
    'docs/validation/delivery66_handoff.py', 'docs/validation/delivery66_music_faults.py',
    'docs/validation/publish_delivery66.py', 'docs/validation/test_delivery66_handoff.py',
    'scripts/activate_community_runtime.py',
    'scripts/package_community_skill.py',
))


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def decode(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            require(key not in value, 'Duplicate JSON field')
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    require(isinstance(value, dict), 'Expected an evidence object')
    return value


def load(path, limit=8 * 1024**2):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, 'Evidence exceeds its read budget')
    return decode(raw)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.pending')
    with temporary.open('xb') as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def local(path, root=ROOT):
    path, root = Path(os.path.abspath(path)), Path(os.path.abspath(root))
    require(not str(path).startswith(('\\\\', '//')) and path.is_relative_to(root), 'Use an owned local path')
    for part in (path, *path.parents):
        require(not part.is_symlink() and not getattr(part, 'is_junction', lambda: False)(),
                'Owned paths must not cross reparse points')
    require(path.resolve().is_relative_to(root.resolve()), 'Owned path escaped its root')
    return path


def member(name):
    require(isinstance(name, str) and name and '\\' not in name, 'Archive name must be canonical')
    path = PurePosixPath(name)
    require(not path.is_absolute() and path.as_posix() == name and all(
        part not in {'.', '..'} and not part.endswith(('.', ' '))
        and part.split('.', 1)[0].casefold() not in RESERVED
        and all(ord(c) >= 32 and c not in ':<>"|?*' for c in part) for part in path.parts),
        'Invalid Windows archive member: ' + name)
    return path


def release_source_files(binding, frozen_source, formal_files, frozen_packaging):
    """Validate the complete public source scope, excluding machine-local config."""
    require(isinstance(binding, dict) and binding.get('format') == SOURCE_BINDING_FORMAT
            and binding.get('local_runtime_config_committed') is False,
            'Reviewed release source binding is missing or invalid')
    groups = binding.get('groups')
    require(isinstance(groups, dict)
            and set(groups) == {'product', 'delivery_tools', 'packaging', 'skill', 'registration', 'documentation'}
            and all(isinstance(rows, dict) and rows for rows in groups.values()),
            'Reviewed release source roles are incomplete')
    require(isinstance(frozen_source, dict) and frozen_source
            and groups['product'] == frozen_source, 'Reviewed product source differs from its freeze')
    require(set(groups['delivery_tools']) == SOURCE_TOOLS, 'Reviewed delivery tool scope is incomplete')
    require(isinstance(frozen_packaging, dict)
            and set(frozen_packaging) == set(round_runner.packaging_source_names())
            and groups['packaging'] == {name: pin for name, pin in frozen_packaging.items() if name not in SOURCE_TOOLS}
            and all(frozen_packaging[name] == groups['delivery_tools'][name]
                    for name in frozen_packaging.keys() & SOURCE_TOOLS),
            'Reviewed packaging source scope is incomplete or inconsistent')
    require(set(groups['documentation']) == set(SOURCE_READMES), 'Three reviewed README entries are required')
    require(isinstance(formal_files, list) and 4 <= len(formal_files) <= 512,
            'Reviewed formal source inventory is missing')
    public, seen = {}, set()
    for row in formal_files:
        require(isinstance(row, dict), 'Invalid formal source row')
        name, pin = row.get('path'), row.get('sha256')
        require(isinstance(name, str) and member(name).as_posix() == name
                and name.casefold() not in seen
                and isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin),
                'Invalid or duplicate formal source file')
        seen.add(name.casefold())
        require(name in {CONFIG, MANIFEST} or name.startswith(SKILL), 'Formal source is outside the single Skill')
        if name != CONFIG:
            public[name] = pin
    skill = {name: pin for name, pin in public.items() if name.startswith(SKILL)}
    require(skill and MANIFEST in public and groups['skill'] == skill
            and groups['registration'] == {MANIFEST: public[MANIFEST]},
            'Reviewed source omits or changes accepted Skill or registration files')
    result, seen = {}, set()
    for rows in groups.values():
        for name, pin in rows.items():
            require(isinstance(name, str) and member(name).as_posix() == name
                    and not name.casefold().startswith('local/')
                    and name.casefold() not in seen
                    and isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin),
                    'Reviewed source contains an invalid, private or overlapping file')
            seen.add(name.casefold())
            result[name] = pin
    return result


def capture_release_source(context):
    freeze, formal = context['freeze'], context['spec']['files']
    public = {row['path']: row['sha256'] for row in formal if row['path'] != CONFIG}
    binding = dict(format=SOURCE_BINDING_FORMAT, local_runtime_config_committed=False, groups=dict(
        product=dict(freeze['file_hashes']), delivery_tools=dict(freeze['delivery_tool_files']),
        packaging={name: pin for name, pin in freeze['packaging_source_files'].items() if name not in SOURCE_TOOLS},
        skill={name: pin for name, pin in public.items() if name.startswith(SKILL)},
        registration={name: pin for name, pin in public.items() if name == MANIFEST},
        documentation={name: sha(local(ROOT / name, root=ROOT)) for name in SOURCE_READMES}))
    for name, pin in release_source_files(binding, freeze['file_hashes'], formal, freeze['packaging_source_files']).items():
        require(sha(local(ROOT / name, root=ROOT)) == pin, 'Reviewed release source changed: ' + name)
    return binding


def archive_plan(zipped, *, maximum_file=32 * 1024**2, maximum_total=128 * 1024**2):
    entries = zipped.infolist()
    require(0 < len(entries) <= 2048, 'Archive entry budget exceeded')
    names = [entry.filename for entry in entries]
    folded = {name.casefold() for name in names}
    require(len(folded) == len(names), 'Duplicate or case-alias archive names')
    total = 0
    for entry in entries:
        path = member(entry.filename)
        require(not entry.is_dir() and stat.S_IFMT(entry.external_attr >> 16) != stat.S_IFLNK,
                'Archive directories and links are forbidden')
        require(not entry.flag_bits & 1 and 0 <= entry.file_size <= maximum_file, 'Invalid or oversized archive member')
        require(not any(parent.as_posix().casefold() in folded for parent in path.parents if str(parent) != '.'),
                'Archive file/directory prefix conflict')
        total += entry.file_size
    require(total <= maximum_total, 'Archive total byte budget exceeded')
    return entries


def extract(archive, destination, *, skill=False):
    destination = local(destination)
    require(not destination.exists(), 'Existing extraction target is preserved')
    with zipfile.ZipFile(local(archive)) as zipped:
        entries = archive_plan(zipped, maximum_file=(32 if skill else 512) * 1024**2,
                               maximum_total=(128 if skill else 2048) * 1024**2)
        inventory = None
        if skill:
            require('KIT-FILES.json' in zipped.namelist(), 'Skill kit inventory is required')
            require(zipped.getinfo('KIT-FILES.json').file_size <= 2 * 1024**2, 'Oversized kit inventory')
            inventory = decode(zipped.read('KIT-FILES.json'))
            rows = inventory['files']
            require(isinstance(rows, list) and len(rows) <= 512, 'Invalid kit inventory')
            expected = {row['path']: row for row in rows}
            require(len(expected) == len(rows) and set(expected) | {'KIT-FILES.json'} == set(zipped.namelist()),
                    'Kit inventory differs from archive contents')
            require(inventory['cli_version'] == VERSION and inventory['skill_count'] == 1
                    and inventory['module_count'] == 17, 'Wrong kit version or Skill layout')
            require([name for name in expected if PurePosixPath(name).name == 'SKILL.md'] == [SKILL + 'SKILL.md'],
                    'Exactly one public Skill entry is required')
            for name, row in expected.items():
                require(type(row['bytes']) is int and row['bytes'] == zipped.getinfo(name).file_size
                        and isinstance(row['sha256'], str) and re.fullmatch('[0-9a-f]{64}', row['sha256']),
                        'Invalid inventory size or digest')
        # Validate every input digest before creating the destination.
        for entry in entries:
            with zipped.open(entry) as source:
                digest = hashlib.file_digest(source, 'sha256').hexdigest()
            if inventory and entry.filename != 'KIT-FILES.json':
                require(digest == expected[entry.filename]['sha256'], 'Corrupt Skill kit content')
        destination.mkdir(parents=True)
        for entry in entries:
            target = local(destination / Path(*member(entry.filename).parts), destination)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(entry) as source, target.open('xb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
    return inventory


def report_path(kind, run):
    require(isinstance(run, str) and run.isalnum() and len(run) <= 32, 'Use bounded alphanumeric run IDs')
    return BASE / (kind + '-' + run) / 'verification.json'


def begin(kind, run):
    out = report_path(kind, run).parent
    require(not out.exists(), 'Existing evidence is immutable; choose a fresh run ID')
    out.mkdir(parents=True)
    for name in ('delivery66_handoff.py', 'delivery66_music_faults.py', 'publish_delivery66.py'):
        source = Path(__file__).with_name(name)
        require(source.is_file(), 'Complete all handoff code before executing a round')
        (out / name).write_bytes(source.read_bytes())
    return out


def execute(out, name, command, *, expected=0, cli=False, timeout=1200):
    env = dict(os.environ)
    temporary = LOCAL / 'temp'
    temporary.mkdir(parents=True, exist_ok=True)
    env.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
               PYTHONDONTWRITEBYTECODE='1', PIP_NO_INDEX='1', PIP_CONFIG_FILE=os.devnull)
    began = time.monotonic()
    with (out / (name + '.stdout')).open('xb') as stdout, (out / (name + '.stderr')).open('xb') as stderr:
        result = subprocess.run(list(map(str, command)), cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
            stdout=stdout, stderr=stderr, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    calls = load(out / 'calls.json')['calls'] if (out / 'calls.json').is_file() else []
    calls.append(dict(name=name, argv=list(map(str, command)), exit_code=result.returncode,
                      elapsed_seconds=time.monotonic() - began))
    save(out / 'calls.json', dict(calls=calls))
    require(result.returncode == 0 if expected == 0 else result.returncode != 0,
            name + ': unexpected exit status; retained stdout/stderr identify the failure')
    print(json.dumps(dict(step=name, exit_code=result.returncode)), flush=True)
    if cli:
        value = load(out / (name + '.stdout'))
        require(value.get('ok') is (expected == 0), name + ': CLI envelope mismatch')
        require(value['provenance']['cli_version'] == VERSION, name + ': wrong installed CLI')
        return value
    return (out / (name + '.stdout')).read_bytes()


def source_unchanged(freeze):
    for name, pin in freeze['file_hashes'].items():
        require(sha(local(ROOT / name)) == pin, 'Frozen source, tests or offline code changed: ' + name)
    tools = freeze.get('delivery_tool_files')
    require(isinstance(tools, dict) and set(tools) == SOURCE_TOOLS, 'Frozen delivery tool scope is incomplete')
    for name, pin in tools.items():
        require(sha(local(ROOT / name)) == pin, 'Frozen delivery tool changed: ' + name)
    packaging = freeze.get('packaging_source_files')
    require(isinstance(packaging, dict) and set(packaging) == set(round_runner.packaging_source_names()),
            'Frozen packaging input scope is incomplete')
    for name, pin in packaging.items():
        require(sha(local(ROOT / name)) == pin, 'Frozen packaging input changed: ' + name)
    require(freeze.get('skill_validator') == round_runner.skill_validator_pin(),
            'Frozen native Skill validator changed')


def guards_equal(guards):
    return all(local(ROOT / name).is_file() and sha(ROOT / name) == pin for name, pin in guards.items())


def ready(args, *, formal_changed=False):
    freeze = load(ROUND / ('freeze-' + args.freeze_run) / 'verification.json')
    require(freeze['status'] == 'frozen' and freeze['cli_version'] == VERSION, 'Wrong implementation freeze')
    source_unchanged(freeze)
    if not formal_changed:
        require(guards_equal(freeze['formal_guard']), 'Formal entry changed since source freeze')
    for mode in ('source-all', 'installed-all'):
        proof = load(ROUND / (mode + '-' + args.tests_run) / 'verification.json')
        require(proof.get('status') == 'passed' and proof.get('cli_version') == VERSION
                and proof.get('file_hashes') == freeze['file_hashes']
                and type(proof.get('tests')) is int and proof['tests'] > 0
                and proof['tests'] == proof.get('discovered_tests')
                and all(type(proof.get(key)) is int and proof[key] == 0 for key in ('failures', 'errors', 'skipped')),
                'Whole source and installed regressions must both pass without skips')
        if mode == 'installed-all':
            require(proof.get('source_fallback') is False, 'Installed regression used a source fallback')
    candidate = load(ROUND / ('candidate-' + args.candidate_run) / 'verification.json')
    require(candidate['status'] == 'installed-and-byte-verified' and candidate['cli_version'] == VERSION,
            'Accepted offline candidate required')
    installed = local(candidate['installed'])
    expected = candidate['application_files']
    require(expected == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}, 'Installed application changed')
    require(sha(local(candidate['archive'])) == candidate['archive_sha256'], 'Offline application ZIP changed')
    staged = load(ROUND / ('skill-entry-' + args.stage_run) / 'verification.json')
    require(staged['status'] == 'passed' and staged['application_files'] == expected, 'Skill entry acceptance required')
    home = local(staged['home'])
    for name, pin in staged['skill_files'].items():
        require(sha(local(home / name)) == pin, 'Staged Skill changed')
    sys.path.insert(0, str(installed / 'site'))
    package = importlib.import_module('ai_ad_editor')
    require(Path(package.__file__).resolve() == installed / 'site/ai_ad_editor/__init__.py'
            and package.VERSION == VERSION, 'Do not mix source and installed imports')
    core = importlib.import_module('ai_ad_editor.delivery')
    descriptor_report = load(ROUND / ('descriptor-' + args.descriptor_run) / 'verification.json')
    descriptor = local(descriptor_report['descriptor'])
    require(descriptor_report['status'] == 'passed'
            and sha(descriptor) == descriptor_report['descriptor_sha256'], 'Delivery descriptor changed')
    spec = load(descriptor)
    if formal_changed:
        for role, row in spec['gates'].items():
            core._gate(ROOT, role, row, VERSION, expected, staged['skill_files'])
    else:
        core.verify(ROOT, descriptor)
    return dict(freeze=freeze, candidate=candidate, installed=installed, staged=staged,
                home=home, descriptor=descriptor, spec=spec, core=core)


def ps(home):
    return ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            Path(home) / SKILL / 'scripts/run.ps1']


def accepted(kind, run, context):
    path = report_path(kind, run)
    value = load(path)
    require(value.get('status') == 'passed' and value.get('cli_version') == VERSION
            and value.get('application_files') == context['candidate']['application_files']
            and value.get('skill_files') == context['staged']['skill_files'], 'Missing matching acceptance: ' + kind)
    if kind in {'portable-kit', 'formal-entry'}:
        require(value.get('packaging_source_files') == context['freeze']['packaging_source_files']
                and value.get('documentation_source_ref') == TAG, 'Accepted packaging inputs or documentation ref differ')
    return value


def quickstart(context, language):
    manifest = context['candidate']['manifest_sha256']
    text = {
    "zh": {
        "intro": "原生Windows CPython3.13 x64应用；唯一公开入口为 `$agent-ffmpeg-local-editor`，包含17个内部模块。应用ZIP不包含Python、FFmpeg／ffprobe、驱动、模型权重或完整音乐运行库。先准备本机依赖；不使用Docker、WSL或虚拟环境。",
        "download": "1. 下载本次Release的两个ZIP、SHA256SUMS.txt及本语言快速开始到同一目录。把下面的路径改为实际路径。逐项比较计算摘要与清单，全部匹配后解包到新目录；后续安装器还会校验应用内部清单。",
        "install": "2. 离线安装应用。目标目录必须是新路径。此步骤不下载模型；模型尚未准备时，可先通过安装版入口执行version／doctor及基础剪辑命令。",
        "models": "3. 配置基础剪辑模式，将统一Skill绑定到上述安装目录。时间线、滤镜、字幕、预览和渲染可直接使用；配音、翻译和语义模型按下一段另行配置。配置器先备份旧配置，再建立基础绑定并清除旧机器模型路径。",
        "gpu": "若使用GPU包，将配置命令替换为下面的形式，并填写对应的实际DLL目录。配音与翻译的CUDA版本要求不同；不要把两个目录混写。后续使用 `--device auto` 优先选择配置的GPU，并检查返回的实际设备／provider及CPU回落说明。",
        "register": "4. 注册唯一Skill并检查实际安装版本。已有同名入口且指向其他位置时，注册器会保留并拒绝替换；升级请先阅读随包交付说明，不手工删除不明目录。Agent外层只需指定 `$agent-ffmpeg-local-editor`。",
        "edit": "5. 创建工程并导入自己的授权素材。下例中的视频、图片、字幕、配音文本和changes.json必须实际存在。读取导入返回的 `data.asset.id`，再依据schema及帮助编写changes.json；不能照抄旧案例的随机ID。视频和音频轨须分别编排，先预览实际滤镜候选并记录客户选择，再合成时间线。",
        "voice": "可选配音／翻译示例会真实运行模型，需先准备输入文件、模型包与配置，并使用新的asset ID。完整音频、发音、翻译语义和时长仍需复核。生成后用真实音频资产ID编写voice-changes.json，将声音显式编入音轨，再执行下面最后一条compose；翻译字幕也须按目标轨道编排。",
        "replay": "6. 验证、预览、渲染并检查实际成片，再导出可编辑工程包。导入使用新的目标目录；重新渲染后分别检查画面、完整音轨、时钟及配方。JSON的ok／status／errors／warnings／artifacts与进程退出码需要同时检查，质量检查不能代替完整播放及听审。",
        "music": "神经音乐是额外能力，需要显式登记已有本地适配器、原生运行库和权重；上述四包不能替代音乐模型。先阅读[神经音乐说明](skills/agent-ffmpeg-local-editor/references/neural-music.md)。普通谱面合成、循环修复和神经生曲的含义不同。",
        "links": "[Skill详情与17模块](skills/agent-ffmpeg-local-editor/SKILL.md) · [滤镜客户选型](skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [配音／翻译／音频](skills/agent-ffmpeg-local-editor/references/community-materials.md) · [升级、恢复及回滚](docs/product/DELIVERY_CONTROLLER.md)",
        "limits": "发布成片前补充素材／模型／声音用途的权利证据，并执行rights check。render的--publish仅执行本地权利门禁，不上传平台。模型生成内容仍须逐项审查；本包不附未审核模型音频。同机新目录验收不等于干净主机或跨机器通过，完整剪映等价及原G01—G38条件继续开放。",
        "packs": "可选模型：需要配音／翻译时，先准备已校验的 `kokoro-zh-en-int8` 与 `opus-zh-en-cpu-int8` 两个CPU包；`kokoro-zh-en-cuda13` 与 `opus-zh-en-cuda12-int8` 为可选GPU包。PACKS指向包含这四种解包目录的父目录；配置器要求两个CPU包，并逐包验证后写入模型绑定。本次两个ZIP未包含这些模型包；来源、许可、预期摘要与复现工具见下方链接。\n\n[Model catalog and pinned manifests](https://github.com/copypasteltd/agent-editor-kit/blob/main/product/src/ai_ad_editor/material_data/model-packs.json) · [CPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_model_pack.py) · [GPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_gpu_packs.py) · [Offline pack installer](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/install_community_pack.py)"
    },
    "zh-TW": {
        "intro": "原生Windows CPython3.13 x64應用；唯一公開入口為 `$agent-ffmpeg-local-editor`，包含17個內部模組。應用ZIP不包含Python、FFmpeg／ffprobe、驅動、模型權重或完整音樂執行庫。先準備本機依賴；不使用Docker、WSL或虛擬環境。",
        "download": "1. 下載本次Release的兩個ZIP、SHA256SUMS.txt及本語言快速開始至同一目錄。將以下路徑改為實際路徑。逐項比較計算摘要與清單，全部相符後解壓縮至新目錄；後續安裝器還會核對應用內部清單。",
        "install": "2. 離線安裝應用。目標目錄必須是新路徑。此步驟不下載模型；模型尚未準備時，可先透過安裝版入口執行version／doctor及基礎剪輯命令。",
        "models": "3. 設定基礎剪輯模式，將統一Skill綁定到上述安裝目錄。時間線、濾鏡、字幕、預覽與算圖可直接使用；配音、翻譯與語意模型按下一段另行設定。設定器先備份舊設定，再建立基礎綁定並清除舊機器模型路徑。",
        "gpu": "若使用GPU包，將設定命令替換為以下形式，並填入對應的實際DLL目錄。配音與翻譯的CUDA版本要求不同；不要混用兩個目錄。後續使用 `--device auto` 優先選擇設定的GPU，並檢查回傳的實際裝置／provider及CPU回落說明。",
        "register": "4. 註冊唯一Skill並檢查實際安裝版本。已有同名入口且指向其他位置時，註冊器會保留並拒絕替換；升級請先閱讀隨包交付說明，不手動刪除不明目錄。Agent外層只需指定 `$agent-ffmpeg-local-editor`。",
        "edit": "5. 建立專案並匯入自己的授權素材。以下影片、圖片、字幕、配音文字和changes.json必須實際存在。讀取匯入回傳的 `data.asset.id`，再依schema及說明編寫changes.json；不能照抄舊案例的隨機ID。影片與音訊軌須分別編排，先預覽實際濾鏡候選並記錄客戶選擇，再合成時間線。",
        "voice": "可選配音／翻譯範例會實際執行模型，須先準備輸入檔案、模型包與設定，並使用新的asset ID。完整音訊、發音、翻譯語意與時長仍須複核。生成後用實際音訊資產ID編寫voice-changes.json，將聲音明確編入音軌，再執行以下最後一條compose；翻譯字幕也須依目標軌道編排。",
        "replay": "6. 驗證、預覽、算圖並檢查實際成片，再匯出可編輯專案包。匯入使用新的目標目錄；重新算圖後分別檢查畫面、完整音軌、時鐘與配方。JSON的ok／status／errors／warnings／artifacts與程序結束碼需要同時檢查，品質檢查不能代替完整播放及聽審。",
        "music": "神經音樂是額外能力，需要明確登記既有本機適配器、原生執行庫與權重；上述四包不能替代音樂模型。先閱讀[神經音樂說明](skills/agent-ffmpeg-local-editor/references/neural-music.md)。一般譜面合成、循環修復與神經生曲的含義不同。",
        "links": "[Skill詳情與17模組](skills/agent-ffmpeg-local-editor/SKILL.md) · [濾鏡客戶選型](skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [配音／翻譯／音訊](skills/agent-ffmpeg-local-editor/references/community-materials.md) · [升級、恢復及回滾](docs/product/DELIVERY_CONTROLLER.md)",
        "limits": "發佈成片前補充素材／模型／聲音用途的權利證據，並執行rights check。render的--publish僅執行本機權利門檻，不上傳平台。模型生成內容仍須逐項審查；本包不附未審核模型音訊。同機新目錄驗收不等於乾淨主機或跨機器通過，完整剪映等價及原G01—G38條件繼續開放。",
        "packs": "選用模型：需要配音／翻譯時，先準備已核對的 `kokoro-zh-en-int8` 與 `opus-zh-en-cpu-int8` 兩個CPU套件；`kokoro-zh-en-cuda13` 與 `opus-zh-en-cuda12-int8` 為選用GPU套件。PACKS指向包含這四種解壓目錄的父目錄；設定器要求兩個CPU套件，逐一驗證後才寫入模型綁定。本次兩個ZIP未包含這些模型套件；來源、授權、預期摘要與重現工具見下方連結。\n\n[Model catalog and pinned manifests](https://github.com/copypasteltd/agent-editor-kit/blob/main/product/src/ai_ad_editor/material_data/model-packs.json) · [CPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_model_pack.py) · [GPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_gpu_packs.py) · [Offline pack installer](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/install_community_pack.py)"
    },
    "en": {
        "intro": "Native Windows CPython3.13 x64 application. The only public entry is `$agent-ffmpeg-local-editor`, with 17 internal modules. Python, FFmpeg/ffprobe, drivers, model weights and the complete music runtime are separate local dependencies. Do not use Docker, WSL or virtual environments.",
        "download": "1. Download both ZIPs, SHA256SUMS.txt and this quickstart from the same release into one directory. Replace the example paths. Compare each computed digest with the checksum list before extracting into new directories; the installer also checks the internal application inventory.",
        "install": "2. Install the application offline into a new target. This does not download models. Before model setup, the installed entry can already run version/doctor and basic editing commands.",
        "models": "3. Configure basic editing by binding the unified Skill to the installation above. Timeline editing, filters, captions, previews and rendering are available through this entry. Configure voice, translation and semantic models separately below. The configurator backs up previous settings and creates a basic binding without inherited machine model paths.",
        "gpu": "For GPU packs, replace the configuration command with the following and provide the actual matching DLL directories. Speech and translation require different CUDA versions. Use `--device auto` to prefer the configured GPU, and inspect the actual device/provider and any reported CPU fallback.",
        "register": "4. Register the one Skill and inspect the actual installed version. A same-name entry pointing elsewhere is preserved and registration refuses to replace it. For upgrades, read the shipped delivery guide rather than deleting an unknown directory. Select `$agent-ffmpeg-local-editor` from the outer Agent.",
        "edit": "5. Create a project and ingest your authorized media. The example video, still, subtitles, narration text and changes.json must exist. Read the returned `data.asset.id`, then author changes.json using the schema and command help; never copy a random asset ID from an old case. Author video and audio tracks separately, preview real look candidates and record client choices before composing.",
        "voice": "The optional speech/translation examples perform actual inference. Prepare their inputs, model packs and configuration first, and use a new asset ID. Review complete audio, pronunciation, translation meaning and duration. Then author voice-changes.json with the actual audio asset ID and an explicit audio track before the final compose command below; place translated subtitles on their intended track too.",
        "replay": "6. Validate, preview, render and inspect the encoded movie, then export an editable project package. Import into a new directory and re-render; check images, complete audio, clocks and recipes separately. Inspect exit codes and JSON ok/status/errors/warnings/artifacts together. Automated quality checks do not replace continuous playback or listening.",
        "music": "Neural music additionally needs an explicitly registered existing local adapter, native runtime and weights; the four packs above do not supply that model. Read [neural music](skills/agent-ffmpeg-local-editor/references/neural-music.md). Editable score synthesis, loop repair and neural generation are separate operations.",
        "links": "[Skill and 17 modules](skills/agent-ffmpeg-local-editor/SKILL.md) · [Client look selection](skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Speech, translation and audio](skills/agent-ffmpeg-local-editor/references/community-materials.md) · [Upgrade, recovery and rollback](docs/product/DELIVERY_CONTROLLER.md)",
        "limits": "Before publishing media, add source/model/voice-use rights evidence and run rights check. render --publish is a local rights gate, not an upload. Review generated content individually; these attachments exclude unreviewed model audio. A new directory on the same host does not establish clean-host or cross-machine acceptance. Full CapCut parity and all original G01–G38 conditions remain open.",
        "packs": "Optional models: prepare verified `kokoro-zh-en-int8` and `opus-zh-en-cpu-int8` CPU packs before enabling voice/translation. `kokoro-zh-en-cuda13` and `opus-zh-en-cuda12-int8` are optional GPU packs. PACKS is the parent of these extracted pack directories. Model configuration requires both CPU packs and verifies each selected pack before binding it. The two release ZIPs do not contain these packs; use the source, license, digest and reproduction links below.\n\n[Model catalog and pinned manifests](https://github.com/copypasteltd/agent-editor-kit/blob/main/product/src/ai_ad_editor/material_data/model-packs.json) · [CPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_model_pack.py) · [GPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_gpu_packs.py) · [Offline pack installer](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/install_community_pack.py)"
    }
}[language]
    return f'''# agent editor kit / CLI{VERSION}

{text['intro']}

{text['download']}

```powershell
$downloads = "E:/video-tools/downloads"
$bundle = "E:/video-tools/application-bundle"
$kit = "E:/video-tools/skill-kit"
Get-Content -LiteralPath "$downloads/SHA256SUMS.txt"
Get-FileHash -LiteralPath "$downloads/agent-editor-kit-{TAG}-cp313-win_amd64.zip" -Algorithm SHA256
Get-FileHash -LiteralPath "$downloads/agent-editor-kit-community-unified-skill-r59.zip" -Algorithm SHA256
Expand-Archive -LiteralPath "$downloads/agent-editor-kit-{TAG}-cp313-win_amd64.zip" -DestinationPath $bundle
Expand-Archive -LiteralPath "$downloads/agent-editor-kit-community-unified-skill-r59.zip" -DestinationPath $kit
```

{text['install']}

```powershell
$python = "C:/Python313/python.exe"
$installed = "E:/video-tools/application-installed"
& $python -E -B -X utf8 "$bundle/install.py" --bundle $bundle --target $installed --manifest-sha256 "{manifest}"
& $python -I -S -B -X utf8 "$installed/run.py" version
& $python -I -S -B -X utf8 "$installed/run.py" doctor
```

{text['models']}

```powershell
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --base-only
```

{text['packs']}

```powershell
$packs = "E:/video-tools/model-packs"
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --packs $packs
```

{text['gpu']}

```powershell
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --packs $packs --voice-cuda-lib "E:/video-tools/cuda13/bin" --translation-cuda-lib "E:/video-tools/cuda12/bin"
```

{text['register']}

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$kit/register-agent-ffmpeg-local-skills.ps1"
$entry = "$kit/skills/agent-ffmpeg-local-editor/scripts/run.ps1"
& $entry version
& $entry doctor
& $entry capabilities
& $entry model-pack list
& $entry gpu inspect
```

{text['edit']}

```powershell
$aekProject = "E:/video-work/my-ad"
& $entry project init $aekProject --name "My ad"
& $entry media ingest --project $aekProject --input "E:/media/product.mp4"
& $entry schema show
& $entry timeline compose --help
& $entry look list --query "Kodak"
& $entry look inspect --id t3-kodak-gold-200
& $entry look preview --id t3-kodak-gold-200 --input "E:/media/still.png" --output "$aekProject/exports/film-preview.png" --strength 0.65
& $entry timeline compose --project $aekProject --input "E:/video-work/changes.json"
& $entry look apply --project $aekProject --id t3-kodak-gold-200 --global --strength 0.65 --dry-run
& $entry look apply --project $aekProject --id t3-kodak-gold-200 --global --strength 0.65
```

{text['voice']}

```powershell
& $entry voice list
& $entry voice synthesize --project $aekProject --voice zf_001 --input "E:/media/narration.txt" --device auto --asset-id asset_voice
& $entry translate subtitles --project $aekProject --from zh-Hans --to en --input "E:/media/captions.srt" --output exports/bilingual.srt --mode bilingual --device auto
& $entry timeline compose --project $aekProject --input "E:/video-work/voice-changes.json"
```

{text['replay']}

```powershell
& $entry validate --project $aekProject
& $entry preview frame --project $aekProject --frame 0
& $entry render --project $aekProject --output "$aekProject/renders/ad.mp4"
& $entry quality check --project $aekProject --input "$aekProject/renders/ad.mp4"
& $entry convert export --project $aekProject --target-format package --output "$aekProject/exports/ad.aevpkg.zip"
& $entry convert import --input "$aekProject/exports/ad.aevpkg.zip" --output "E:/video-work/restored-ad"
& $entry render --project "E:/video-work/restored-ad" --output "E:/video-work/restored-ad/renders/replay.mp4"
& $entry rights check --project $aekProject
```

{text['music']}

```powershell
& $entry music generate --help
& $entry delivery --help
```

{text['links']}

{text['limits']}

`{RELEASE}` / CLI`{VERSION}`
'''


def kit(args):
    context = ready(args)
    out = begin('kit', args.run)
    work = local(LOCAL / ('kit-' + args.run))
    require(not work.exists(), 'Preserve earlier kit outputs')
    work.mkdir(parents=True)
    base_report = json.loads(execute(out, 'base-packager', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        ROOT / 'scripts/package_community_skill.py', '--output', work / 'base',
        '--skill-source', context['home'], '--archive-name', 'base.zip', '--source-ref', TAG]))
    packaging = context['freeze']['packaging_source_files']
    require(base_report.get('packaging_source_files') == {name: pin for name, pin in packaging.items()
            if name != 'docs/product/DELIVERY_CONTROLLER.md'}
            and base_report.get('documentation_source_ref') == TAG, 'Base packager inputs or documentation ref differ')
    content = {}
    with zipfile.ZipFile(work / 'base/base.zip') as zipped:
        archive_plan(zipped)
        base_inventory = decode(zipped.read('KIT-FILES.json'))
        require(base_inventory.get('packaging_source_files') == base_report['packaging_source_files']
                and base_inventory.get('documentation_source_ref') == TAG, 'Base ZIP provenance differs from its receipt')
        for name in zipped.namelist():
            if name != 'KIT-FILES.json':
                content[name] = zipped.read(name)
    for language, suffix in [('zh', ''), ('zh-TW', '.zh-TW'), ('en', '.en')]:
        content['QUICKSTART' + suffix + '.md'] = quickstart(context, language).encode('utf-8')
    content['docs/product/DELIVERY_CONTROLLER.md'] = (ROOT / 'docs/product/DELIVERY_CONTROLLER.md').read_bytes()
    inventory = dict(format='agent-community-single-skill-v1', release=RELEASE, cli_version=VERSION,
        packaging_source_files=packaging, documentation_source_ref=TAG,
        skill_count=1, module_count=17, files=[dict(path=name, bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest()) for name, data in sorted(content.items())])
    content['KIT-FILES.json'] = encoded(inventory)
    destination = work / 'agent-editor-kit-community-unified-skill-r59.zip'
    with zipfile.ZipFile(destination, 'x') as zipped:
        for name, data in sorted(content.items()):
            member(name)
            info = zipfile.ZipInfo(name, (2026, 11, 6, 0, 0, 0))
            info.compress_type, info.external_attr = zipfile.ZIP_DEFLATED, 0o100644 << 16
            zipped.writestr(info, data)
    source_unchanged(context['freeze'])
    require(guards_equal(context['freeze']['formal_guard']), 'Formal entry changed during packaging')
    save(out / 'verification.json', dict(status='built-not-yet-independently-accepted', cli_version=VERSION,
        archive=str(destination), archive_sha256=sha(destination), entries=len(content),
        application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
        packaging_source_files=packaging, documentation_source_ref=TAG,
        actual_registered_entry_tested=False, formal_activation=False))


def replay(context, out, prefix, work, label):
    reference = load(ROUND / ('package-replay-' + context['args'].package_run) / 'verification.json')
    package = local(reference['project_package'])
    project = work / (label + '-project')
    execute(out, label + '-import', [*prefix, 'convert', 'import', '--input', package, '--output', project], cli=True)
    movie = project / 'renders/handoff.mp4'
    execute(out, label + '-render', [*prefix, 'render', '--project', project, '--output', movie], cli=True)
    ffmpeg = importlib.import_module('ai_ad_editor.media').ffmpeg_path()
    result = {}
    for kind, options in [('RGBA', ['-map', '0:v:0', '-an', '-pix_fmt', 'rgba']),
                          ('PCM', ['-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le'])]:
        raw = execute(out, label + '-' + kind, [ffmpeg, '-nostdin', '-v', 'error', '-i', movie,
            *options, '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
        result[kind] = raw.decode().strip()
        require(result[kind] == reference['decoded']['original_' + kind], 'Whole replay media differs: ' + kind)
    music = load(ROUND / ('native-music-' + context['args'].music_run) / 'verification.json')
    asset = next(row for row in load(project / 'project.json')['assets'] if row['id'] == music['asset']['id'])
    require(sha(project / asset['uri']) == music['master_audio']['sha256']
            and asset['source']['music_generation'] == music['asset']['source']['music_generation'],
            'Portable replay lost master audio or editable recipe')
    return dict(project=str(project), movie=str(movie), decoded=result, full_master_and_recipe_equal=True)


def verify_kit(args):
    context = ready(args)
    context['args'] = args
    built = load(report_path('kit', args.kit_run))
    require(built['cli_version'] == VERSION and sha(local(built['archive'])) == built['archive_sha256'], 'Kit archive changed')
    require(built.get('packaging_source_files') == context['freeze']['packaging_source_files']
            and built.get('documentation_source_ref') == TAG, 'Built kit source provenance changed')
    out = begin('portable-kit', args.run)
    work = local(LOCAL / ('portable-' + args.run))
    require(not work.exists(), 'Preserve earlier portable verification')
    work.mkdir(parents=True)
    home = work / '工具包 中文 spaces'
    extracted = extract(built['archive'], home, skill=True)
    require(extracted.get('packaging_source_files') == built['packaging_source_files']
            and extracted.get('documentation_source_ref') == TAG, 'Extracted kit source provenance differs')
    require(load(home / MANIFEST)['files'] == load(context['home'] / MANIFEST)['files'], 'Kit changed Skill inventory')
    bundle = work / 'application-bundle'
    extract(context['candidate']['archive'], bundle)
    installed = work / 'application-installed'
    execute(out, 'portable-install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        bundle / 'install.py', '--bundle', bundle, '--target', installed,
        '--manifest-sha256', context['candidate']['manifest_sha256'], '--timeout-seconds', '600'])
    require({p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
            == context['candidate']['application_files'], 'Fresh portable application differs')
    configuration = json.loads(execute(out, 'portable-basic-configuration',
        [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
         home / 'scripts/activate_community_runtime.py', '--installed', installed, '--base-only']))
    require(configuration.get('configuration_mode') == 'base-only'
            and configuration.get('verified_packs') == []
            and configuration.get('model_verification_performed') is False,
            'Portable basic editing configuration unexpectedly requires models')
    require(load(home / CONFIG)['installed_directory'] == str(installed)
            and load(home / 'local/agent-ffmpeg/community-runtime.json') == {},
            'Portable basic configuration retained foreign machine model paths')
    discovery = work / 'isolated-discovery'
    execute(out, 'portable-register', ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
        home / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
        '-ReceiptPath', out / 'registration.json'])
    require((discovery / 'agent-ffmpeg-local-editor').resolve() == (home / SKILL).resolve(), 'Registration did not select portable Skill')
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
              discovery / 'agent-ffmpeg-local-editor/scripts/run.ps1']
    execute(out, 'portable-version', [*prefix, 'version'], cli=True)
    capabilities = execute(out, 'portable-capabilities', [*prefix, 'capabilities'], cli=True)
    require(capabilities['data']['capabilities']['verified_skill_delivery']['protocol'] == 'agent-editor-skill-delivery-v2',
            'Portable entry does not discover the delivery controller')
    result = replay(context, out, prefix, work, 'portable')
    source_unchanged(context['freeze'])
    require(guards_equal(context['freeze']['formal_guard']), 'Portable test changed formal discovery')
    save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
        application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
        kit_archive=built['archive'], kit_sha256=built['archive_sha256'], fresh_offline_install=True,
        packaging_source_files=built['packaging_source_files'], documentation_source_ref=TAG,
        independent_registration=True, actual_PowerShell_entry=True, source_fallback=False,
        actual_base_only_configuration=True, optional_model_packs_required=False,
        complete_RGBA_PCM_replay=True, replay=result, clean_host=False, cross_machine=False,
        formal_activation=False, human_listening=False, natural_quality_accepted=False))


def activate(args):
    context = ready(args)
    context['args'] = args
    accepted('portable-kit', args.kit_verify_run, context)
    faults = accepted('music-faults', args.faults_run, context)
    require(set(faults.get('cases', {})) == {'cancel', 'timeout', 'publication-conflict'}
            and all(row.get('passed') is True for row in faults['cases'].values()), 'Actual music fault cases required')
    out = begin('formal-entry', args.run)
    work = local(LOCAL / ('formal-' + args.run))
    work.mkdir(parents=True)
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', context['installed'] / 'run.py']
    execute(out, 'inspect', [*prefix, 'delivery', 'inspect', '--workspace', ROOT, '--descriptor', context['descriptor']], cli=True)
    execute(out, 'plan', [*prefix, 'delivery', 'activate', '--workspace', ROOT, '--descriptor', context['descriptor'], '--dry-run'], cli=True)
    active = False
    try:
        first = execute(out, 'activate-first', [*prefix, 'delivery', 'activate', '--workspace', ROOT,
            '--descriptor', context['descriptor']], cli=True)['data']
        active = True
        execute(out, 'registered-first-version', [*ps(ROOT), 'version'], cli=True)
        execute(out, 'rollback-plan', [*prefix, 'delivery', 'rollback', '--workspace', ROOT, '--dry-run'], cli=True)
        execute(out, 'rollback-first', [*prefix, 'delivery', 'rollback', '--workspace', ROOT], cli=True)
        active = False
        require(guards_equal(context['freeze']['formal_guard']), 'Explicit rollback did not restore exact formal files')
        old = execute(out, 'previous-entry-version', [*ps(ROOT), 'version'])
        require(json.loads(old)['data']['cli_version'] == '0.1.63', 'Rollback did not restore previous actual runtime')
        second = execute(out, 'activate-final', [*prefix, 'delivery', 'activate', '--workspace', ROOT,
            '--descriptor', context['descriptor']], cli=True)['data']
        active = True
        discovery = Path.home() / '.codex/skills/agent-ffmpeg-local-editor'
        require(discovery.resolve() == (ROOT / SKILL).resolve(), 'The real discovered Skill is not this installation')
        real_prefix = ps(ROOT)
        real_prefix[-1] = discovery / 'scripts/run.ps1'
        execute(out, 'actual-discovery-version', [*real_prefix, 'version'], cli=True)
        result = replay(context, out, real_prefix, work, 'actual-discovery')
        for row in context['spec']['files']:
            require(sha(ROOT / row['path']) == row['sha256'], 'Formal file changed during acceptance')
        source_unchanged(context['freeze'])
        save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
            application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
            packaging_source_files=context['freeze']['packaging_source_files'], documentation_source_ref=TAG,
            actual_C_drive_discovery=True, actual_PowerShell_entry=True, source_fallback=False,
            explicit_rollback_byte_equal=True, previous_delivery_id=first['delivery_id'],
            delivery_id=second['delivery_id'], complete_RGBA_PCM_replay=True, replay=result,
            formal_activation=True, backups_preserved=True, human_listening=False, natural_quality_accepted=False))
    except BaseException as exc:
        recovery = None
        if active:
            try:
                recovery = execute(out, 'rollback-on-failed-acceptance', [*prefix, 'delivery', 'rollback', '--workspace', ROOT], cli=True)
            except BaseException as recovery_error:
                recovery = dict(error=repr(recovery_error), manual_recovery_required=True)
        save(out / 'verification.json', dict(status='failed', cli_version=VERSION, error=repr(exc), recovery=recovery,
            formal_activation=not guards_equal(context['freeze']['formal_guard'])))
        raise


def assets(args):
    context = ready(args, formal_changed=True)
    formal = accepted('formal-entry', args.formal_run, context)
    portable = accepted('portable-kit', args.kit_verify_run, context)
    for row in context['spec']['files']:
        require(sha(ROOT / row['path']) == row['sha256'], 'Formal entry changed after acceptance')
    source_binding = capture_release_source(context)
    out = begin('release-assets', args.run)
    directory = local(LOCAL / ('release-assets-' + args.run))
    require(not directory.exists(), 'Earlier release assets are immutable')
    directory.mkdir(parents=True)
    sources = {
        'agent-editor-kit-' + TAG + '-cp313-win_amd64.zip': local(context['candidate']['archive']),
        'agent-editor-kit-community-unified-skill-r59.zip': local(portable['kit_archive']),
    }
    require(sha(sources['agent-editor-kit-community-unified-skill-r59.zip']) == portable['kit_sha256'], 'Accepted kit changed')
    for name, source in sources.items():
        shutil.copyfile(source, directory / name)
        require(sha(directory / name) == sha(source), 'Release attachment changed while copying')
    for language, suffix in [('zh', ''), ('zh-TW', '.zh-TW'), ('en', '.en')]:
        (directory / ('QUICKSTART' + suffix + '.md')).write_text(quickstart(context, language), encoding='utf-8', newline='\n')
    notes = ('# agent editor kit ' + TAG + '\n\n'
        'CLI0.1.66, one public Skill and 17 internal modules. Includes complete restore preflight, '
        'bounded durable transaction backups, bounded music progress reads and the v2 verified delivery controller.\n\n'
        'Acceptance: matching whole-source/installed regressions, actual CUDA neural music, complete PCM and '
        'editable project replay, actual cancellation/timeout/publication-conflict cases, fresh same-host offline '
        'installation, portable Skill registration, formal activation and explicit rollback.\n\n'
        'Python3.13 x64, FFmpeg, drivers, model weights and external music runtime are separate dependencies. '
        'Neural outputs remain internal/unverified and are excluded from these attachments. No human listening, '
        'clean-host/cross-machine certification or full CapCut parity is claimed. The original G01–G38 scope remains open.\n\n'
        'Start with offline application installation, --base-only configuration and the single Skill; '
        'AI model packs are optional. Read QUICKSTART.en.md before use.\n\n'
        '简体：校验摘要后离线安装应用，以--base-only完成基础配置，再注册唯一Skill；'
        'AI模型按需单独配置，使用前查看QUICKSTART.md。\n\n'
        '繁體：核對摘要後離線安裝應用，以--base-only完成基礎設定，再註冊唯一Skill；'
        'AI模型按需另行設定，使用前查看QUICKSTART.zh-TW.md。\n')
    (directory / 'RELEASE-NOTES.md').write_text(notes, encoding='utf-8', newline='\n')
    rows = [dict(name=path.name, bytes=path.stat().st_size, sha256=sha(path)) for path in sorted(directory.iterdir())]
    (directory / 'SHA256SUMS.txt').write_text(''.join(row['sha256'] + '  ' + row['name'] + '\n' for row in rows), encoding='utf-8', newline='\n')
    rows.append(dict(name='SHA256SUMS.txt', bytes=(directory / 'SHA256SUMS.txt').stat().st_size, sha256=sha(directory / 'SHA256SUMS.txt')))
    gates = {kind: dict(path=str(report_path(kind, run)), sha256=sha(report_path(kind, run))) for kind, run in
             [('formal-entry', args.formal_run), ('portable-kit', args.kit_verify_run), ('music-faults', args.faults_run)]}
    lock = dict(format=RELEASE_LOCK_FORMAT, repository='copypasteltd/agent-editor-kit', tag=TAG,
        runtime_release=RELEASE, cli_version=VERSION, assets=rows, gates=gates,
        frozen_source=context['freeze']['file_hashes'], frozen_packaging_sources=context['freeze']['packaging_source_files'],
        source_binding=source_binding, descriptor=str(context['descriptor']),
        descriptor_sha256=sha(context['descriptor']), formal_delivery_id=formal['delivery_id'],
        public_model_media_included=False, created_at_utc=datetime.now(timezone.utc).isoformat())
    save(directory / 'release-lock.json', lock)
    save(out / 'verification.json', dict(status='ready-not-published', cli_version=VERSION,
        directory=str(directory), lock_sha256=sha(directory / 'release-lock.json'),
        assets=rows, formal_activation=True, publication_attempted=False))


def arguments(parser=None):
    parser = parser or argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    for name, default in [('freeze', 'r4'), ('tests', 'r4'), ('candidate', 'r1'), ('stage', 'r1'),
                           ('music', 'r1'), ('package', 'r1'), ('descriptor', 'r1'), ('kit', 'r1'),
                           ('kit-verify', 'r1'), ('faults', 'r1'), ('formal', 'r1')]:
        parser.add_argument('--' + name + '-run', default=default)
    return parser


def main():
    parser = arguments()
    parser.add_argument('action', choices=['kit', 'verify-kit', 'activate', 'assets'])
    args = parser.parse_args()
    require(os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix,
            'Use native Windows Python -B without a virtual environment')
    for name, value in vars(args).items():
        if name == 'run' or name.endswith('_run'):
            require(value.isalnum() and len(value) <= 32, 'Invalid run ID')
    return {'kit': kit, 'verify-kit': verify_kit, 'activate': activate, 'assets': assets}[args.action](args)


if __name__ == '__main__':
    raise SystemExit(main())
