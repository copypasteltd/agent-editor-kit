"""Agent commands for built-in materials, offline voice/translation and music."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from . import community_audio, community_device, community_models, material_catalog, material_project
from .captions import cues_to_srt, parse_caption_file, validate_cues
from .errors import AppError, argument_error
from .media import probe_media
from .policy import require_local_reference
from .project import load_project
from .rights import active_records, add_record, load_ledger, save_ledger
from .utils import atomic_write_json, atomic_write_text, ensure_inside, new_id, now_iso, sha256_bytes, sha256_file


def placement_parser(parser):
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--sequence-id', default=None)
    parser.add_argument('--track-id', default=None)
    parser.add_argument('--timeline-start-seconds', type=float, default=0.)


def placement(args):
    return dict(apply=args.apply, sequence_id=args.sequence_id, track_id=args.track_id, start=args.timeline_start_seconds)


def device_parser(parser):
    parser.add_argument('--device', choices=['auto', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--gpu-pack', default=None)
    parser.add_argument('--device-index', type=int, default=0)
    parser.add_argument('--cuda-library-directory', default=None, help='显式指定已安装的 NVIDIA 运行库目录')


def add_parser(subs, leaf):
    gpu = subs.add_parser('gpu', help='检查本机 NVIDIA GPU 与空闲显存；不调度其他任务')
    gpu_actions = gpu.add_subparsers(dest='action', required=True)
    leaf(gpu_actions.add_parser('inspect'))
    materials = subs.add_parser('materials', help='内置开源音乐、短乐、音效和字体')
    actions = materials.add_subparsers(dest='action', required=True)
    search = leaf(actions.add_parser('list', help='按稳定 ID、类别、许可和多语名称检索'))
    search.add_argument('--query', default='')
    search.add_argument('--kind', choices=material_catalog.KINDS, default=None)
    search.add_argument('--category', default=None)
    search.add_argument('--limit', type=int, default=40)
    search.add_argument('--offset', type=int, default=0)
    inspect = leaf(actions.add_parser('inspect', help='查看具体内容、原始来源和许可'))
    inspect.add_argument('--id', required=True)
    verify = leaf(actions.add_parser('verify', help='校验音频/字体与许可的真实字节'))
    scope = verify.add_mutually_exclusive_group(required=True)
    scope.add_argument('--id')
    scope.add_argument('--all', action='store_true')
    ingest = leaf(actions.add_parser('ingest', help='复制内置素材、许可与署名证据到可编辑工程'))
    ingest.add_argument('--project', required=True)
    ingest.add_argument('--id', required=True)
    ingest.add_argument('--asset-id', default=None)
    placement_parser(ingest)

    voice = subs.add_parser('voice', help='Kokoro 中英离线 CPU 音色库与配音')
    actions = voice.add_subparsers(dest='action', required=True)
    voices = leaf(actions.add_parser('list', help='检索上游 103 个具名音色；权重另见离线包'))
    voices.add_argument('--language', choices=['zh', 'en'], default=None)
    voices.add_argument('--query', default='')
    synth = leaf(actions.add_parser('synthesize', help='使用显式校验的离线 Kokoro 包生成并导入 WAV'))
    synth.add_argument('--project', required=True)
    synth.add_argument('--pack', default=None)
    text = synth.add_mutually_exclusive_group(required=True)
    text.add_argument('--text')
    text.add_argument('--input')
    synth.add_argument('--voice', default='zf_001')
    synth.add_argument('--speed', type=float, default=1.)
    synth.add_argument('--threads', type=int, default=2)
    synth.add_argument('--asset-id', default=None)
    synth.add_argument('--output', default=None)
    placement_parser(synth)
    device_parser(synth)

    translate = subs.add_parser('translate', help='OPUS 中英双向 CPU 翻译和保留时序的字幕')
    actions = translate.add_subparsers(dest='action', required=True)
    for action in ('text', 'subtitles'):
        parser = leaf(actions.add_parser(action, help='翻译 UTF-8 文本' if action == 'text' else '翻译字幕并保留 cue 顺序与时间'))
        parser.add_argument('--project', required=True)
        parser.add_argument('--pack', default=None)
        parser.add_argument('--from', dest='source_language', choices=['en', 'zh-Hans', 'zh-Hant'], required=True)
        parser.add_argument('--to', dest='target_language', choices=['en', 'zh-Hans', 'zh-Hant'], required=True)
        parser.add_argument('--output', required=True)
        parser.add_argument('--threads', type=int, default=2)
        parser.add_argument('--beam-size', type=int, default=4)
        parser.add_argument('--glossary', default=None, help='有源词、目标词和已知译法的显式译后替换 JSON')
        device_parser(parser)
        if action == 'text':
            group = parser.add_mutually_exclusive_group(required=True)
            group.add_argument('--text')
            group.add_argument('--input')
        else:
            parser.add_argument('--input', required=True)
            parser.add_argument('--mode', choices=['translation', 'bilingual'], default='translation')

    packs = subs.add_parser('model-pack', help='查看或验证本版支持的离线 CPU 模型包')
    actions = packs.add_subparsers(dest='action', required=True)
    leaf(actions.add_parser('list'))
    verify = leaf(actions.add_parser('verify'))
    verify.add_argument('--id', required=True)
    verify.add_argument('--pack', required=True)

    music = subs.add_parser('music', help='本地可编辑谱面合成、音效、BGM准备和侧链闪避')
    actions = music.add_subparsers(dest='action', required=True)
    inspect_score = leaf(actions.add_parser('inspect-score', help='校验并规范化本地可编辑谱面，不生成文件'))
    inspect_score.add_argument('--input', required=True)
    compose = leaf(actions.add_parser('compose', help='用本地解析合成器生成谱面音频；不是神经文本生曲'))
    compose.add_argument('--input', required=True)
    effect = leaf(actions.add_parser('effect', help='生成可编辑的程序whoosh/riser/impact/chime音效'))
    effect.add_argument('--preset', choices=['whoosh', 'riser', 'impact', 'chime'], required=True)
    effect.add_argument('--duration-seconds', type=float, required=True)
    effect.add_argument('--seed', type=int, default=0)
    effect.add_argument('--pitch', type=int, default=60)
    for parser in (compose, effect):
        parser.add_argument('--project', required=True)
        parser.add_argument('--new-asset-id', default=None)
        parser.add_argument('--stems', action='store_true')
        placement_parser(parser)
    repair_loop = leaf(actions.add_parser('repair-loop', help='交叠修复循环接缝；明确缩短周期，不保证听感无缝'))
    repair_loop.add_argument('--project', required=True)
    repair_loop.add_argument('--asset-id', default=None)
    repair_loop.add_argument('--input', default=None, help='本地可编辑loop recipe JSON，与源及处理选项互斥')
    repair_loop.add_argument('--crossfade-ms', type=float, default=None)
    repair_loop.add_argument('--curve', choices=['linear','raised-cosine'], default=None)
    repair_loop.add_argument('--new-asset-id', default=None)
    placement_parser(repair_loop)
    prepare = leaf(actions.add_parser('prepare', help='裁切或显式循环、增益、淡入淡出并保留源记录'))
    prepare.add_argument('--asset-id', required=True)
    prepare.add_argument('--duration-seconds', type=float, required=True)
    prepare.add_argument('--offset-seconds', type=float, default=0.)
    prepare.add_argument('--loop', action='store_true')
    prepare.add_argument('--gain-db', type=float, default=0.)
    prepare.add_argument('--fade-in-seconds', type=float, default=0.)
    prepare.add_argument('--fade-out-seconds', type=float, default=0.)
    mix = leaf(actions.add_parser('mix', help='显式混合人声与配乐；保留原分轨并可压低配乐'))
    mix.add_argument('--voice-asset-id', required=True)
    mix.add_argument('--music-asset-id', required=True)
    mix.add_argument('--duration-seconds', type=float, default=None)
    mix.add_argument('--voice-gain-db', type=float, default=0.)
    mix.add_argument('--music-gain-db', type=float, default=-18.)
    mix.add_argument('--duck', action='store_true')
    mix.add_argument('--duck-threshold', type=float, default=0.02)
    mix.add_argument('--duck-ratio', type=float, default=8.)
    mix.add_argument('--duck-attack-ms', type=float, default=20.)
    mix.add_argument('--duck-release-ms', type=float, default=250.)
    mix.add_argument('--loop-music', action='store_true')
    for parser in (prepare, mix):
        parser.add_argument('--project', required=True)
        parser.add_argument('--new-asset-id', default=None)
        parser.add_argument('--output', default=None)
        placement_parser(parser)


def read_text(args) -> str:
    if args.input:
        require_local_reference(args.input, field='input')
        path = Path(args.input).expanduser().resolve()
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise argument_error('文本必须为不超过 1 MiB 的本地 UTF-8 文件', 'input')
        text = path.read_text('utf-8-sig')
    else:
        text = args.text
    if not text or not text.strip() or '\x00' in text:
        raise argument_error('文本不能为空或包含 NUL', 'text/input')
    return text.strip()


def ensure_model_rights(root: Path, pack: Path, manifest: dict[str, Any], model_id: str) -> str:
    model = manifest['models'][model_id]
    ident = 'model_' + model_id.replace('-', '_') + '_' + model['sha256'][:12]
    ledger = load_ledger(root)
    current = next((r for r in active_records(ledger) if r['asset_id'] == ident), None)
    if current:
        if current['sha256'] != 'sha256:' + model['sha256']:
            raise AppError('MODEL_RIGHTS_HASH_MISMATCH', '既有模型权利与当前模型包不符', exit_code=7)
        return ident
    directory = ensure_inside(root, root / 'assets/model-evidence' / ident)
    directory.mkdir(parents=True, exist_ok=False)
    evidence = (directory / 'SOURCE.txt').relative_to(root).as_posix()
    atomic_write_text(root / evidence, 'Offline model source and output review context\n' + json.dumps(model, ensure_ascii=False, indent=2)
                      + '\n\nOriginal model license\n' + (pack / model['license_path']).read_text('utf-8-sig'))
    add_record(ledger, dict(asset_id=ident, kind='model', sha256='sha256:' + model['sha256'],
                            source_url='local://' + evidence, source_version=manifest['id'], creator=model['creator'],
                            license_spdx=model['license'], license_url=evidence, evidence=evidence,
                            attribution=model['creator'] + '; ' + model['id'] + '; source and license in ' + evidence,
                            permitted_uses=['internal', 'commercial_ad'], restrictions=model.get('obligations', []),
                            verification_status='verified', verified_by='pinned-offline-model-pack',
                            takedown_status='clear', retrieved_at=now_iso(),
                            notes='Model permission is recorded separately from generated text, voice and project-context review.'))
    save_ledger(root, ledger)
    return ident


def run_inference(args, root, payload, task, pack, manifest, device):
    try:
        result = community_models.infer(root, pack=str(pack), pack_id=manifest['id'], task=task,
                                         payload=payload, dry_run=args.dry_run)
    except AppError as error:
        # Corrupt/missing packs never silently fall back. Only a real CUDA
        # worker failure may retry CPU in auto mode, before any output exists.
        if args.device != 'auto' or device['selected'] != 'cuda' or error.code != 'COMMUNITY_MODEL_FAILED':
            raise
        if payload.get('output') and Path(payload['output']).exists():
            raise
        cpu_id = 'kokoro-zh-en-int8' if task == 'voice' else 'opus-zh-en-cpu-int8'
        pack, manifest = community_models.verify_pack(args.pack, cpu_id)
        device = {**device, 'selected': 'cpu', 'fallback_reason': 'cuda_inference_failed',
                  'failed_gpu_worker': error.as_dict()}
        payload = {**payload, 'device': 'cpu', 'cuda_library_directory': None}
        result = community_models.infer(root, pack=str(pack), pack_id=cpu_id, task=task,
                                         payload=payload, dry_run=args.dry_run)
    return result, pack, manifest, device


def command_voice(args):
    if args.action == 'list':
        return material_catalog.voices(language=args.language, query=args.query)
    root, project = load_project(args.project)
    text = read_text(args)
    if len(text) > 3000:
        raise argument_error('单次配音最多 3000 个字符；长文请显式分段', 'text')
    community_audio.finite(args.speed, 'speed', 0.5, 2.)
    if not 1 <= args.threads <= 8:
        raise argument_error('threads 必须为 1–8', 'threads')
    voices = material_catalog.voices()['voices']
    voice = next((v for v in voices if v['id'] == args.voice), None)
    if voice is None:
        raise argument_error('未知音色；先运行 voice list', 'voice')
    aid = material_project.new_asset_id(project, args.asset_id, 'asset_voice')
    output = community_audio.output_path(root, args.output, aid)
    community_device.configure(args, 'voice')
    device = community_device.select(args.device, args.gpu_pack, minimum_mib=3072, device_index=args.device_index)
    if device['selected'] == 'cuda' and args.device_index != 0:
        raise argument_error('此 Kokoro CUDA 适配器当前仅支持 device-index 0', 'device_index')
    pack_id = 'kokoro-zh-en-cuda13' if device['selected'] == 'cuda' else 'kokoro-zh-en-int8'
    pack, manifest = community_models.verify_pack(args.gpu_pack if device['selected'] == 'cuda' else args.pack, pack_id)
    payload = dict(text=text, voice_id=voice['id'], speaker_id=voice['speaker_id'], speed=args.speed,
                   threads=args.threads, output=str(output), device=device['selected'], device_index=args.device_index,
                   cuda_library_directory=community_device.library_directory(args.cuda_library_directory))
    if args.dry_run:
        return community_models.infer(root, pack=str(pack), pack_id=manifest['id'], task='voice', payload=payload, dry_run=True)
    # Check placement before starting inference, using a candidate natural-duration stub.
    material_project.append_audio(root, json.loads(json.dumps(project)),
                                   {'id': aid, 'kind': 'audio', 'probe': {'duration_seconds': 1}}, **placement(args))
    output.parent.mkdir(parents=True, exist_ok=True)
    result, pack, manifest, device = run_inference(args, root, payload, 'voice', pack, manifest, device)
    if result.get('rms', 0) <= 0.0001 or result.get('sample_rate') != 24000:
        raise AppError('VOICE_OUTPUT_INVALID', '实际配音为空、静音或采样率无效', exit_code=6)
    parent = ensure_model_rights(root, pack, manifest, 'kokoro')
    digest = 'sha256:' + sha256_file(output)
    text_sha = sha256_bytes(text.encode('utf-8'))
    evidence = ('assets/community-audio/' + aid + '-SOURCE.txt')
    atomic_write_text(root / evidence, 'Generated local speech\nVoice ' + voice['id'] + '\nText SHA-256 ' + text_sha + '\nText\n' + text + '\nModel ' + parent)
    asset = dict(id=aid, kind='audio', uri=output.relative_to(root).as_posix(), sha256=digest,
                 probe=probe_media(output), rights_ref=aid,
                 source=dict(source_url='local://' + evidence, source_version=manifest['engine']['id'],
                             retrieved_at=now_iso(), original_name=output.name, derived_from=[parent],
                             generation=dict(voice_id=voice['id'], speed=args.speed, text_sha256=text_sha,
                                             model_pack_manifest_sha256=result['pack']['manifest_sha256'])))
    rights = dict(asset_id=aid, kind='audio', sha256=digest, source_url='local://' + evidence,
                  source_version=manifest['engine']['id'], creator='local Kokoro synthesis',
                  license_spdx='LicenseRef-UNVERIFIED', license_url='', attribution='', permitted_uses=['internal'],
                  restrictions=[], evidence=evidence, derived_from=[parent], verification_status='unverified',
                  verified_by='', takedown_status='clear', retrieved_at=now_iso(),
                  notes='Review the input text, pronunciation, voice/output rights and target use; no reference-voice cloning was performed.')
    return {**material_project.commit_asset(root, project, asset, rights, command='voice.synthesize',
                                             report=dict(synthesis=result, text_sha256=text_sha), **placement(args)),
            'synthesis': result, 'voice': voice, 'device': device, 'review_required': True}


def glossary(path: str | None) -> list[dict[str, Any]]:
    if not path:
        return []
    require_local_reference(path, field='glossary')
    file = Path(path).expanduser().resolve()
    if not file.is_file() or file.stat().st_size > 128 * 1024:
        raise argument_error('术语表必须为不超过 128 KiB 的本地 JSON', 'glossary')
    data = json.loads(file.read_text('utf-8-sig'))
    if not isinstance(data, dict) or set(data) != {'entries'} or not isinstance(data['entries'], list) or len(data['entries']) > 100:
        raise argument_error('术语表结构必须为 entries 数组，最多 100 项', 'glossary')
    for row in data['entries']:
        if (not isinstance(row, dict) or set(row) != {'source', 'target', 'variants'}
                or not isinstance(row['variants'], list) or not row['variants']
                or not all(isinstance(t, str) and t.strip() and len(t) <= 200 for t in [row['source'], row['target'], *row['variants']])):
            raise argument_error('每项术语需要 source、target 和非空 variants', 'glossary.entries')
    return data['entries']


def apply_glossary(inputs, outputs, entries):
    edits = []
    for index, (source, target) in enumerate(zip(inputs, outputs)):
        for entry in entries:
            if entry['source'].casefold() not in source.casefold():
                continue
            if entry['target'].casefold() not in target.casefold():
                pattern = '|'.join(re.escape(v) for v in sorted(entry['variants'], key=len, reverse=True))
                target, count = re.subn(pattern, lambda m: entry['target'], target, flags=re.IGNORECASE)
                if not count:
                    raise AppError('GLOSSARY_VARIANT_NOT_FOUND', '译文未包含指定术语译法；需人工复核术语表后重试', exit_code=2,
                                   path='cue_or_paragraph[' + str(index) + ']')
                edits.append(dict(index=index, source=entry['source'], target=entry['target'], replacements=count))
        outputs[index] = target
    return edits


def command_translate(args):
    root, project = load_project(args.project)
    if (args.source_language == 'en') == (args.target_language == 'en'):
        raise argument_error('此方案只支持中英双向；简繁转换在中文输入/输出中显式处理', 'from/to')
    if not 1 <= args.threads <= 8 or not 1 <= args.beam_size <= 8:
        raise argument_error('threads 和 beam-size 必须为 1–8', 'threads/beam_size')
    require_local_reference(args.output, field='output')
    output = Path(args.output)
    output = ensure_inside(root, output if output.is_absolute() else root / output)
    if output.exists() or output.suffix.casefold() != ('.srt' if args.action == 'subtitles' else '.txt'):
        raise argument_error('选择尚不存在的项目内 .srt 或 .txt 输出', 'output')
    license_target = output.with_name(output.name + '.MODEL-LICENSE.txt')
    if license_target.exists():
        raise argument_error('模型许可输出已存在', str(license_target))
    entries = glossary(args.glossary)
    cues = None
    if args.action == 'subtitles':
        require_local_reference(args.input, field='input')
        path = Path(args.input).expanduser().resolve()
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise argument_error('字幕输入必须为不超过 1 MiB 的本地文件', 'input')
        cues = parse_caption_file(path)
        valid = validate_cues(cues, allow_overlap=True)
        if not valid['ok'] or not 1 <= len(cues) <= 1000:
            raise argument_error('字幕需要 1–1000 条有效 cue', 'input')
        texts = [c['text'] for c in cues]
        source_text = path.read_text('utf-8-sig')
    else:
        source_text = read_text(args)
        texts = [line.strip() for line in source_text.splitlines() if line.strip()]
        if not 1 <= len(texts) <= 1000:
            raise argument_error('需要 1–1000 个非空文本段；长文请显式分段', 'input')
    pair = 'en-zh' if args.source_language == 'en' else 'zh-en'
    payload = dict(pair=pair, texts=texts, source_language=args.source_language, target_language=args.target_language,
                   threads=args.threads, beam_size=args.beam_size)
    community_device.configure(args, 'translation')
    device = community_device.select(args.device, args.gpu_pack, minimum_mib=1536, device_index=args.device_index)
    selected_pack = args.gpu_pack if device['selected'] == 'cuda' else args.pack
    pack_id = 'opus-zh-en-cuda12-int8' if device['selected'] == 'cuda' else 'opus-zh-en-cpu-int8'
    payload.update(device=device['selected'], device_index=args.device_index,
                   cuda_library_directory=community_device.library_directory(args.cuda_library_directory))
    pack, manifest = community_models.verify_pack(selected_pack, pack_id)
    result, pack, manifest, device = run_inference(args, root, payload, 'translate', pack, manifest, device)
    if args.dry_run:
        return {**result, 'output': str(output), 'units': len(texts), 'cue_timing_preserved': cues is not None}
    translations = list(result['output'])
    if len(translations) != len(texts):
        raise AppError('TRANSLATION_COUNT_MISMATCH', '翻译条目数不符；未写出字幕', exit_code=6)
    edits = apply_glossary(texts, translations, entries)
    output_cues = None
    if cues is not None:
        output_cues = [{**c, 'text': (c['text'] + '\n' + t if args.mode == 'bilingual' else t)} for c, t in zip(cues, translations)]
        content = cues_to_srt(output_cues, preserve_order=True)
    else:
        content = '\n'.join(translations) + '\n'
    # Copy actual model attribution and legal text into this portable project.
    parent = ensure_model_rights(root, pack, manifest, pair)
    model = manifest['models'][pair]
    license_content = 'Machine translation model\n' + json.dumps(model, ensure_ascii=False, indent=2) + '\n\n' + (pack / model['license_path']).read_text('utf-8-sig')
    # Validate evidence before writing either output. Exclusive creation also
    # preserves a file another process creates while inference is running.
    output.parent.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for destination, text in ((license_target, license_content), (output, content)):
            with destination.open('x', encoding='utf-8', newline='\n') as handle:
                created.append(destination)
                handle.write(text)
    except BaseException:
        for destination in created:
            destination.unlink(missing_ok=True)
        raise
    report = dict(engine=manifest['engine']['id'], device=device, pair=pair, input_sha256=sha256_bytes(source_text.encode('utf-8')),
                  output=str(output), output_sha256='sha256:' + sha256_file(output), input_units=len(texts),
                  source_language=args.source_language, target_language=args.target_language,
                  input=texts, translations=translations, cue_timing_preserved=cues is not None,
                  source_cues=cues, output_cues=output_cues, output_format='srt' if cues is not None else 'text',
                  styles_preserved=False if cues is not None else None,
                  glossary_mode='explicit-post-edit-not-constrained-decoding', glossary_edits=edits,
                  model_rights_ref=parent, license_evidence=str(license_target), inference=result,
                  semantic_human_acceptance=False, network='disabled')
    path = root / 'validation' / (new_id('translation') + '.json')
    atomic_write_json(path, report)
    return {**report, 'report': str(path), 'review_required': True}


def command(args, envelope):
    key = (args.domain, args.action)
    if args.domain == 'gpu':
        data = community_device.inspect()
    elif args.domain == 'materials':
        if args.action == 'list':
            data = material_catalog.search(query=args.query, kind=args.kind, category=args.category, limit=args.limit, offset=args.offset)
        elif args.action == 'inspect':
            row, col = material_catalog.find(args.id)
            data = dict(record=row, collection=col, network='disabled')
        elif args.action == 'verify':
            ids = [args.id] if args.id else [r['id'] for r in material_catalog.catalog()['records']]
            results = [material_catalog.verify(ident) for ident in ids]
            data = dict(verified=len(results), ids=ids, network='disabled')
        else:
            root, project = load_project(args.project)
            data = material_project.import_material(root, project, args.id, asset_id=args.asset_id, dry_run=args.dry_run, **placement(args))
    elif args.domain == 'voice':
        data = command_voice(args)
    elif args.domain == 'translate':
        data = command_translate(args)
    elif args.domain == 'model-pack':
        if args.action == 'list':
            data = {**community_models.pack_catalog(), 'weights_in_base_package': False, 'runtime_downloads': False}
        else:
            path, manifest = community_models.verify_pack(args.pack, args.id)
            data = dict(id=args.id, path=str(path), verified=True, files=len(manifest['files']),
                        manifest_sha256=sha256_file(path / 'manifest.json'), network='disabled')
    elif args.domain == 'music' and args.action in ['inspect-score', 'compose', 'effect']:
        from . import music_score
        if args.action == 'effect':
            payload = music_score.effect_score(args.preset, args.duration_seconds, args.seed, args.pitch)
        else:
            require_local_reference(args.input, field='input')
            path = Path(args.input).expanduser().resolve()
            if not path.is_file() or path.stat().st_size > 1024*1024:
                raise argument_error('Score requires a local UTF-8 JSON file of at most1MiB', 'input')
            try:
                payload = json.loads(path.read_text('utf-8-sig'))
            except (ValueError, UnicodeError) as error:
                raise argument_error('Invalid UTF-8 score JSON', 'input') from error
        if args.action == 'inspect-score':
            canonical, plan = music_score.prepare(payload)
            data = dict(engine=music_score.ENGINE, canonical_score=canonical, frames=plan['frames'],
                        duration_seconds=plan['frames']/music_score.RATE, notes=plan['notes'],
                        device=dict(selected='cpu', backend='numpy-analytical'),
                        neural_model=False, network='disabled')
        else:
            root, project = load_project(args.project)
            data = music_score.generate(root, project, payload, new_id=args.new_asset_id,
                                        stems=args.stems, placement=placement(args), dry_run=args.dry_run,
                                        command='music.'+args.action)
    elif args.domain == 'music' and args.action == 'repair-loop':
        from . import music_loop
        if args.input:
            if args.asset_id is not None or args.crossfade_ms is not None or args.curve is not None:
                raise argument_error('Recipe input cannot be combined with source/processing options','input')
            require_local_reference(args.input,field='input')
            path=Path(args.input).expanduser().resolve()
            if not path.is_file() or path.stat().st_size>65536:
                raise argument_error('Loop recipe requires local UTF-8 JSON <=64KiB','input')
            try:
                options=music_loop.read_recipe(json.loads(path.read_text('utf-8-sig')))
            except (ValueError,UnicodeError) as error:
                raise argument_error('Invalid loop recipe JSON','input') from error
        else:
            if not args.asset_id:raise argument_error('Source asset or recipe is required','asset_id/input')
            options=dict(asset_id=args.asset_id,crossfade_ms=100. if args.crossfade_ms is None else args.crossfade_ms,
                         curve=args.curve or 'raised-cosine')
        root,project=load_project(args.project)
        data=music_loop.repair(root,project,**options,new_id=args.new_asset_id,placement=placement(args),dry_run=args.dry_run)
    else:
        root, project = load_project(args.project)
        common = dict(output=args.output, new_id=args.new_asset_id, placement=placement(args), dry_run=args.dry_run)
        if args.action == 'prepare':
            data = community_audio.prepare(root, project, asset_id=args.asset_id, duration=args.duration_seconds,
                                             offset=args.offset_seconds, loop=args.loop, gain_db=args.gain_db,
                                             fade_in=args.fade_in_seconds, fade_out=args.fade_out_seconds, **common)
        else:
            data = community_audio.mix(root, project, voice_asset_id=args.voice_asset_id, music_asset_id=args.music_asset_id,
                                         duration=args.duration_seconds, voice_gain_db=args.voice_gain_db, music_gain_db=args.music_gain_db,
                                         duck=args.duck, threshold=args.duck_threshold, ratio=args.duck_ratio,
                                         attack=args.duck_attack_ms, release=args.duck_release_ms, loop_music=args.loop_music, **common)
    warnings = ([{'code': 'COMMUNITY_OUTPUT_REVIEW_REQUIRED', 'message': '先试听、校对文本与模型输出，再确认项目用途和发布权利'}]
                if data.get('review_required') else [])
    if data.get('device', {}).get('fallback_reason'):
        warnings.append({'code': 'GPU_CPU_FALLBACK', 'message': '实际使用 CPU；原因见 data.device.fallback_reason'})
    return envelope('.'.join(key), args, data=data, status='planned' if args.dry_run else 'succeeded',
                    warnings=warnings, operation_id=data.get('operation_id'))


COMMAND_KEYS = [('materials', a) for a in ('list', 'inspect', 'verify', 'ingest')] + [
    ('voice', 'list'), ('voice', 'synthesize'), ('translate', 'text'), ('translate', 'subtitles'),
    ('model-pack', 'list'), ('model-pack', 'verify'), ('music', 'prepare'), ('music', 'mix'),
    ('music', 'inspect-score'), ('music', 'compose'), ('music', 'effect'), ('music', 'repair-loop'), ('gpu', 'inspect')]
