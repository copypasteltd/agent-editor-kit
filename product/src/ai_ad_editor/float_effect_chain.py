"""Ordered local Float32 exposure/LUT effects on the original author clock."""
from .errors import AppError
from .float_exposure import Exposure, compile_effects as compile_exposure, apply_exposure
from .float_lut import LUTPlan, compile_lut, apply_lut, verify_dependencies, MAX_WORKING_BYTES
from .float_curves import CurvePlan, compile_curves, apply_curves, ALIASES as CURVE_ALIASES
from .float_levels import (LevelPlan,ExposureAnimation,compile_levels,compile_animated_exposure,
    apply_levels,apply_animated_exposure,ALIASES as LEVEL_ALIASES)
from .float_balance import BalancePlan,compile_balance,apply_balance,ALIASES as BALANCE_ALIASES
from .float_selective_hsl import SelectiveHSLPlan,compile_hsl,apply_hsl,ALIASES as HSL_ALIASES
from .float_tone import TonePlan,compile_tone,apply_tone,ALIASES as TONE_ALIASES
from .float_gaussian import GaussianPlan,compile_gaussian,apply_gaussian,ALIASES as GAUSSIAN_ALIASES
from .float_spatial import SpatialPlan,compile_spatial,apply_spatial,ALIASES as SPATIAL_ALIASES
from .float_sharpen import SharpenPlan,compile_sharpen,apply_sharpen,ALIASES as SHARPEN_ALIASES
from .float_keyer import KeyerPlan,compile_keyer,apply_keyer,ALIASES as KEYER_ALIASES

PROTOCOL = 'ordered-author-clock-float32-effect-chain-v1'


class EffectCompiler:
    def __init__(self, *, resource_root, working_signal, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
        self.root,self.working,self.budget,self.cancel = resource_root,working_signal,max_working_bytes,cancel
        self.cubes = {}

    def compile(self, effects):
        if not isinstance(effects,list) or len(effects)>128:
            raise AppError('FLOAT_EFFECT_CHAIN_ARGUMENT','效果链须为最多128项数组',exit_code=2)
        result = []
        for effect in effects:
            if not isinstance(effect,dict) or type(effect.get('enabled',True)) is not bool:
                raise AppError('FLOAT_EFFECT_CHAIN_ARGUMENT','效果声明或enabled无效',exit_code=2)
            if not effect.get('enabled',True): continue
            name = str(effect.get('type','')).strip().lower().replace('-','_')
            if name=='exposure':
                p = effect.get('parameters',{})
                if 'keyframes' in effect or isinstance(p,dict) and 'keyframes' in p:
                    result.append(compile_animated_exposure(effect))
                else:
                    result.extend(compile_exposure([effect]))
            elif name in ('lut3d','lut','cube','look'):
                result.append(compile_lut(effect,resource_root=self.root,cache=self.cubes,
                    max_working_bytes=self.budget,cancel=self.cancel))
            elif name in CURVE_ALIASES:
                result.append(compile_curves(effect))
            elif name in LEVEL_ALIASES:
                result.append(compile_levels(effect))
            elif name in BALANCE_ALIASES:
                result.append(compile_balance(effect))
            elif name in HSL_ALIASES:
                result.append(compile_hsl(effect))
            elif name in TONE_ALIASES:
                result.append(compile_tone(effect))
            elif name in GAUSSIAN_ALIASES:
                result.append(compile_gaussian(effect))
            elif name in SPATIAL_ALIASES:
                result.append(compile_spatial(effect))
            elif name in SHARPEN_ALIASES:
                result.append(compile_sharpen(effect))
            elif name in KEYER_ALIASES:
                result.append(compile_keyer(effect))
            else:
                raise AppError('FLOAT_TIMELINE_UNSUPPORTED','该效果尚未连接浮点时间线',exit_code=2)
        return tuple(result)

    def dependencies(self, plans):
        """Return every actual LUT/library identity used by compiled chains."""
        result = {}
        for chain in plans:
            for plan in chain:
                if isinstance(plan, LUTPlan):
                    for dependency in plan.dependencies:
                        previous = result.setdefault(dependency.path, dependency)
                        if previous != dependency:
                            raise AppError('FLOAT_LUT_RESOURCE_CHANGED', '效果链LUT依赖身份冲突', exit_code=2)
        return tuple(result[path] for path in sorted(result))

    def verify(self, plans):
        seen = set()
        for chain in plans:
            for plan in chain:
                if isinstance(plan,LUTPlan):
                    for dependency in plan.dependencies:
                        if dependency not in seen:
                            verify_dependencies((dependency,),cancel=self.cancel); seen.add(dependency)

    def apply(self, surface, plans, tick):
        retained = sum(len(cube.payload) for cube in self.cubes.values())
        if all(isinstance(plan,Exposure) for plan in plans):
            return apply_exposure(surface,plans,max_working_bytes=self.budget-retained,cancel=self.cancel)
        rows = []
        value = surface
        for index,plan in enumerate(plans):
            if isinstance(plan,Exposure):
                value,metadata = apply_exposure(value,(plan,),max_working_bytes=self.budget-retained,cancel=self.cancel)
                rows.append({'index':index,'type':'exposure',**metadata})
            elif isinstance(plan,LUTPlan):
                value,metadata = apply_lut(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':'lut3d',**metadata})
            elif isinstance(plan,CurvePlan):
                value,metadata = apply_curves(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':'rgb_curves',**metadata})
            elif isinstance(plan,LevelPlan):
                value,metadata = apply_levels(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':'color_levels',**metadata})
            elif isinstance(plan,ExposureAnimation):
                value,metadata = apply_animated_exposure(value,plan,tick,max_working_bytes=self.budget-retained,cancel=self.cancel)
                rows.append({'index':index,'type':'exposure',**metadata})
            elif isinstance(plan,BalancePlan):
                value,metadata = apply_balance(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':plan.effect_type,**metadata})
            elif isinstance(plan,SelectiveHSLPlan):
                value,metadata = apply_hsl(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':'selective_hsl',**metadata})
            elif isinstance(plan,TonePlan):
                value,metadata = apply_tone(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':plan.effect_type,**metadata})
            elif isinstance(plan,GaussianPlan):
                value,metadata = apply_gaussian(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':'blur',**metadata})
            elif isinstance(plan,SpatialPlan):
                value,metadata = apply_spatial(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':plan.effect_type,**metadata})
            elif isinstance(plan,SharpenPlan):
                value,metadata = apply_sharpen(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':'sharpen',**metadata})
            elif isinstance(plan,KeyerPlan):
                value,metadata = apply_keyer(value,plan,tick,working_signal=self.working,retained_table_bytes=retained,
                    max_working_bytes=self.budget,cancel=self.cancel)
                rows.append({'index':index,'type':'chroma_key',**metadata})
            else:
                raise AppError('FLOAT_EFFECT_CHAIN_ARGUMENT','效果链含未编译计划',exit_code=2)
        return value,{'protocol':PROTOCOL,'ordered_effects':rows,'author_tick':str(tick),
            'alpha':'explicit-per-effect-alpha-mapping' if any(r.get('alpha')!='input-bits-preserved' for r in rows) else 'input-bits-preserved',
            'integer_intermediate':False,'HDR_accepted':False}
