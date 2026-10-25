"""Translate, synthesize and commit an editable subtitle dubbing batch atomically."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import time
import wave
from types import SimpleNamespace

from . import community_device, community_models, dubbing, material_catalog
from .captions import cues_to_srt
from .community_cli import apply_glossary, glossary
from .errors import AppError, argument_error
from .job_workspaces import managed_workspace
from .media import probe_media
from .policy import require_local_reference
from .project import TICKS_PER_SECOND, asset_map, create_snapshot, find_sequence, find_track, load_project, save_project
from .rights import add_record, load_ledger, save_ledger
from .utils import assert_id, atomic_write_json, new_id, now_iso, sha256_file
from .validator import validate_project

FORMAT = 'agent-subtitle-dubbing-v1'


def add_parser(subs, leaf):
    domain = subs.add_parser('dub', help='字幕翻译、完整分段配音与可编辑音轨联合处理')
    actions = domain.add_subparsers(dest='action', required=True)
    parser = leaf(actions.add_parser('subtitles', help='保留源文/译文/配音，以实际 WAV 样本数检查时窗'))
    parser.add_argument('--project', required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--from', dest='source_language', choices=['en','zh-Hans','zh-Hant'], required=True)
    parser.add_argument('--to', dest='target_language', choices=['en','zh-Hans','zh-Hant'], required=True)
    parser.add_argument('--id', default=None)
    parser.add_argument('--voice', default=None)
    parser.add_argument('--voice-map', default=None, help='本地 JSON: {"cues":{"原字幕编号":"音色 ID"}}；不自动识别说话人')
    parser.add_argument('--speed', type=float, default=1.)
    parser.add_argument('--fit', choices=['reject','speed'], default='reject')
    parser.add_argument('--max-speed', type=float, default=1.5)
    parser.add_argument('--overlap-policy', choices=['reject','mix'], default='reject')
    parser.add_argument('--subtitle-mode', choices=['translation','bilingual'], default='bilingual')
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--beam-size', type=int, default=4)
    parser.add_argument('--glossary', default=None)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--sequence-id', default=None)
    parser.add_argument('--audio-track-id', default=None)
    parser.add_argument('--subtitle-track-id', default=None)
    parser.add_argument('--font-asset-id', default=None)
    parser.add_argument('--timeline-start-tick', type=int, default=0)
    parser.add_argument('--device', choices=['auto','cpu','cuda'], default='auto')
    parser.add_argument('--device-index', type=int, default=0)
    for task in ('voice','translation'):
        parser.add_argument('--'+task+'-device', choices=['auto','cpu','cuda'], default=None)
        parser.add_argument('--'+task+'-pack', default=None)
        parser.add_argument('--'+task+'-gpu-pack', default=None)
        parser.add_argument('--'+task+'-cuda-library-directory', default=None)
    parser.add_argument('--timeout-seconds', type=float, default=3600.)
    parser.add_argument('--cancel-file', default=None)


def local_file(value, *, maximum, field):
    require_local_reference(value, field=field)
    path = Path(value).expanduser().resolve()
    if not path.is_file() or path.stat().st_size > maximum:
        raise argument_error('本地文件不存在或超过字节预算', field)
    return path


def checkpoint(deadline, cancel):
    if cancel is not None and cancel.exists():
        raise AppError('CANCELLED', '字幕配音任务已取消', exit_code=8, path=str(cancel))
    remaining = deadline-time.monotonic()
    if remaining <= 0:
        raise AppError('PROCESS_TIMEOUT', '字幕配音联合任务总超时', exit_code=6)
    return remaining


def model_context(args, task):
    config = SimpleNamespace(pack=getattr(args, task+'_pack'), gpu_pack=getattr(args, task+'_gpu_pack'),
        cuda_library_directory=getattr(args, task+'_cuda_library_directory'),
        device=getattr(args, task+'_device') or args.device, device_index=args.device_index)
    community_device.configure(config, task)
    selected = community_device.select(config.device, config.gpu_pack,
        minimum_mib=3072 if task=='voice' else 1536, device_index=args.device_index)
    if task=='voice' and selected['selected']=='cuda' and args.device_index != 0:
        raise argument_error('Kokoro CUDA 当前仅支持 device-index 0', 'device_index')
    pack_id = (('kokoro-zh-en-cuda13' if selected['selected']=='cuda' else 'kokoro-zh-en-int8') if task=='voice'
        else ('opus-zh-en-cuda12-int8' if selected['selected']=='cuda' else 'opus-zh-en-cpu-int8'))
    pack, manifest = community_models.verify_pack(config.gpu_pack if selected['selected']=='cuda' else config.pack, pack_id)
    library = community_device.library_directory(config.cuda_library_directory)
    return dict(config=config, device=selected, pack=pack, manifest=manifest, library=library)


def run_model(root, job, context, task, payload, deadline, cancel):
    attempts = []
    for attempt in range(2):
        selected = context['device']['selected']
        directory = job.path / (task+'-'+str(attempt+1)+'-'+selected)
        directory.mkdir()
        request = dict(payload, device=selected, device_index=context['config'].device_index,
            cuda_library_directory=context['library'] if selected=='cuda' else None)
        if task=='voice':
            request['segments'] = [dict(spec, output_directory=str(directory / ('cue-'+str(spec['cue_index']))))
                for spec in payload['segments']]
        try:
            result = community_models.infer(directory, pack=str(context['pack']), pack_id=context['manifest']['id'],
                task=task, payload=request, timeout=checkpoint(deadline,cancel), cancel_file=cancel)
        except AppError as error:
            attempts.append(dict(provider=selected, error=error.as_dict(), request_payload=request,
                traces=[dict(path=str(path.relative_to(job.path)), text=path.read_text('utf-8',errors='replace'))
                    for path in sorted((directory/'validation').glob('*')) if path.is_file()]))
            if context['config'].device!='auto' or selected!='cuda' or error.code!='COMMUNITY_MODEL_FAILED' or attempt:
                raise
            # A fresh directory is essential if CUDA wrote part of a batch before failing.
            cpu_id = 'kokoro-zh-en-int8' if task=='voice' else 'opus-zh-en-cpu-int8'
            pack, manifest = community_models.verify_pack(context['config'].pack,cpu_id)
            context.update(pack=pack, manifest=manifest, device=dict(context['device'], selected='cpu',
                fallback_reason='cuda_inference_failed', failed_gpu_worker=error.as_dict()))
            continue
        checkpoint(deadline,cancel)
        if result.get('provider') != selected or result.get('network') != 'disabled':
            raise AppError('DUBBING_MODEL_RESPONSE_INVALID','模型设备或离线响应不符',exit_code=6)
        attempts.append(dict(provider=selected, result=result,
            request=json.loads(Path(result['request']).read_text('utf-8')),
            raw_response=json.loads(Path(result['response']).read_text('utf-8')),
            worker_log=Path(result['worker_log']).read_text('utf-8')))
        return result, attempts
    raise RuntimeError('Unreachable model retry state')


def track_plan(root, project, args, cues):
    tps = int(project.get('settings',{}).get('timebase',{}).get('ticks_per_second',TICKS_PER_SECOND))
    if tps%1000 or args.timeline_start_tick<0 or args.timeline_start_tick+max(c['end_ms'] for c in cues)*tps//1000 >= 2**63:
        raise argument_error('毫秒字幕需 timebase 可整除 1000，且偏移在非负 int64 范围', 'timeline_start_tick/timebase')
    audio = subtitle = sequence = None
    if args.apply:
        if not args.audio_track_id or not args.subtitle_track_id or not args.font_asset_id:
            raise argument_error('--apply 需要 audio-track-id、subtitle-track-id 和已导入 font-asset-id', 'apply')
        sequence = find_sequence(project,args.sequence_id)
        audio, subtitle = find_track(sequence,args.audio_track_id,None), find_track(sequence,args.subtitle_track_id,None)
        for track,kind in ((audio,'audio'),(subtitle,'subtitle')):
            if track.get('kind')!=kind or track.get('locked') or track.get('muted'):
                raise argument_error('目标轨道类型错误、锁定或静音',kind+'_track_id')
            if args.overlap_policy=='mix' and track.get('overlap_policy')!='allow':
                raise argument_error('mix 需两个目标轨道显式 overlap_policy=allow', 'overlap_policy')
            for cue in cues:
                start = args.timeline_start_tick+cue['start_ms']*tps//1000
                end = args.timeline_start_tick+cue['end_ms']*tps//1000
                if any(max(start,int(c.get('timeline_start_tick',0))) < min(end,int(c.get('timeline_start_tick',0))+int(c.get('duration_tick',0))) for c in track.get('clips',[])):
                    raise argument_error('目标时窗与既有片段重叠；请使用空白范围或其他轨道',kind+'_track_id')
        font = asset_map(project).get(args.font_asset_id)
        if not font or font.get('kind')!='font' or not (root/font['uri']).is_file():
            raise argument_error('font-asset-id 必须为实际存在的已登记字体','font_asset_id')
    return tps,sequence,audio,subtitle


def validate_batch(job, result, specs, args):
    rows = result.get('segments')
    if (not isinstance(rows,list) or not 1<=len(rows)<=len(specs) or result.get('model_initializations')!=1
            or result.get('processed_cues')!=len(rows) or result.get('requested_cues')!=len(specs)):
        raise ValueError('Invalid batch count or initialization count')
    checked = []
    for row,spec in zip(rows,specs):
        if any(row.get(k)!=spec[k] for k in ('cue_index','voice_id','speaker_id','slot_samples')):
            raise ValueError('Cue/voice/window response mismatch')
        attempts = row.get('attempts')
        if not isinstance(attempts,list) or not 1<=len(attempts)<=dubbing.MAX_ATTEMPTS or row.get('final_attempt')!=len(attempts)-1:
            raise ValueError('Invalid attempt list')
        speed = args.speed
        for index,attempt in enumerate(attempts):
            path = Path(attempt['output'])
            if not path.is_absolute() or not path.resolve().is_relative_to(job.path) or path.is_symlink() or not path.is_file():
                raise ValueError('Voice output escaped its job')
            measured = dubbing.inspect_wave(path)
            if attempt.get('samples')!=measured['samples'] or abs(attempt.get('speed',0)-speed)>1e-9:
                raise ValueError('WAV samples or speed sequence disagree with response')
            if index and (args.fit!='speed' or attempts[index-1]['samples']<=spec['slot_samples']):
                raise ValueError('Unexpected retry after a fitting utterance')
            if index<len(attempts)-1 and speed>=args.max_speed:
                raise ValueError('Retry exceeds the configured speed limit')
            attempt.update(measured,sha256='sha256:'+sha256_file(path))
            speed = dubbing.next_speed(speed,measured['samples'],spec['slot_samples'],args.max_speed)
        fit = attempts[-1]['samples']<=spec['slot_samples']
        if row.get('fit_status')!=('fits' if fit else 'overflow'):
            raise ValueError('Worker fit status disagrees with actual WAV')
        checked.append(row)
    fits = len(checked)==len(specs) and all(r['fit_status']=='fits' for r in checked)
    if result.get('total_generations') != sum(len(row['attempts']) for row in checked):
        raise ValueError('Generation count is inconsistent')
    if result.get('fit_status')!=('fits' if fits else 'overflow'):
        raise ValueError('Batch fit status is inconsistent')
    return checked,fits


def execute(args):
    root, original = load_project(args.project)
    deadline = time.monotonic()+args.timeout_seconds
    if not math.isfinite(args.timeout_seconds) or not 0<args.timeout_seconds<=604800:
        raise argument_error('timeout-seconds 必须为 0..604800 的正数','timeout_seconds')
    cancel = None
    if args.cancel_file:
        require_local_reference(args.cancel_file,field='cancel_file')
        cancel = Path(args.cancel_file)
        cancel = (cancel if cancel.is_absolute() else root/cancel).resolve()
    checkpoint(deadline,cancel)
    preserve_text = args.source_language == args.target_language
    if not preserve_text and (args.source_language=='en') == (args.target_language=='en'):
        raise argument_error('联合流程支持中英双向或同语种保留原文；简繁转换请先显式处理','from/to')
    if preserve_text and args.glossary:
        raise argument_error('同语种保留原文不会应用译后术语替换；请先显式校正文案','glossary')
    if not 1<=args.threads<=8 or not 1<=args.beam_size<=8:
        raise argument_error('threads/beam-size 必须为 1–8','threads/beam_size')
    if not all(math.isfinite(v) and .5<=v<=2 for v in (args.speed,args.max_speed)) or (args.fit=='speed' and args.max_speed<args.speed):
        raise argument_error('语速需为 0.5–2；加速上限不得低于基础语速','speed/max_speed')
    source = local_file(args.input,maximum=1024*1024,field='input')
    source_bytes = source.read_bytes()
    if len(source_bytes)>1024*1024:
        raise argument_error('字幕读取期间超过 1 MiB 预算','input')
    try:
        cues = dubbing.parse_srt(source_bytes.decode('utf-8-sig'))
    except (ValueError,UnicodeError) as error:
        raise argument_error(str(error),'input') from error
    ordered = sorted(cues,key=lambda cue:cue['start_ms'])
    if args.overlap_policy=='reject' and any(a['end_ms']>b['start_ms'] for a,b in zip(ordered,ordered[1:])):
        raise argument_error('字幕时窗重叠；需明确 mix 和允许重叠的目标轨道','overlap_policy')
    candidate = copy.deepcopy(original)
    tps,sequence,audio_track,subtitle_track = track_plan(root,candidate,args,cues)
    voices = {v['id']:v for v in material_catalog.voices()['voices']}
    default = args.voice or ('af_maple' if args.target_language=='en' else 'zf_001')
    mapping = {}
    if args.voice_map:
        try:
            data = json.loads(local_file(args.voice_map,maximum=128*1024,field='voice_map').read_text('utf-8-sig'))
        except (ValueError,UnicodeError) as error:
            raise argument_error('voice-map 必须为有效 UTF-8 JSON','voice_map') from error
        if not isinstance(data,dict) or set(data)!={'cues'} or not isinstance(data['cues'],dict):
            raise argument_error('voice-map 格式必须为 cues 对象','voice_map')
        mapping = data['cues']
        if not set(mapping).issubset({cue['source_id'] for cue in cues}):
            raise argument_error('voice-map 含不存在的原字幕编号','voice_map')
    for cue in cues:
        ident = mapping.get(cue['source_id'],default)
        if not isinstance(ident,str) or ident not in voices or voices[ident]['language']!=('en' if args.target_language=='en' else 'zh'):
            raise argument_error('音色不存在或与目标语言不匹配','voice')
        cue['voice'] = voices[ident]
    terms = glossary(args.glossary)
    contexts = {task:model_context(args,task) for task in (('voice',) if preserve_text else ('translation','voice'))}
    checkpoint(deadline,cancel)
    ident = args.id or new_id('dub')
    assert_id(ident,'id')
    destination = root/'assets/derived/dubbing'/ident
    if destination.exists():
        raise argument_error('配音输出 ID 已存在；不覆盖既有输出','id')
    plan = dict(format=FORMAT,cues=cues,source=str(source),source_sha256='sha256:'+hashlib.sha256(source_bytes).hexdigest(),
        output_directory=str(destination),fit=args.fit,base_speed=args.speed,max_speed=args.max_speed,
        overlap_policy=args.overlap_policy,subtitle_mode=args.subtitle_mode,timeline_start_tick=args.timeline_start_tick,
        devices={task:context['device'] for task,context in contexts.items()},applied=args.apply,
        actual_audio_duration_known=False,model_inference=False,review_required=True,
        text_mode='preserve-original' if preserve_text else 'translate')
    if args.dry_run:
        return plan
    operation = new_id('op_dub')
    with managed_workspace(root,'subtitle-dubbing') as job:
        stage = job.path/'deliver'
        stage.mkdir()
        (stage/'source.srt').write_bytes(source_bytes)
        pair = 'en-zh' if args.source_language=='en' else 'zh-en'
        if preserve_text:
            texts,translation_attempts = [c['text'] for c in cues],[]
        else:
            translated,translation_attempts = run_model(root,job,contexts['translation'],'translate',dict(pair=pair,
                texts=[c['text'] for c in cues],source_language=args.source_language,target_language=args.target_language,
                threads=args.threads,beam_size=args.beam_size),deadline,cancel)
            texts = translated.get('output')
        if not isinstance(texts,list) or len(texts)!=len(cues) or not all(isinstance(t,str) and t.strip() and len(t)<=3000 for t in texts):
            raise AppError('DUBBING_TRANSLATION_INVALID','翻译数量/文本无效或单段过长',exit_code=6)
        edits = apply_glossary([c['text'] for c in cues],texts,terms)
        if any(requires_plain_text(t) for t in texts):
            raise AppError('DUBBING_TRANSLATION_INVALID','译文包含字幕格式/控制指令，需先人工修正',exit_code=6)
        specs = [dict(cue_index=c['index'],voice_id=c['voice']['id'],speaker_id=c['voice']['speaker_id'],
            text=text,slot_samples=c['slot_samples']) for c,text in zip(cues,texts)]
        spoken,voice_attempts = run_model(root,job,contexts['voice'],'voice',dict(segments=specs,speed=args.speed,
            max_speed=args.max_speed,fit=args.fit,threads=args.threads),deadline,cancel)
        try:
            measured,fits = validate_batch(job,spoken,specs,args)
        except (ValueError,KeyError,TypeError,OSError,wave.Error) as error:
            raise AppError('DUBBING_VOICE_INVALID','配音响应与实际 WAV 检查失败',exit_code=6,cause=str(error)) from error
        if not fits:
            failure = dict(format=FORMAT,status='overflow',plan=plan,translations=texts,measured=measured,
                translation_attempts=translation_attempts,voice_attempts=voice_attempts)
            atomic_write_json(job.path/'failure.json',failure)
            job.hold_for_review('DUBBING_CUE_OVERFLOW; original speech and attempts retained; explicit recover can clean')
            raise AppError('DUBBING_CUE_OVERFLOW','完整配音超出字幕时窗；工程未提交，原始声音与报告保留供复核',
                exit_code=2,path=str(job.path/'failure.json'),operation_id=operation)
        report = dict(format=FORMAT,operation_id=operation,source_language=args.source_language,target_language=args.target_language,
            plan=plan,glossary_edits=edits,translation_attempts=translation_attempts,voice_attempts=voice_attempts,
            timing_scope='cue_windows_not_phonetic_alignment_or_lip_sync',human_semantic_acceptance=False,
            human_listening=False,truncation=False,cues=[],text_mode=plan['text_mode'])
        translated_cues = [dict(c,text=t) for c,t in zip(cues,texts)]
        bilingual_cues = [dict(c,text=t if preserve_text else c['text']+'\n'+t) for c,t in zip(cues,texts)]
        (stage/'translated.srt').write_text(cues_to_srt(translated_cues,preserve_order=True),encoding='utf-8')
        (stage/'bilingual.srt').write_text(cues_to_srt(bilingual_cues,preserve_order=True),encoding='utf-8')
        ledger = load_ledger(root)
        assets,clips,publish = [],[],[]
        evidence = (destination/'report.json').relative_to(root).as_posix()

        def register(path,kind,parents,probe=None,model=None):
            target = destination/path.relative_to(stage)
            aid = new_id('dub_'+kind)
            digest = 'sha256:'+sha256_file(path)
            asset = dict(id=aid,kind=kind,uri=target.relative_to(root).as_posix(),sha256=digest,rights_ref=aid,
                probe=probe or {},source=dict(source_url='local://'+evidence,original_name=path.name,
                    retrieved_at=now_iso(),source_version=FORMAT,derived_from=parents))
            record = dict(asset_id=aid,kind=kind,sha256=digest,source_url='local://'+evidence,
                source_version=FORMAT,creator='local subtitle dubbing',license_spdx='LicenseRef-UNVERIFIED',
                license_url='',attribution='',permitted_uses=['internal'],restrictions=[],evidence=evidence,
                derived_from=parents,verification_status='unverified',verified_by='',takedown_status='clear',
                retrieved_at=now_iso(),notes='Review source/translation, complete speech, model/output rights and intended use.')
            candidate.setdefault('assets',[]).append(asset)
            add_record(ledger,record)
            assets.append(asset)
            publish.append((path,target))
            return asset

        model_refs = {}
        for task,context in contexts.items():
            mid = 'kokoro' if task=='voice' else pair
            model = context['manifest']['models'][mid]
            name = task+'-MODEL-SOURCE.txt'
            content = json.dumps(model,ensure_ascii=False,indent=2)+'\n\n'+(context['pack']/model['license_path']).read_text('utf-8-sig')
            (stage/name).write_text(content,encoding='utf-8')
            target = destination/name
            ref = new_id('dub_model')
            model_evidence = target.relative_to(root).as_posix()
            add_record(ledger,dict(asset_id=ref,kind='model',sha256='sha256:'+model['sha256'],
                source_url='local://'+model_evidence,source_version=context['manifest']['id'],creator=model['creator'],
                license_spdx=model['license'],license_url=model_evidence,evidence=model_evidence,
                attribution=model['creator']+'; '+mid,permitted_uses=['internal','commercial_ad'],
                restrictions=model.get('obligations',[]),verification_status='verified',verified_by='pinned-offline-model-pack',
                takedown_status='clear',retrieved_at=now_iso(),notes='Model permission does not license source or generated content.'))
            publish.append((stage/name,target))
            model_refs[task] = ref
        source_asset = register(stage/'source.srt','subtitle',[],dict(duration_tick=max(c['end_ms'] for c in cues)*tps//1000,subtitle_cues=len(cues)))
        translation_asset = register(stage/'translated.srt','subtitle',[source_asset['id']]+([model_refs['translation']] if 'translation' in model_refs else []),source_asset['probe'])
        bilingual_asset = register(stage/'bilingual.srt','subtitle',[source_asset['id'],translation_asset['id']],source_asset['probe'])
        for cue,text,row in zip(cues,texts,measured):
            registered = []
            for index,attempt in enumerate(row['attempts']):
                checkpoint(deadline,cancel)
                raw = Path(attempt['output'])
                relative = Path('audio')/('cue-'+str(cue['index']))/raw.name
                target = stage/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                raw.rename(target)
                probe = probe_media(target)
                duration = (attempt['samples']*tps+dubbing.SAMPLE_RATE-1)//dubbing.SAMPLE_RATE
                probe['duration_tick'] = duration
                asset = register(target,'audio',[translation_asset['id'],model_refs['voice']],probe)
                registered.append(asset)
                attempt.update(output=asset['uri'],asset_id=asset['id'],duration_tick=duration)
            final = registered[-1]
            start = args.timeline_start_tick+cue['start_ms']*tps//1000
            if args.apply:
                duration = final['probe']['duration_tick']
                audio_clip = dict(id=new_id('dub_audio'),asset_id=final['id'],enabled=True,
                    timeline_start_tick=start,source_in_tick=0,source_out_tick=duration,duration_tick=duration)
                audio_track.setdefault('clips',[]).append(audio_clip)
                shown = bilingual_cues[cue['index']-1]['text'] if args.subtitle_mode=='bilingual' else text
                sub_duration = (cue['end_ms']-cue['start_ms'])*tps//1000
                display_asset = bilingual_asset if args.subtitle_mode=='bilingual' else translation_asset
                subtitle_clip = dict(id=new_id('dub_caption'),timeline_start_tick=start,duration_tick=sub_duration,
                    source_in_tick=0,source_out_tick=sub_duration,generator={'type':'text'},
                    subtitle=dict(text=shown,style=dict(fontsize=40,fontcolor='white',borderw=2,bordercolor='black',
                        x='(w-text_w)/2',y='h-text_h-40',font_asset_id=args.font_asset_id)),
                    rights_dependencies=[dict(rights_ref=display_asset['rights_ref'],sha256=display_asset['sha256'])])
                subtitle_track.setdefault('clips',[]).append(subtitle_clip)
                clips.extend([audio_clip,subtitle_clip])
            report['cues'].append(dict(index=cue['index'],source_id=cue['source_id'],source_text=cue['text'],
                translation=text,start_ms=cue['start_ms'],end_ms=cue['end_ms'],voice=cue['voice'],
                attempts=row['attempts'],final_asset_id=final['id'],final_samples=row['attempts'][-1]['samples'],
                slot_samples=cue['slot_samples'],fit_status='fits'))
        if sequence:
            sequence['duration_tick'] = max(int(sequence.get('duration_tick',0)),args.timeline_start_tick+max(c['end_ms'] for c in cues)*tps//1000)
        report.update(model_rights_refs=model_refs,model_inference=True,actual_audio_duration_known=True,
            output_assets=[a['id'] for a in assets],applied=args.apply,clip_ids=[c['id'] for c in clips])
        atomic_write_json(stage/'report.json',report)
        report_asset = register(stage/'report.json','generated',[a['id'] for a in assets])
        checkpoint(deadline,cancel)
        snapshot = create_snapshot(root,original,label='before-dub-subtitles')
        for path,target in publish:
            checkpoint(deadline,cancel)
            job.publish(path,target)
        validation = validate_project(root,candidate,rights_ledger=ledger,strict_rights=False)
        if not validation['ok']:
            raise AppError('DUBBING_PROJECT_INVALID','配音联合工程校验失败',exit_code=2,cause=json.dumps(validation['errors'],ensure_ascii=False))
        checkpoint(deadline,cancel)
        candidate.setdefault('provenance',{}).setdefault('change_log',[]).append(dict(operation_id=operation,
            command='dub.subtitles',report=report_asset['uri'],before_snapshot_id=snapshot['snapshot_id'],at=now_iso()))
        save_ledger(root,ledger)
        save_project(root,candidate)
        atomic_write_json(root/'operations'/(operation+'.json'),dict(operation_id=operation,command='dub.subtitles',status='succeeded',
            report=report_asset['uri'],asset_ids=[a['id'] for a in assets],clip_ids=[c['id'] for c in clips],before_snapshot_id=snapshot['snapshot_id']))
        return dict(operation_id=operation,report=str(root/report_asset['uri']),assets=assets,clips=clips,
            devices={task:context['device'] for task,context in contexts.items()},review_required=True,
            cue_count=len(cues),model_initializations=spoken['model_initializations'],total_generations=spoken['total_generations'],
            fit_status='fits',truncation=False,validation=validation,before_snapshot=snapshot)


def requires_plain_text(text):
    import re
    return bool(re.search(r'<[^>]*>|\{\\|-->|\n\s*\n',text) or any(ord(c)<32 and c not in '\n\t' for c in text))


def command(args,envelope):
    try:
        data = execute(args)
    except (AppError,ValueError,TypeError,KeyError,StopIteration,OSError) as caught:
        error = caught if isinstance(caught,AppError) else AppError(
            'DUBBING_IO_FAILED' if isinstance(caught,OSError) else 'DUBBING_RESPONSE_INVALID',
            '字幕配音写入失败' if isinstance(caught,OSError) else '字幕配音响应或模型元数据无效',
            exit_code=9,cause=str(caught))
        root = Path(args.project).expanduser().resolve()
        if not args.dry_run and (root/'project.json').is_file():
            operation = error.operation_id or new_id('op_dub')
            error.operation_id = operation
            try:
                atomic_write_json(root/'operations'/(operation+'.json'),dict(operation_id=operation,
                    command='dub.subtitles',status='failed',error=error.as_dict(),created_at=now_iso()))
            except OSError as record_error:
                error.diagnostics = dict(failure_record_write_failed=str(record_error))
        raise error
    warnings = [dict(code='DUBBING_REVIEW_REQUIRED',message='校对源文/译文并试听完整配音；cue 级安排不代表字词精标或口型完成')]
    for task,device in data['devices'].items():
        if device.get('fallback_reason'):
            warnings.append(dict(code='GPU_CPU_FALLBACK',task=task,message=device['fallback_reason']))
    return envelope('dub.subtitles',args,data=data,status='planned' if args.dry_run else 'succeeded',warnings=warnings,
        operation_id=data.get('operation_id'))
