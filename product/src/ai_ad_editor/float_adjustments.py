"""Ordered sequence adjustments after the complete linear Float32 composite.

Global settings are evaluated once on the selected sequence's clock, never
once per child canvas. Intervals retain their authored start and duration;
selecting a shorter sequence only clips coverage, not animation time.
"""
from dataclasses import dataclass
from fractions import Fraction
import copy
import json

from .errors import AppError

PROTOCOL = 'selected-sequence-author-clock-float32-adjustments-v1'
MAX_LAYERS = 128
MAX_EFFECTS = 4096
MAX_DECLARATION_BYTES = 8 * 1024**2


def error(kind, message, **details):
    return AppError('FLOAT_ADJUSTMENT_' + kind, message, exit_code=2,
                    diagnostics=details or None)


def integer(value, minimum=0):
    if type(value) is not int or not minimum <= value < 2**63:
        raise error('CLOCK', '调整层时钟须为范围内的JSON整数')
    return value


@dataclass(frozen=True)
class AdjustmentPlan:
    index: int
    id: str
    start_tick: int
    end_tick: int
    effects: tuple


class FloatAdjustments:
    def __init__(self, raw, compiler, sequence, *, cancel):
        self.compiler, self.poll = compiler, cancel
        self.poll()
        duration = integer(sequence['duration_tick'], 1)
        raw = [] if raw is None else raw
        if not isinstance(raw, list) or len(raw) > MAX_LAYERS:
            raise error('BUDGET', '调整层须为最多128层的数组')
        try:
            size = len(json.dumps(raw, ensure_ascii=False, allow_nan=False).encode('utf8'))
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            raise error('ARGUMENT', '调整层必须是有限JSON声明') from exc
        if size > MAX_DECLARATION_BYTES:
            raise error('BUDGET', '调整层声明超过8MiB')
        self.plans = []
        rows, count = [], 0
        for index, incoming in enumerate(raw):
            self.poll()
            layer = {'type': incoming} if isinstance(incoming, str) else copy.deepcopy(incoming)
            if not isinstance(layer, dict) or type(layer.get('enabled', True)) is not bool:
                raise error('ARGUMENT', '调整层格式或enabled无效', index=index)
            label = layer.get('id', 'adjustment_' + str(index))
            if not isinstance(label, str) or not label or len(label) > 256:
                raise error('ARGUMENT', '调整层ID须为非空字符串', index=index)
            start = integer(layer.get('start_tick', 0))
            declared = integer(layer['duration_tick'], 1) if 'duration_tick' in layer else None
            if declared is not None and start + declared >= 2**63:
                raise error('CLOCK', '调整层终点超出时钟范围', index=index)
            end = start + declared if declared is not None else duration
            row = dict(index=index, id=label, enabled=layer.get('enabled', True),
                start_tick=start, declared_duration_tick=declared, end_tick=end,
                effective_start_tick=min(start, duration), effective_end_tick=min(end, duration),
                effect_types=[], compiled_effects=0)
            rows.append(row)
            if not row['enabled']:
                continue
            if 'effects' in layer:
                if set(layer) - {'id', 'enabled', 'start_tick', 'duration_tick', 'effects'}:
                    raise error('ARGUMENT', '调整层容器含未知字段', index=index)
                effects = layer['effects']
            else:
                effect = {k: v for k, v in layer.items() if k not in {'start_tick', 'duration_tick'}}
                effects = [effect]
            if not isinstance(effects, list):
                raise error('ARGUMENT', '调整层effects须为数组', index=index)
            count += len(effects)
            if count > MAX_EFFECTS:
                raise error('BUDGET', '调整层效果总数超过4096')
            effects = [{'type': e} if isinstance(e, str) else e for e in effects]
            # The existing compiler owns each effect's parameters, explicit
            # signal, animation, range, alpha and resource requirements.
            chain = compiler.compile(effects)
            if declared is not None:
                for effect in effects:
                    if not effect.get('enabled', True):
                        continue
                    parameters = effect.get('parameters', {})
                    tracks = effect.get('keyframes', parameters.get('keyframes', []))
                    if any(key['at_tick'] > declared for track in tracks for key in track['keyframes']):
                        raise error('CLOCK', '关键帧超过调整层原始声明时长', index=index)
            row['effect_types'] = [e['type'] for e in effects if e.get('enabled', True)]
            row['compiled_effects'] = len(chain)
            if chain and start < min(end, duration):
                if compiler.working.transfer != 'linear':
                    raise error('SIGNAL', '浮点调整层要求明确线性光工作域')
                self.plans.append(AdjustmentPlan(index, label, start, end, chain))
        self.plans = tuple(self.plans)
        self.metadata = dict(protocol=PROTOCOL, selected_sequence_id=sequence['id'],
            stage='after-all-video-and-subtitle-tracks-before-delivery-conversion',
            clock='selected sequence tick minus declared layer start; no frame-grid resnap',
            nested_application='once at selected root; child canvases are not graded twice',
            intervals='start-inclusive/end-exclusive; clipped coverage retains original animation clock',
            layers=rows, active_plans=len(self.plans), applied_frames=0, layer_applications=0,
            integer_intermediate=False, GPU=False, audio_changed=False,
            workspace_scope='existing per-effect explicit quota; not aggregate process RSS')

    def apply(self, surface, at_tick, *, left_limit=False):
        self.poll()
        if isinstance(at_tick, bool) or not isinstance(at_tick, (int, Fraction)) or at_tick < 0:
            raise error('CLOCK', '调整层取样时钟须为非负整数或精确有理数')
        value, rows = surface, []
        for plan in self.plans:
            covered = (plan.start_tick < at_tick <= plan.end_tick) if left_limit else (plan.start_tick <= at_tick < plan.end_tick)
            if not covered:
                continue
            self.poll()
            tick = at_tick - plan.start_tick
            sampled = tick
            if left_limit and tick > 0:
                sampled -= min(Fraction(1, 2**52), Fraction(tick) / 2)
            value, evidence = self.compiler.apply(value, plan.effects, sampled)
            if any(row.get('GPU') for row in evidence.get('ordered_effects',[])):
                self.metadata['GPU']=True
                self.metadata['GPU_scope']='analytic-optical-effects-only;other-adjustment-operators-CPU'
            rows.append(dict(index=plan.index, id=plan.id, author_tick=str(tick),
                left_limit=left_limit, effects=evidence))
        if rows:
            self.metadata['applied_frames'] += 1
            self.metadata['layer_applications'] += len(rows)
        return value, rows

    def verify(self):
        self.compiler.verify(p.effects for p in self.plans)
