"""CLI integration for reviewed ad storyboards and exact scoped revisions."""
from pathlib import Path

from . import ad_storyboard as storyboard
from .artifact_locks import artifact_entry, verification_scope, verification_summary
from .errors import AppError
from .execution_control import operation_budget, checkpoint
from .policy import resolve_local_path
from .project import load_project, create_snapshot, save_project, asset_map
from .text_layout import build_text_layout
from .utils import atomic_write_json, load_json, new_id, now_iso
from .validator import validate_project


ACTIONS = ('storyboard', 'build', 'revise', 'select')


def add_parsers(actions, leaf):
    for action in ACTIONS:
        parser = leaf(actions.add_parser(action, help={
            'storyboard': '将已确认文案/素材规划为可编辑的多画幅广告',
            'build': '核对计划、工程和实际素材后原子提交广告分镜',
            'revise': '按稳定变体/镜头 ID 规划局部返工，保留其他编辑',
            'select': '用真实校准语义检索联合选材，生成可编辑广告计划'}[action]))
        parser.add_argument('--project', required=True)
        parser.add_argument('--input', required=True)
        if action != 'build':
            parser.add_argument('--output', required=True, help='新的项目内 validation/*.json 计划')
        parser.add_argument('--timeout-seconds', type=float, default=600)
        parser.add_argument('--cancel-file')
        if action == 'select':
            parser.add_argument('--index-id', required=True)
            parser.add_argument('--calibration-id', required=True)
            parser.add_argument('--device', choices=('auto', 'cpu', 'cuda'), default='auto')
            parser.add_argument('--device-index', type=int, default=0)
            parser.add_argument('--batch-size', type=int, default=8)
            parser.add_argument('--limit', type=int, choices=range(1, 21), default=10)
            parser.add_argument('--kind', choices=('image', 'video'))


def _check_assets(root, project, plan):
    assets = asset_map(project)
    paths = {}
    for pin in plan['asset_pins']:
        checkpoint()
        asset = assets[pin['asset_id']]
        path = resolve_local_path(root, asset['uri'], field='asset.uri')
        entry = artifact_entry(path, 'ad-storyboard-input')
        if entry['sha256'] != pin['sha256']:
            raise AppError('AD_ASSET_CHANGED', '实际素材已偏离工程和计划的内容摘要', exit_code=2, path=str(path))
        paths[asset['id']] = path
    return paths


def _check_layout(plan, paths):
    from PIL import ImageFont
    fonts = {}
    for sequence in plan['sequences']:
        canvas = sequence['canvas']
        for track in sequence['tracks']:
            if track['kind'] != 'subtitle':
                continue
            for clip in track['clips']:
                checkpoint()
                subtitle = clip.get('subtitle', {})
                style = subtitle.get('style', {})
                if clip.get('ad_storyboard', {}).get('role') != 'caption':
                    continue
                key = (style['font_asset_id'], style['fontsize'])
                if key not in fonts:
                    fonts[key] = ImageFont.truetype(str(paths[key[0]]), key[1])
                layout = build_text_layout(subtitle['text'], style, fonts[key], key[1])
                # The generated anchor is bottom-aligned with an explicit inset.
                # Keep user-authored expressions on revisions for render review.
                y = style.get('y', '')
                margin = int(y.rsplit('-', 1)[1]) if isinstance(y, str) and y.startswith('h-text_h-') and y.rsplit('-', 1)[1].isdigit() else 0
                border = style.get('borderw', 0)
                if layout.width + 2 * border > canvas['width'] or layout.height + margin + 2 * border > canvas['height']:
                    raise AppError('AD_CAPTION_OVERFLOW', '文案在目标画幅中超出安全范围；请明确缩短或调整字体', exit_code=2,
                                   path=clip['id'], diagnostics={'width': layout.width, 'height': layout.height, 'canvas': canvas})


def command(args, envelope, operation):
    root, project = load_project(args.project)
    input_path = resolve_local_path(root, args.input, field='input')
    with verification_scope(), operation_budget(args.timeout_seconds, args.cancel_file, root=root):
        input_pin = artifact_entry(input_path, 'ad-selection-brief') if args.action == 'select' else None
        payload = load_json(input_path)
        initial = validate_project(root, project, strict_rights=False)
        if not initial['ok']:
            raise AppError('PROJECT_INVALID', '广告规划前工程无效', exit_code=2, diagnostics=initial)
        selection = None
        if args.action == 'select':
            from .ad_selection import prepare, resolve
            from .semantic import search
            prepared = prepare(project, payload)
            # Reject an invalid output before loading a model or allocating a
            # managed semantic workspace. The final save remains atomic.
            output = resolve_local_path(root, args.output, field='output')
            if not output.is_relative_to((root / 'validation').resolve()):
                raise AppError('AD_OUTPUT_INVALID', '分镜计划必须保存到项目 validation 目录', exit_code=2)
            if output.exists():
                raise AppError('OUTPUT_EXISTS', '计划输出已存在；请提供新路径', exit_code=2, path=str(output))
            retrieved = search(root, project, index_id=args.index_id, queries_file=input_path,
                calibration_id=args.calibration_id, device=args.device, device_index=args.device_index,
                batch_size=args.batch_size, limit=args.limit, kind=args.kind, distinct_assets=False,
                timeout=args.timeout_seconds, cancel_file=args.cancel_file, dry_run=args.dry_run)
            if args.dry_run:
                return envelope('ad.select', args, status='planned', data=dict(
                    output=str(output), retrieval=retrieved, model_forward_calls=0,
                    verification=verification_summary(),
                    required_duration_ticks=prepared['required_duration_ticks'],
                    plan=None, selection_not_executed=True))
            plan, selection = resolve(project, prepared, retrieved)
            selection['retrieval'] = retrieved
        elif args.action == 'storyboard':
            plan = storyboard.plan_storyboard(project, payload)
        elif args.action == 'revise':
            plan = storyboard.plan_revision(project, payload)
        else:
            plan = payload
        candidate = storyboard.apply_plan(project, plan)
        paths = _check_assets(root, project, plan)
        _check_layout(plan, paths)
        validation = validate_project(root, candidate, strict_rights=False)
        if not validation['ok']:
            raise AppError('PROJECT_INVALID', '广告分镜会生成无效项目', exit_code=2, diagnostics=validation)
        data = dict(plan=plan, validation=validation, verification=verification_summary(),
                    sequence_ids=[s['id'] for s in plan['sequences']])
        if selection is not None:
            data['selection'] = selection
        output = None
        if args.action != 'build':
            output = resolve_local_path(root, args.output, field='output')
            try:
                output.relative_to((root / 'validation').resolve())
            except ValueError as exc:
                raise AppError('AD_OUTPUT_INVALID', '分镜计划必须保存到项目 validation 目录', exit_code=2, path=str(output)) from exc
            if output.exists():
                raise AppError('OUTPUT_EXISTS', '计划输出已存在；请提供新路径', exit_code=2, path=str(output))
            data['output'] = str(output)
        checkpoint(force=True)
        if input_pin is not None and artifact_entry(input_path, 'ad-selection-brief') != input_pin:
            raise AppError('AD_INPUT_CHANGED', '选材请求在规划期间发生改变', exit_code=2)
        if args.dry_run:
            return envelope('ad.' + args.action, args, status='planned', data=data, warnings=plan['warnings'])
        if output is not None:
            atomic_write_json(output, plan)
            return envelope('ad.' + args.action, args, data=data, warnings=plan['warnings'])
        snapshot = create_snapshot(root, project, label='before-ad-' + plan['kind'])
        operation_id = new_id('op')
        record = dict(operation_id=operation_id, command='ad.build', status='succeeded', created_at=now_iso(),
                      plan_sha256=plan['plan_sha256'], kind=plan['kind'], sequence_ids=data['sequence_ids'],
                      input=str(input_path), before_snapshot_id=snapshot['snapshot_id'])
        candidate.setdefault('provenance', {}).setdefault('change_log', []).append(record.copy())
        checkpoint(force=True)
        save_project(root, candidate)
        operation(root, operation_id, record)
        checkpoint(force=True)
        return envelope('ad.build', args, data={**data, 'before_snapshot': snapshot},
                        warnings=plan['warnings'], operation_id=operation_id)
