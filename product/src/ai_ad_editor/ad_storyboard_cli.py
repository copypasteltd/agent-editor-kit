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


ACTIONS = ('storyboard', 'build', 'revise')


def add_parsers(actions, leaf):
    for action in ACTIONS:
        parser = leaf(actions.add_parser(action, help={
            'storyboard': '将已确认文案/素材规划为可编辑的多画幅广告',
            'build': '核对计划、工程和实际素材后原子提交广告分镜',
            'revise': '按稳定变体/镜头 ID 规划局部返工，保留其他编辑'}[action]))
        parser.add_argument('--project', required=True)
        parser.add_argument('--input', required=True)
        if action != 'build':
            parser.add_argument('--output', required=True, help='新的项目内 validation/*.json 计划')
        parser.add_argument('--timeout-seconds', type=float, default=600)
        parser.add_argument('--cancel-file')


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
    payload = load_json(input_path)
    with verification_scope(), operation_budget(args.timeout_seconds, args.cancel_file, root=root):
        initial = validate_project(root, project, strict_rights=False)
        if not initial['ok']:
            raise AppError('PROJECT_INVALID', '广告规划前工程无效', exit_code=2, diagnostics=initial)
        if args.action == 'storyboard':
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
