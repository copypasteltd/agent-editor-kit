from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from .errors import AppError
from .clip_windows import validate_window, validate_track_transitions
from .speed_curves import compile_curve
from .sequence_canvas import validate_canvas
from .edit_planner import validate_editing
from .source_transitions import analyze as analyze_source_transitions
from .audio_routing import plan as plan_audio_routing
from .effect_automation import (ALIASES as AUTOMATION_EFFECT_ALIASES,
                                parameter_names as automation_parameter_names,
                                validate as validate_legacy_effect_automation,
                                _finite_number as finite_effect_number)

from .policy import reference_kind, resolve_local_path
from .project import asset_map
from .rights import check_project_rights, load_ledger
from .lut_library import find_lut
from .utils import ID_RE, sha256_file


TRANSITION_TYPES = {
    "fade", "fade_in", "fade_out", "dissolve", "crossfade", "wipe", "slide",
    "circlecrop", "rectcrop", "distance", "fadeblack", "fadewhite", "radial",
    "smoothleft", "smoothright", "smoothup", "smoothdown", "circleopen", "circleclose",
    "horzopen", "horzclose", "vertopen", "vertclose", "diagtl", "diagtr", "diagbl", "diagbr",
    "hlslice", "hrslice", "vuslice", "vdslice", "pixelize", "zoomin", "fadefast", "fadeslow",
    "hlwind", "hrwind", "vuwind", "vdwind", "coverleft", "coverright", "coverup", "coverdown",
    "revealleft", "revealright", "revealup", "revealdown", "wipetl", "wipetr", "wipebl", "wipebr",
    "hblur", "fadegrays", "squeezeh", "squeezev",
}

EFFECT_KEYFRAME_ALIASES: dict[str, set[str]] = {
    "brightness": {"brightness", "amount", "value"},
    "contrast": {"contrast", "amount", "value"},
    "saturation": {"saturation", "amount", "value"},
    "color": {"brightness", "contrast", "saturation"},
    "hue": {"degrees", "angle", "hue", "value"},
    "hue_rotate": {"degrees", "angle", "hue", "value"},
    "hsl": {"hue", "degrees", "angle", "saturation", "lightness", "brightness", "value"},
    "hsl_adjust": {"hue", "degrees", "angle", "saturation", "lightness", "brightness", "value"},
    "gamma": {"gamma", "amount", "value"},
    "gamma_adjust": {"gamma", "amount", "value"},
    "vignette": {"angle", "value"},
}
EFFECT_KEYFRAME_ALIASES.update({name: automation_parameter_names(name) for name in AUTOMATION_EFFECT_ALIASES})
from .selective_hsl import ALIASES as HSL_ALIASES, SPECS as HSL_SPECS
EFFECT_KEYFRAME_ALIASES.update({name: set(HSL_SPECS) for name in HSL_ALIASES})
from .curve_automation import ALIASES as CURVE_ALIASES, parameter_names as curve_parameter_names
EFFECT_KEYFRAME_ALIASES.update({name: curve_parameter_names(name) for name in CURVE_ALIASES})

COLOR_METADATA_VALUES: dict[str, set[str]] = {
    "primaries": {"bt709", "bt2020", "smpte170m", "smpte432"},
    "transfer": {"bt709", "bt2020-10", "smpte2084", "arib-std-b67", "iec61966-2-1", "linear"},
    "matrix": {"bt709", "bt2020nc", "bt2020c", "smpte170m", "gbr"},
    "range": {"limited", "full", "tv", "pc"},
}

TONE_MAP_ALGORITHMS = {"none", "linear", "gamma", "clip", "reinhard", "hable", "mobius"}
TONE_MAP_INPUT_TRANSFERS = {"bt2020-10", "bt2020-12", "smpte2084", "arib-std-b67"}

LUT_EFFECT_TYPES = {"lut", "lut3d", "cube", "look"}
LUT_EXTENSIONS = {".cube", ".3dl", ".csp", ".dat"}


def _schema_path() -> Path:
    from .schema_contract import schema_path
    return schema_path()


def _schema_report(project: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    """Execute the pinned package contract; executor/resource failures are errors."""
    from .schema_contract import make_validator
    try:
        validator = make_validator()
        failures: list[dict[str, Any]] = []
        for item in sorted(validator.iter_errors(project), key=lambda error: tuple(str(x) for x in error.absolute_path)):
            parts = [str(value) for value in item.absolute_path]
            failures.append({"code": "SCHEMA_VALIDATION_FAILED", "message": item.message, "path": ".".join(parts) or "$", "retryable": False})
        return failures, [], "jsonschema"
    except AppError as exc:
        return [exc.as_dict()], [], "unavailable"


def _int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def validate_project(root: Path, project: dict[str, Any], *, strict_rights: bool = False, target: str = "commercial_ad", rights_ledger: dict[str, Any] | None = None) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    native_settings = project.get('settings')
    native_pipeline = native_settings.get('pixel_pipeline') if isinstance(native_settings,dict) else None
    native_curves = isinstance(native_pipeline,dict) and native_pipeline.get('engine')=='float32-native-v1'

    def validate_effect_automation(effect, *, duration_tick=None):
        name = str(effect.get('type','')).strip().lower().replace('-','_')
        if native_curves:
            from .float_keyer import ALIASES as KEYER_ALIASES,validate_keyer
            if name in KEYER_ALIASES:return validate_keyer(effect,duration_tick=duration_tick)
            from .float_sharpen import ALIASES as SHARPEN_ALIASES,validate_sharpen
            if name in SHARPEN_ALIASES:return validate_sharpen(effect,duration_tick=duration_tick)
            from .float_spatial import ALIASES as SPATIAL_ALIASES,validate_spatial
            if name in SPATIAL_ALIASES:return validate_spatial(effect,duration_tick=duration_tick)
            from .float_gaussian import ALIASES as GAUSSIAN_ALIASES,validate_gaussian
            if name in GAUSSIAN_ALIASES:return validate_gaussian(effect,duration_tick=duration_tick)
            from .float_tone import ALIASES as TONE_ALIASES,validate_tone
            if name in TONE_ALIASES:return validate_tone(effect,duration_tick=duration_tick)
            from .float_balance import ALIASES as BALANCE_ALIASES,validate_balance
            if name in BALANCE_ALIASES:return validate_balance(effect,duration_tick=duration_tick)
            if name in HSL_ALIASES:
                from .float_selective_hsl import validate_hsl
                return validate_hsl(effect,duration_tick=duration_tick)
        if native_curves and name in CURVE_ALIASES:
            from .float_curves import validate_curves
            return validate_curves(effect,duration_tick=duration_tick)
        if native_curves and name in ('exposure','color_levels','levels','colorlevels'):
            from .float_levels import validate_native
            return validate_native(effect,duration_tick=duration_tick)
        return validate_legacy_effect_automation(effect,duration_tick=duration_tick)

    def effect_properties(name):
        if native_curves:
            from .float_keyer import ALIASES as KEYER_ALIASES,parameter_names as keyer_parameter_names
            if name in KEYER_ALIASES:return keyer_parameter_names()
            from .float_sharpen import ALIASES as SHARPEN_ALIASES,parameter_names as sharpen_parameter_names
            if name in SHARPEN_ALIASES:return sharpen_parameter_names()
            from .float_spatial import ALIASES as SPATIAL_ALIASES,parameter_names as spatial_parameter_names
            if name in SPATIAL_ALIASES:return spatial_parameter_names()
            from .float_gaussian import ALIASES as GAUSSIAN_ALIASES,parameter_names as gaussian_parameter_names
            if name in GAUSSIAN_ALIASES:return gaussian_parameter_names()
            from .float_tone import ALIASES as TONE_ALIASES,parameter_names as tone_parameter_names
            if name in TONE_ALIASES:return tone_parameter_names(name)
            from .float_balance import ALIASES as BALANCE_ALIASES,parameter_names
            if name in BALANCE_ALIASES:return parameter_names(name)
            if name in HSL_ALIASES:
                from .float_selective_hsl import BOUNDS
                return frozenset(BOUNDS)
        if native_curves and name in ('color_levels','levels','colorlevels'):
            from .float_levels import PARAMETER_NAMES
            return PARAMETER_NAMES
        if native_curves and name in CURVE_ALIASES:
            from .float_curves import PARAMETER_NAMES
            return PARAMETER_NAMES
        return EFFECT_KEYFRAME_ALIASES.get(name)
    schema_errors, schema_warnings, schema_engine = _schema_report(project)
    errors.extend(schema_errors)
    warnings.extend(schema_warnings)
    if not schema_errors:
        from .html_components import validate_project_metadata
        try:
            validate_project_metadata(project)
        except AppError as exc:
            errors.append(exc.as_dict())

    def error(code: str, message: str, path: str) -> None:
        errors.append({"code": code, "message": message, "path": path, "retryable": False})

    def warning(code: str, message: str, path: str) -> None:
        warnings.append({"code": code, "message": message, "path": path})

    def validate_audio_processing(control: dict[str, Any], path: str) -> None:
        def bounded(value: Any, lower: float, upper: float, location: str) -> None:
            if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or not lower <= value <= upper:
                error('AUDIO_PARAMETER_INVALID',f'音频参数必须是 {lower}..{upper} 的有限数字',location)
        for field in ('mute','muted','solo','duck_under_voice','dialogue_enhance','voice_enhance'):
            if field in control and not isinstance(control[field],bool):
                error('AUDIO_BOOLEAN_INVALID',f'audio.{field} 必须是布尔值',path+'.'+field)
        for field,limits in {'volume':(0,4),'fade_in':(0,86400),'fade_out':(0,86400),
                             'pitch_semitones':(-24,24),'highpass':(20,20000),'lowpass':(20,20000)}.items():
            if field in control:bounded(control[field],*limits,path+'.'+field)
        for field in ('noise_reduction','denoise'):
            if field in control and not isinstance(control[field],bool):bounded(control[field],-80,-20,path+'.'+field)
        for field in ('compressor','equalizer','eq','reverb','loudnorm'):
            value=control.get(field)
            if value is None:continue
            if field=='compressor' and isinstance(value,bool):continue
            if not isinstance(value,dict):
                error('AUDIO_EFFECT_INVALID',f'audio.{field} 必须是参数对象',path+'.'+field);continue
            ranges={'compressor':{'threshold':(.000976563,1),'ratio':(1,20),'attack':(.01,2000),'release':(1,9000)},
                    'equalizer':{'frequency':(20,20000),'f':(20,20000),'gain':(-24,24),'g':(-24,24),'width':(.05,10),'w':(.05,10)},
                    'reverb':{'in_gain':(0,1),'out_gain':(0,1)},
                    'loudnorm':{'i':(-70,-5),'integrated':(-70,-5),'tp':(-9,0),'true_peak':(-9,0),'lra':(1,50)}}
            for parameter,limits in ranges.get('equalizer' if field=='eq' else field,{}).items():
                if parameter in value:bounded(value[parameter],*limits,path+'.'+field+'.'+parameter)
            if field=='reverb':
                counts=[]
                for parameter,default,limits in (('delays','60|90',(0,90000)),('decays','0.25|0.15',(0,1))):
                    raw=value.get(parameter,default)
                    if not isinstance(raw,str) or not re.fullmatch(r'\d+(?:\.\d+)?(?:\|\d+(?:\.\d+)?)*',raw):
                        error('AUDIO_REVERB_INVALID','回声 delays/decays 必须是以 | 分隔的非负数字',path+'.reverb.'+parameter);continue
                    parts=raw.split('|');counts.append(len(parts))
                    if len(parts)>32:error('AUDIO_REVERB_INVALID','回声抽头不能超过 32 个',path+'.reverb.'+parameter)
                    for part in parts:bounded(float(part),*limits,path+'.reverb.'+parameter)
                if len(counts)==2 and counts[0]!=counts[1]:error('AUDIO_REVERB_INVALID','回声 delays/decays 数量必须一致',path+'.reverb')

    def validate_lut_resource(effect_value: dict[str, Any], effect_path: str) -> None:
        effect_type = str(effect_value.get("type", "")).lower().replace("-", "_")
        if effect_type not in LUT_EFFECT_TYPES:
            return
        parameters = effect_value.get("parameters") if isinstance(effect_value.get("parameters"), dict) else effect_value
        if "intensity" in parameters:
            raw_intensity = parameters.get("intensity")
            try:
                intensity = float(raw_intensity)
            except (TypeError, ValueError):
                intensity = math.nan
            if isinstance(raw_intensity, bool) or not math.isfinite(intensity) or not 0.0 <= intensity <= 1.0:
                error("LUT_INTENSITY_INVALID", "LUT intensity 必须是 0..1 的有限数字", f"{effect_path}.parameters.intensity")
        lut_id = parameters.get("lut_id")
        raw_path = parameters.get("path", parameters.get("file", parameters.get("lut")))
        path_field = f"{effect_path}.parameters.path"
        registered_record = None
        if lut_id is not None and str(lut_id).strip():
            path_field = f"{effect_path}.parameters.lut_id"
            registered_record = find_lut(root, str(lut_id).strip())
            if registered_record is None:
                error("LUT_ID_MISSING", f"LUT 库中不存在: {lut_id}", path_field)
                return
            raw_path = registered_record.get("uri")
        if raw_path is None or not str(raw_path).strip():
            error("LUT_PATH_MISSING", "LUT 效果必须提供 parameters.path/file", path_field)
            return
        raw_text = str(raw_path).strip()
        if "://" in raw_text and not raw_text.lower().startswith("file://"):
            error("LUT_PATH_NETWORK", "LUT 运行时路径不允许网络协议", path_field)
            return
        if raw_text.lower().startswith("file://"):
            raw_text = raw_text[7:]
        lut_path = Path(raw_text)
        if not lut_path.is_absolute():
            lut_path = root / lut_path
        try:
            lut_path.resolve().relative_to(root.resolve())
        except ValueError:
            error("LUT_PATH_OUTSIDE_PROJECT", "LUT 路径必须位于项目根目录内", path_field)
            return
        if not lut_path.exists() or not lut_path.is_file():
            error("LUT_FILE_MISSING", f"LUT 文件不存在: {lut_path}", path_field)
        if lut_path.suffix.lower() not in LUT_EXTENSIONS:
            error("LUT_EXTENSION_UNSUPPORTED", "LUT 文件扩展名只支持 .cube、.3dl、.csp 或 .dat", path_field)
        if registered_record is not None and lut_path.exists() and lut_path.is_file():
            try:
                actual_hash = f"sha256:{sha256_file(lut_path)}"
            except OSError as exc:
                error("LUT_HASH_READ_FAILED", f"读取登记 LUT 哈希失败: {exc}", path_field)
            else:
                if actual_hash != registered_record.get("sha256"):
                    error("LUT_HASH_MISMATCH", "登记 LUT 的 SHA-256 与项目文件不一致", path_field)

    if project.get("schema_version") != "0.1.0":
        error("SCHEMA_VERSION_UNSUPPORTED", "只支持 Agent Project schema 0.1.0", "schema_version")
    for field in ("project", "settings", "assets", "sequences", "provenance"):
        if field not in project:
            error("FIELD_REQUIRED", f"缺少顶层字段: {field}", field)
    if not isinstance(project.get("assets", []), list):
        error("TYPE_INVALID", "assets 必须是数组", "assets")
    if not isinstance(project.get("sequences", []), list):
        error("TYPE_INVALID", "sequences 必须是数组", "sequences")

    settings_value = project.get("settings")
    if isinstance(settings_value, dict):
        from .hardware_acceleration import configuration as acceleration_configuration
        try:
            acceleration_configuration(settings_value.get('acceleration'))
        except AppError as exc:
            error(exc.code, exc.message, exc.path or 'settings.acceleration')
        from .projection_opencl import configuration as projection_configuration
        try:
            projection_configuration(settings_value.get('projection_acceleration'))
        except AppError as exc:
            error(exc.code, exc.message, exc.path or 'settings.projection_acceleration')
        if settings_value.get('pixel_pipeline') is not None:
            from .float_standard_render import configuration as float_configuration
            from .render import output_settings
            try:
                float_configuration(settings_value['pixel_pipeline'], settings_value, output_settings(settings_value))
            except (AppError, KeyError, TypeError, ValueError) as exc:
                error(getattr(exc, 'code', 'FLOAT_RENDER_CONFIG'), getattr(exc, 'message', str(exc)),
                      getattr(exc, 'path', None) or 'settings.pixel_pipeline')
        if 'sequence_sampling' in settings_value:
            from .sequence_sampling import configuration as sequence_sampling_configuration
            try:
                sequence_sampling_configuration(settings_value['sequence_sampling'])
            except AppError as exc:
                error(exc.code, exc.message, exc.path or 'settings.sequence_sampling')
        if 'audio_stretch' in settings_value:
            from .audio_stretch import configuration
            try:
                configuration(root, settings_value['audio_stretch'])
            except AppError as exc:
                error(exc.code, exc.message, exc.path or 'settings.audio_stretch')
        color_value = settings_value.get("color")
        if color_value is not None:
            if not isinstance(color_value, dict):
                error("COLOR_METADATA_INVALID", "settings.color 必须是对象", "settings.color")
            else:
                for color_field, allowed_values in COLOR_METADATA_VALUES.items():
                    raw_color = color_value.get(color_field)
                    if raw_color is not None and str(raw_color).lower() not in allowed_values:
                        error("COLOR_METADATA_UNSUPPORTED", f"不支持的色彩元数据: {raw_color}", f"settings.color.{color_field}")
                tone_map = str(color_value.get("tone_map", color_value.get("tone_mapping", "none"))).lower()
                if tone_map not in TONE_MAP_ALGORITHMS:
                    error("TONE_MAP_UNSUPPORTED", f"不支持的 HDR tone map 算法: {tone_map}", "settings.color.tone_map")
                for field, allowed in {
                    "input_transfer": TONE_MAP_INPUT_TRANSFERS,
                    "input_primaries": {"bt2020", "bt709"},
                    "input_matrix": {"bt2020nc", "bt2020c", "bt709"},
                    "input_range": {"limited", "full", "tv", "pc"},
                }.items():
                    raw_value = color_value.get(field)
                    if raw_value is not None and str(raw_value).lower() not in allowed:
                        error("TONE_MAP_INPUT_UNSUPPORTED", f"不支持的 HDR 输入色彩字段: {raw_value}", f"settings.color.{field}")
                for field in ("tone_map_desat", "tone_map_peak"):
                    if field not in color_value:
                        continue
                    raw_value = color_value.get(field)
                    try:
                        numeric_value = float(raw_value)
                    except (TypeError, ValueError):
                        numeric_value = math.nan
                    if isinstance(raw_value, bool) or not math.isfinite(numeric_value) or numeric_value < 0:
                        error("TONE_MAP_PARAMETER_INVALID", f"{field} 必须是非负有限数字", f"settings.color.{field}")

        adjustments = settings_value.get("adjustments")
        if adjustments is not None:
            if not isinstance(adjustments, list):
                error("ADJUSTMENTS_INVALID", "settings.adjustments 必须是数组", "settings.adjustments")
            else:
                max_sequence_duration = max(
                    (_int(item.get("duration_tick"), 0) for item in project.get("sequences", []) if isinstance(item, dict)),
                    default=0,
                )

                def validate_adjustment_effect(effect_value: Any, effect_path: str, *, keyframe_limit: int | None = None) -> None:
                    if isinstance(effect_value, str):
                        return
                    if not isinstance(effect_value, dict):
                        error("EFFECT_INVALID", "序列调节效果必须是字符串或对象", effect_path)
                        return
                    if effect_value.get("enabled") is not None and not isinstance(effect_value.get("enabled"), bool):
                        error("EFFECT_ENABLED_INVALID", "序列调节效果 enabled 必须是布尔值", f"{effect_path}.enabled")
                    effect_type = str(effect_value.get("type", "")).lower().replace("-", "_")
                    if not effect_type:
                        error("EFFECT_TYPE_MISSING", "序列调节效果缺少 type", f"{effect_path}.type")
                        return
                    parameters = effect_value.get("parameters") if isinstance(effect_value.get("parameters"), dict) else effect_value
                    validate_lut_resource(effect_value, effect_path)
                    for finding in validate_effect_automation(effect_value, duration_tick=keyframe_limit):
                        error(finding['code'], finding['message'], effect_path+finding['suffix'])
                    raw_tracks = effect_value.get("keyframes")
                    if not isinstance(raw_tracks, list):
                        raw_tracks = parameters.get("keyframes") if isinstance(parameters.get("keyframes"), list) else []
                    supported_properties = effect_properties(effect_type)
                    for track_index, track_value in enumerate(raw_tracks):
                        track_path = f"{effect_path}.keyframes[{track_index}]"
                        if not isinstance(track_value, dict):
                            error("EFFECT_KEYFRAMES_INVALID", "序列调节 keyframe track 必须是对象", track_path)
                            continue
                        property_name = str(track_value.get("property", "")).strip().lower().replace("-", "_")
                        for prefix in ("effect.", "parameters.", f"{effect_type}."):
                            if property_name.startswith(prefix):
                                property_name = property_name[len(prefix):]
                                break
                        if not property_name:
                            error("EFFECT_KEYFRAME_PROPERTY_INVALID", "序列调节 keyframe property 不能为空", f"{track_path}.property")
                        elif supported_properties is None or property_name not in supported_properties:
                            warning("EFFECT_KEYFRAME_PROPERTY_UNSUPPORTED", "该序列调节参数关键帧不会逐帧执行，将使用静态参数值", f"{track_path}.property")
                        keyframes = track_value.get("keyframes")
                        if not isinstance(keyframes, list) or not keyframes:
                            error("EFFECT_KEYFRAMES_INVALID", "序列调节 keyframe track 必须包含非空 keyframes", f"{track_path}.keyframes")
                            continue
                        previous_at = -1
                        for keyframe_index, keyframe_value in enumerate(keyframes):
                            keyframe_path = f"{track_path}.keyframes[{keyframe_index}]"
                            if not isinstance(keyframe_value, dict):
                                error("EFFECT_KEYFRAMES_INVALID", "序列调节 keyframe 必须是对象", keyframe_path)
                                continue
                            at = _int(keyframe_value.get("at_tick"), -1)
                            limit = max_sequence_duration if keyframe_limit is None else keyframe_limit
                            if at < 0 or at < previous_at or limit and at > limit:
                                error("EFFECT_KEYFRAME_TIME_INVALID", "序列调节 keyframe at_tick 必须单调且位于当前调节层局部时钟范围内", f"{keyframe_path}.at_tick")
                            previous_at = at
                            interpolation = keyframe_value.get("interpolation")
                            if interpolation not in {"hold", "linear", "ease_in", "ease_out", "ease_in_out", "bezier"}:
                                error("INTERPOLATION_INVALID", "序列调节关键帧插值类型无效", f"{keyframe_path}.interpolation")
                            value = keyframe_value.get("value")
                            try:
                                numeric_value = float(value)
                            except (TypeError, ValueError, OverflowError):
                                numeric_value = math.nan
                            if isinstance(value, bool) or not math.isfinite(numeric_value):
                                error("EFFECT_KEYFRAME_VALUE_INVALID", "序列调节关键帧 value 必须是有限数字", f"{keyframe_path}.value")

                for adjustment_index, adjustment_value in enumerate(adjustments):
                    adjustment_path = f"settings.adjustments[{adjustment_index}]"
                    if isinstance(adjustment_value, str):
                        continue
                    if not isinstance(adjustment_value, dict):
                        error("ADJUSTMENT_INVALID", "序列调节层必须是字符串或对象", adjustment_path)
                        continue
                    if adjustment_value.get("enabled") is not None and not isinstance(adjustment_value.get("enabled"), bool):
                        error("ADJUSTMENT_ENABLED_INVALID", "序列调节 enabled 必须是布尔值", f"{adjustment_path}.enabled")
                    has_start = "start_tick" in adjustment_value
                    has_duration = "duration_tick" in adjustment_value
                    adjustment_duration_limit = max_sequence_duration
                    if has_start or has_duration:
                        start_tick = _int(adjustment_value.get("start_tick", 0), -1)
                        duration_tick = _int(adjustment_value.get("duration_tick", max_sequence_duration - max(0, start_tick)), -1)
                        adjustment_duration_limit = duration_tick
                        if start_tick < 0:
                            error("ADJUSTMENT_START_INVALID", "序列调节 start_tick 必须是非负整数", f"{adjustment_path}.start_tick")
                        if duration_tick <= 0:
                            error("ADJUSTMENT_DURATION_INVALID", "序列调节 duration_tick 必须大于 0", f"{adjustment_path}.duration_tick")
                        if max_sequence_duration and start_tick >= max_sequence_duration:
                            error("ADJUSTMENT_START_OUT_OF_RANGE", "序列调节 start_tick 必须位于序列时长内", f"{adjustment_path}.start_tick")
                        if max_sequence_duration and start_tick >= 0 and duration_tick > 0 and start_tick + duration_tick > max_sequence_duration:
                            error("ADJUSTMENT_END_OUT_OF_RANGE", "序列调节区间不能越过序列时长", adjustment_path)
                    if isinstance(adjustment_value.get("effects"), list):
                        for effect_index, effect_value in enumerate(adjustment_value["effects"]):
                            validate_adjustment_effect(effect_value, f"{adjustment_path}.effects[{effect_index}]", keyframe_limit=adjustment_duration_limit)
                    elif adjustment_value.get("type"):
                        validate_adjustment_effect(adjustment_value, adjustment_path, keyframe_limit=adjustment_duration_limit)
                    else:
                        error("ADJUSTMENT_EFFECTS_MISSING", "序列调节层必须提供 effects 或 type", adjustment_path)

    ids: set[str] = set()
    for index, asset in enumerate(project.get("assets", [])):
        path = f"assets[{index}]"
        aid = asset.get("id")
        if not isinstance(aid, str) or not ID_RE.fullmatch(aid):
            error("ID_INVALID", "资产 ID 不符合规范", f"{path}.id")
        elif aid in ids:
            error("ID_DUPLICATE", f"重复 ID: {aid}", f"{path}.id")
        else:
            ids.add(aid)
        uri = asset.get("uri")
        if not isinstance(uri, str) or not uri:
            error("ASSET_URI_MISSING", "资产 uri 缺失", f"{path}.uri")
        else:
            if "://" in uri and not uri.startswith("file://"):
                error("ASSET_URI_NETWORK", "运行时资产 uri 不允许网络协议", f"{path}.uri")
            asset_path = Path(uri)
            if not asset_path.is_absolute():
                asset_path = root / asset_path
            try:
                asset_path.resolve().relative_to(root.resolve())
            except ValueError:
                if not asset.get("extensions", {}).get("external_authorized"):
                    error("ASSET_PATH_OUTSIDE_PROJECT", "资产路径越过项目根目录且未声明外部授权", f"{path}.uri")
            if not asset_path.exists():
                error("ASSET_FILE_MISSING", f"资产文件不存在: {asset_path}", f"{path}.uri")
        probe = asset.get("probe")
        if not isinstance(probe, dict):
            error("ASSET_PROBE_MISSING", "资产 probe 缺失", f"{path}.probe")
        if not asset.get("rights_ref"):
            error("RIGHTS_REF_MISSING", "资产 rights_ref 缺失", f"{path}.rights_ref")
        if isinstance(asset.get('source'),dict) and 'face_retouch' in asset['source']:
            try:
                from .local_face import validate_recipe
                metadata = asset['source']['face_retouch']
                if not isinstance(metadata,dict) or set(metadata) != {'recipe'}:
                    raise ValueError('FACE_RETOUCH_METADATA_INVALID')
                validate_recipe(metadata['recipe'])
            except (ValueError,TypeError,KeyError,OverflowError,ZeroDivisionError) as exc:
                error('FACE_RETOUCH_METADATA_INVALID',str(exc),f'{path}.source.face_retouch')
        if isinstance(asset.get('source'), dict) and 'outpainting' in asset['source']:
            try:
                from .local_outpainting import validate_recipe
                validate_recipe(asset['source']['outpainting'], asset=asset, assets=asset_map(project))
            except AppError as exc:
                error(exc.code, exc.message, f'{path}.source.outpainting')
        if isinstance(asset.get('source'), dict) and 'vace_generation' in asset['source']:
            try:
                from .vace_context import validate_generation_metadata
                validate_generation_metadata(asset['source']['vace_generation'], asset=asset)
            except AppError as exc:
                error(exc.code, exc.message, f'{path}.source.vace_generation')

    declared_sequence_ids = {str(item.get("id")) for item in project.get("sequences", []) if item.get("id")}
    sequence_ids: set[str] = set()
    for si, sequence in enumerate(project.get("sequences", [])):
        sp = f"sequences[{si}]"
        try:
            plan_audio_routing(sequence)
        except AppError as exc:
            error(exc.code, exc.message, (exc.path or 'sequence.audio_routing').replace('sequence.', sp+'.', 1))
        try:
            analyze_source_transitions(project, sequence)
        except AppError as exc:
            error(exc.code, exc.message, (exc.path or 'sequence.source_transitions').replace('sequence.', sp+'.', 1))
        try:
            validate_editing(sequence)
            from .magnetic_mode import validate as validate_magnetic
            validate_magnetic(sequence)
        except AppError as exc:
            error(exc.code, exc.message, (exc.path or 'sequence.editing').replace('sequence.', sp+'.', 1))
        try:
            validate_canvas(sequence.get('canvas'), path=sp+'.canvas')
        except AppError as exc:
            error(exc.code, exc.message, exc.path or sp+'.canvas')
        sid = sequence.get("id")
        if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
            error("ID_INVALID", "序列 ID 不符合规范", f"{sp}.id")
        elif sid in ids or sid in sequence_ids:
            error("ID_DUPLICATE", f"重复 ID: {sid}", f"{sp}.id")
        else:
            sequence_ids.add(sid)
            ids.add(sid)
        duration = _int(sequence.get("duration_tick", 0))
        if duration <= 0:
            error("DURATION_INVALID", "序列 duration_tick 必须大于 0", f"{sp}.duration_tick")
        track_ids: set[str] = set()
        for ti, track in enumerate(sequence.get("tracks", [])):
            tp = f"{sp}.tracks[{ti}]"
            if 'sync_lock' in track and type(track['sync_lock']) is not bool:
                error('EDIT_CONFIGURATION_INVALID', '轨道 sync_lock 必须是布尔值', tp+'.sync_lock')
            tid = track.get("id")
            if not isinstance(tid, str) or not ID_RE.fullmatch(tid):
                error("ID_INVALID", "轨道 ID 不符合规范", f"{tp}.id")
            elif tid in ids or tid in track_ids:
                error("ID_DUPLICATE", f"重复 ID: {tid}", f"{tp}.id")
            else:
                track_ids.add(tid)
                ids.add(tid)
            if track.get("kind") not in {"video", "overlay", "audio", "subtitle", "data"}:
                error("TRACK_KIND_INVALID", "轨道 kind 无效", f"{tp}.kind")
            if track.get('kind') == 'overlay':
                from .bindings import native_clock_project
                if not native_clock_project(project):
                    error('TRACK_OVERLAY_PIPELINE_REQUIRED','overlay 轨道需要显式 float32-native-v1 渲染；默认轨道请使用 video',f'{tp}.kind')
            track_audio = track.get("audio")
            if track_audio is not None:
                if not isinstance(track_audio, dict):
                    error("TRACK_AUDIO_INVALID", "轨道 audio 必须是对象", f"{tp}.audio")
                else:
                    validate_audio_processing(track_audio,f'{tp}.audio')
                    for boolean_field in ("mute", "muted", "solo", "duck_under_voice"):
                        if boolean_field in track_audio and not isinstance(track_audio[boolean_field], bool):
                            error("TRACK_AUDIO_BOOLEAN_INVALID", f"轨道 audio.{boolean_field} 必须是布尔值", f"{tp}.audio.{boolean_field}")
                    if "volume" in track_audio:
                        raw_volume = track_audio.get("volume")
                        try:
                            volume = float(raw_volume)
                        except (TypeError, ValueError):
                            volume = math.nan
                        if isinstance(raw_volume, bool) or not math.isfinite(volume) or not 0.0 <= volume <= 4.0:
                            error("TRACK_AUDIO_VOLUME_INVALID", "轨道 audio.volume 必须是 0..4 的有限数字", f"{tp}.audio.volume")
                    if "pan" in track_audio:
                        raw_pan = track_audio.get("pan")
                        try:
                            pan = float(raw_pan)
                        except (TypeError, ValueError):
                            pan = math.nan
                        if isinstance(raw_pan, bool) or not math.isfinite(pan) or not -1.0 <= pan <= 1.0:
                            error("TRACK_AUDIO_PAN_INVALID", "轨道 audio.pan 必须是 -1..1 的有限数字", f"{tp}.audio.pan")
                    if "role" in track_audio and (not isinstance(track_audio.get("role"), str) or not str(track_audio.get("role")).strip()):
                        error("TRACK_AUDIO_ROLE_INVALID", "轨道 audio.role 必须是非空字符串", f"{tp}.audio.role")
            clips = track.get("clips", [])
            occupied: list[tuple[int, int, str]] = []
            try:
                validate_track_transitions(track)
            except AppError as exc:
                error(exc.code,exc.message,tp)
            for ci, clip in enumerate(clips):
                cp = f"{tp}.clips[{ci}]"
                if clip.get('link_id') is not None and (not isinstance(clip['link_id'], str) or not ID_RE.fullmatch(clip['link_id'])):
                    error('EDIT_LINK_ID_INVALID', '片段 link_id 必须为有效标识符或 null', cp+'.link_id')
                if isinstance(clip.get('subtitle'), dict) and 'asset_time_offset_tick' in clip['subtitle'] and type(clip['subtitle']['asset_time_offset_tick']) is not int:
                    error('SUBTITLE_ASSET_OFFSET_INVALID', '文件字幕时钟偏移必须为整数 tick', cp+'.subtitle.asset_time_offset_tick')
                dependencies = clip.get('rights_dependencies', [])
                if not isinstance(dependencies, list) or any(not isinstance(d, dict) or set(d) != {'rights_ref','sha256'} or not isinstance(d.get('rights_ref'), str) or not d['rights_ref'] or not re.fullmatch(r'sha256:[0-9a-f]{64}', str(d.get('sha256',''))) for d in dependencies):
                    error('CLIP_RIGHTS_DEPENDENCIES_INVALID', '片段权利依赖必须包含非空 rights_ref 和 sha256', f'{cp}.rights_dependencies')
                track_kind = str(track.get("kind", ""))
                generator = clip.get("generator")
                text_generator = isinstance(generator, dict) and str(generator.get("type", "")).lower() == "text"
                if generator is not None and (not isinstance(generator, dict) or str(generator.get("type", "")).lower() != "text"):
                    error("GENERATOR_UNSUPPORTED", "当前片段 generator 只支持 type=text", f"{cp}.generator")
                if generator is not None and track_kind != "subtitle":
                    error("GENERATOR_TRACK_INVALID", "文字 generator 必须位于 subtitle 轨道", f"{cp}.generator")
                inline_text_layer = track_kind == "subtitle" and text_generator and isinstance(clip.get("subtitle"), dict)
                cid = clip.get("id")
                if not isinstance(cid, str) or not ID_RE.fullmatch(cid):
                    error("ID_INVALID", "片段 ID 不符合规范", f"{cp}.id")
                elif cid in ids:
                    error("ID_DUPLICATE", f"重复 ID: {cid}", f"{cp}.id")
                else:
                    ids.add(cid)
                start = _int(clip.get("timeline_start_tick"), -1)
                dur = _int(clip.get("duration_tick"))
                src_in = _int(clip.get("source_in_tick"), -1)
                src_out = _int(clip.get("source_out_tick"), -1)
                if start < 0 or dur <= 0 or src_in < 0 or src_out <= src_in:
                    error("TIME_RANGE_INVALID", "片段时间范围无效", cp)
                if start + dur > duration:
                    error("CLIP_OUTSIDE_SEQUENCE", "片段超出序列时长", cp)
                if not inline_text_layer and clip.get("asset_id") not in asset_map(project) and clip.get("sequence_id") not in declared_sequence_ids:
                    error("REFERENCE_MISSING", "片段引用的资产或序列不存在", cp)
                if inline_text_layer and (clip.get("asset_id") or clip.get("sequence_id")):
                    error("GENERATOR_REFERENCE_CONFLICT", "文字 generator 不能同时引用 asset_id 或 sequence_id", cp)
                if track_kind == "subtitle" and clip.get("asset_id"):
                    subtitle_asset = asset_map(project).get(clip.get("asset_id"))
                    if subtitle_asset and subtitle_asset.get("kind") != "subtitle":
                        error("SUBTITLE_ASSET_KIND_INVALID", "subtitle 轨道只能引用 subtitle 资产", f"{cp}.asset_id")
                if clip.get("asset_id"):
                    asset = asset_map(project).get(clip.get("asset_id"))
                    if asset and asset.get("kind") != "subtitle" and _int(asset.get("probe", {}).get("duration_tick", 0)) and src_out > _int(asset["probe"]["duration_tick"]):
                        error("SOURCE_OUTSIDE_ASSET", "source_out_tick 超出素材长度", cp)
                authored_dur = dur
                if 'presentation_window' in clip:
                    try:
                        from .bindings import native_clock_project
                        authored_dur = validate_window(clip,allow_tracking=native_clock_project(project))
                    except AppError as exc:
                        error(exc.code, exc.message, cp+'.presentation_window')
                speed_curve = clip.get("speed_curve")
                if speed_curve is not None:
                    curve_points = speed_curve if isinstance(speed_curve, list) else speed_curve.get("keyframes") if isinstance(speed_curve, dict) else None
                    if not isinstance(curve_points, list) or not curve_points:
                        error("SPEED_CURVE_INVALID", "speed_curve 必须包含非空 keyframes", f"{cp}.speed_curve")
                    else:
                        previous_speed_at = -1
                        source_span = max(1, src_out - src_in)
                        curve_error_start = len(errors)
                        for point_index, point in enumerate(curve_points):
                            if not isinstance(point, dict):
                                error("SPEED_CURVE_INVALID", "speed_curve.keyframes 项必须是对象", f"{cp}.speed_curve.keyframes[{point_index}]")
                                continue
                            at = _int(point.get("at_tick"), -1)
                            try:
                                curve_speed = float(point.get("speed", point.get("value")))
                            except (TypeError, ValueError):
                                curve_speed = -1.0
                            if at < 0 or at > source_span or at < previous_speed_at:
                                error("SPEED_CURVE_RANGE", "speed 曲线 at_tick 必须单调且位于源片段范围内", f"{cp}.speed_curve.keyframes[{point_index}]")
                            if not math.isfinite(curve_speed) or curve_speed <= 0:
                                error("SPEED_CURVE_SPEED_INVALID", "speed 曲线 speed 必须是正数", f"{cp}.speed_curve.keyframes[{point_index}].speed")
                            interpolation = str(point.get("interpolation", "linear"))
                            if interpolation not in {"hold", "linear", "ease_in", "ease_out", "ease_in_out", "bezier"}:
                                error("SPEED_CURVE_INTERPOLATION_INVALID", "speed 曲线插值类型无效", f"{cp}.speed_curve.keyframes[{point_index}].interpolation")
                            previous_speed_at = at
                        if len(errors) == curve_error_start:
                            try:
                                curve_tps = max(1, _int(project.get('settings', {}).get('timebase', {}).get('ticks_per_second'), 90000))
                                compile_curve(clip, source_span, curve_tps)
                            except AppError as exc:
                                error(exc.code, exc.message, f'{cp}.speed_curve')
                freeze = clip.get("freeze")
                if freeze is not None:
                    if not isinstance(freeze, dict):
                        error("FREEZE_INVALID", "freeze 必须是对象", f"{cp}.freeze")
                    else:
                        freeze_duration = _int(freeze.get("duration_tick"), 0)
                        freeze_at = _int(freeze.get("at_tick"), -1)
                        original_duration = authored_dur - freeze_duration
                        if freeze_duration <= 0:
                            error("FREEZE_DURATION_INVALID", "freeze.duration_tick 必须为正数", f"{cp}.freeze.duration_tick")
                        if original_duration <= 0:
                            error("FREEZE_RANGE_INVALID", "freeze 必须保留至少一个非冻结片段时长", f"{cp}.freeze")
                        elif freeze_at < 0 or freeze_at > original_duration:
                            error("FREEZE_AT_INVALID", "freeze.at_tick 必须位于冻结前的片段时长内", f"{cp}.freeze.at_tick")
                        freeze_audio_mode = str(freeze.get("audio_mode", "silence")).lower()
                        if freeze_audio_mode not in {"silence", "continue"}:
                            error("FREEZE_AUDIO_MODE_INVALID", "freeze.audio_mode 只支持 silence 或 continue", f"{cp}.freeze.audio_mode")
                transform = clip.get("transform")
                if transform is not None:
                    if not isinstance(transform, dict):
                        error("TRANSFORM_INVALID", "transform 必须是对象", f"{cp}.transform")
                    else:
                        anchor = transform.get("anchor")
                        if anchor is not None:
                            if not isinstance(anchor, dict):
                                error("TRANSFORM_ANCHOR_INVALID", "transform.anchor 必须是对象", f"{cp}.transform.anchor")
                            else:
                                for axis in ("x", "y"):
                                    if axis not in anchor:
                                        continue
                                    raw_value = anchor.get(axis)
                                    try:
                                        value = float(raw_value)
                                    except (TypeError, ValueError):
                                        value = math.nan
                                    if isinstance(raw_value, bool) or not math.isfinite(value):
                                        error("TRANSFORM_ANCHOR_INVALID", "transform.anchor.x/y 必须是有限数字", f"{cp}.transform.anchor.{axis}")
                                    elif not 0.0 <= value <= 1.0:
                                        error("TRANSFORM_ANCHOR_RANGE", "transform.anchor.x/y 必须位于 0 到 1", f"{cp}.transform.anchor.{axis}")
                        for axis in ("x", "y"):
                            alias = f"anchor_{axis}"
                            if alias not in transform:
                                continue
                            raw_value = transform.get(alias)
                            try:
                                value = float(raw_value)
                            except (TypeError, ValueError):
                                value = math.nan
                            if isinstance(raw_value, bool) or not math.isfinite(value):
                                error("TRANSFORM_ANCHOR_INVALID", f"transform.{alias} 必须是有限数字", f"{cp}.transform.{alias}")
                            elif not 0.0 <= value <= 1.0:
                                error("TRANSFORM_ANCHOR_RANGE", f"transform.{alias} 必须位于 0 到 1", f"{cp}.transform.{alias}")
                crop = clip.get("crop")
                clip_crop_tracks = [item for item in clip.get("keyframes", []) if isinstance(item, dict) and str(item.get("property", "")).startswith("crop.")]
                if clip_crop_tracks and not isinstance(crop, dict):
                    error("CROP_KEYFRAMES_REQUIRE_CROP", "crop.* 关键帧必须声明 crop 对象及坐标单位", f"{cp}.crop")
                if crop is not None:
                    if not isinstance(crop, dict):
                        error("CROP_INVALID", "crop 必须是对象", f"{cp}.crop")
                    else:
                        crop_unit = str(crop.get("unit", "pixels")).lower()
                        if crop_unit not in {"pixels", "pixel", "normalized", "relative"}:
                            error("CROP_UNIT_INVALID", "crop.unit 只支持 pixels 或 normalized", f"{cp}.crop.unit")
                        for crop_field in ("x", "y", "width", "height", "w", "h"):
                            if crop_field not in crop:
                                continue
                            try:
                                crop_value = float(crop[crop_field])
                            except (TypeError, ValueError):
                                error("CROP_PARAMETER_INVALID", f"crop.{crop_field} 必须是有限数字", f"{cp}.crop.{crop_field}")
                                continue
                            if not math.isfinite(crop_value):
                                error("CROP_PARAMETER_INVALID", f"crop.{crop_field} 必须是有限数字", f"{cp}.crop.{crop_field}")
                            elif crop_value < 0 or crop_unit in {"normalized", "relative"} and crop_value > 1:
                                error("CROP_PARAMETER_RANGE", "crop 坐标和尺寸必须位于合法范围", f"{cp}.crop.{crop_field}")
                        fit_mode = str(crop.get("fit", crop.get("mode", "fit"))).lower()
                        if fit_mode not in {"fit", "fill", "stretch"}:
                            error("CROP_FIT_UNSUPPORTED", "crop.fit 只支持 fit、fill、stretch", f"{cp}.crop.fit")

                        def validate_crop_keyframes(tracks: Any, tracks_path: str) -> None:
                            if tracks is None:
                                return
                            if not isinstance(tracks, list):
                                error("CROP_KEYFRAMES_INVALID", "crop keyframes 必须是数组", tracks_path)
                                return
                            for track_index, track_value in enumerate(tracks):
                                track_path = f"{tracks_path}[{track_index}]"
                                if not isinstance(track_value, dict):
                                    error("CROP_KEYFRAMES_INVALID", "crop keyframe track 必须是对象", track_path)
                                    continue
                                property_name = str(track_value.get("property", ""))
                                normalized_name = property_name.removeprefix("crop.")
                                if normalized_name not in {"x", "y", "width", "w", "height", "h"}:
                                    error("CROP_KEYFRAME_PROPERTY_UNSUPPORTED", "crop keyframe property 只支持 x、y、width 和 height", f"{track_path}.property")
                                keyframes = track_value.get("keyframes")
                                if not isinstance(keyframes, list) or not keyframes:
                                    error("CROP_KEYFRAMES_INVALID", "crop keyframe track 必须包含非空 keyframes", f"{track_path}.keyframes")
                                    continue
                                previous_at = -1
                                for keyframe_index, keyframe_value in enumerate(keyframes):
                                    keyframe_path = f"{track_path}.keyframes[{keyframe_index}]"
                                    if not isinstance(keyframe_value, dict):
                                        error("CROP_KEYFRAMES_INVALID", "crop keyframe 必须是对象", keyframe_path)
                                        continue
                                    at = _int(keyframe_value.get("at_tick"), -1)
                                    if at < 0 or at > authored_dur or at < previous_at:
                                        error("CROP_KEYFRAME_TIME_INVALID", "crop keyframe at_tick 必须单调且位于片段内", f"{keyframe_path}.at_tick")
                                    previous_at = at
                                    interpolation = keyframe_value.get("interpolation")
                                    if interpolation not in {"hold", "linear", "ease_in", "ease_out", "ease_in_out", "bezier"}:
                                        error("INTERPOLATION_INVALID", "crop 关键帧插值类型无效", f"{keyframe_path}.interpolation")
                                    if interpolation == "bezier":
                                        controls = keyframe_value.get("control_points")
                                        if not isinstance(controls, list) or len(controls) not in {2, 4} or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in controls):
                                            error("BEZIER_CONTROL_POINTS_INVALID", "crop Bezier 控制点必须为 2 或 4 个有限数字", f"{keyframe_path}.control_points")
                                        elif len(controls) == 4 and not (0.0 <= controls[0] <= 1.0 and 0.0 <= controls[2] <= 1.0):
                                            error("BEZIER_CONTROL_POINT_RANGE", "Bezier x 控制点必须位于 0 到 1", f"{keyframe_path}.control_points")
                                    try:
                                        numeric_value = float(keyframe_value.get("value"))
                                    except (TypeError, ValueError):
                                        numeric_value = math.nan
                                    if isinstance(keyframe_value.get("value"), bool) or not math.isfinite(numeric_value):
                                        error("CROP_KEYFRAME_VALUE_INVALID", "crop keyframe value 必须是有限数字", f"{keyframe_path}.value")
                                    elif normalized_name in {"width", "w", "height", "h"} and numeric_value <= 0:
                                        error("CROP_KEYFRAME_RANGE", "crop width/height 关键帧必须大于 0", f"{keyframe_path}.value")
                                    elif numeric_value < 0 or crop_unit in {"normalized", "relative"} and numeric_value > 1:
                                        error("CROP_KEYFRAME_RANGE", "crop 坐标和尺寸关键帧必须位于合法范围", f"{keyframe_path}.value")

                        validate_crop_keyframes(crop.get("keyframes"), f"{cp}.crop.keyframes")
                        validate_crop_keyframes(clip_crop_tracks, f"{cp}.keyframes")
                effects = clip.get("effects")
                if effects is not None:
                    if not isinstance(effects, list):
                        error("EFFECTS_INVALID", "effects 必须是数组", f"{cp}.effects")
                    else:
                        for effect_index, effect_value in enumerate(effects):
                            effect_path = f"{cp}.effects[{effect_index}]"
                            if isinstance(effect_value, str):
                                continue
                            if not isinstance(effect_value, dict):
                                error("EFFECT_INVALID", "效果必须是字符串或对象", effect_path)
                                continue
                            effect_type = str(effect_value.get("type", "")).lower().replace("-", "_")
                            parameters = effect_value.get("parameters") if isinstance(effect_value.get("parameters"), dict) else effect_value
                            validate_lut_resource(effect_value, effect_path)
                            for finding in validate_effect_automation(effect_value, duration_tick=authored_dur):
                                error(finding['code'], finding['message'], effect_path+finding['suffix'])
                            raw_effect_tracks = effect_value.get("keyframes")
                            if not isinstance(raw_effect_tracks, list):
                                raw_effect_tracks = parameters.get("keyframes") if isinstance(parameters.get("keyframes"), list) else []
                            if not raw_effect_tracks:
                                continue
                            supported_properties = effect_properties(effect_type)
                            for track_index, track_value in enumerate(raw_effect_tracks):
                                track_path = f"{effect_path}.keyframes[{track_index}]"
                                if not isinstance(track_value, dict):
                                    error("EFFECT_KEYFRAMES_INVALID", "效果 keyframe track 必须是对象", track_path)
                                    continue
                                property_name = str(track_value.get("property", "")).strip().lower().replace("-", "_")
                                for prefix in ("effect.", "parameters.", f"{effect_type}.") if effect_type else ("effect.", "parameters."):
                                    if property_name.startswith(prefix):
                                        property_name = property_name[len(prefix):]
                                        break
                                if not property_name:
                                    error("EFFECT_KEYFRAME_PROPERTY_INVALID", "效果 keyframe property 不能为空", f"{track_path}.property")
                                elif supported_properties is None or property_name not in supported_properties:
                                    warning("EFFECT_KEYFRAME_PROPERTY_UNSUPPORTED", "该效果参数关键帧不会逐帧执行，将使用静态参数值", f"{track_path}.property")
                                keyframes = track_value.get("keyframes")
                                if not isinstance(keyframes, list) or not keyframes:
                                    error("EFFECT_KEYFRAMES_INVALID", "效果 keyframe track 必须包含非空 keyframes", f"{track_path}.keyframes")
                                    continue
                                previous_at = -1
                                for keyframe_index, keyframe_value in enumerate(keyframes):
                                    keyframe_path = f"{track_path}.keyframes[{keyframe_index}]"
                                    if not isinstance(keyframe_value, dict):
                                        error("EFFECT_KEYFRAMES_INVALID", "效果 keyframe 必须是对象", keyframe_path)
                                        continue
                                    at = _int(keyframe_value.get("at_tick"), -1)
                                    if at < 0 or at > authored_dur or at < previous_at:
                                        error("EFFECT_KEYFRAME_TIME_INVALID", "效果 keyframe at_tick 必须单调且位于片段内", f"{keyframe_path}.at_tick")
                                    previous_at = at
                                    interpolation = keyframe_value.get("interpolation")
                                    if interpolation not in {"hold", "linear", "ease_in", "ease_out", "ease_in_out", "bezier"}:
                                        error("INTERPOLATION_INVALID", "效果关键帧插值类型无效", f"{keyframe_path}.interpolation")
                                    if interpolation == "bezier":
                                        controls = keyframe_value.get("control_points")
                                        if not isinstance(controls, list) or len(controls) not in {2, 4} or any(not finite_effect_number(value) for value in controls):
                                            error("BEZIER_CONTROL_POINTS_INVALID", "效果 Bezier 控制点必须是 2 或 4 个有限数字", f"{keyframe_path}.control_points")
                                        elif len(controls) == 4 and not (0.0 <= controls[0] <= 1.0 and 0.0 <= controls[2] <= 1.0):
                                            error("BEZIER_CONTROL_POINT_RANGE", "效果 Bezier 控制点 x 必须位于 0 到 1", f"{keyframe_path}.control_points")
                                    value = keyframe_value.get("value")
                                    try:
                                        numeric_value = float(value)
                                    except (TypeError, ValueError, OverflowError):
                                        numeric_value = math.nan
                                    if isinstance(value, bool) or not math.isfinite(numeric_value):
                                        error("EFFECT_KEYFRAME_VALUE_INVALID", "效果关键帧 value 必须是有限数字", f"{keyframe_path}.value")
                for transition_field in ("transition_in", "transition_out"):
                    transition_value = clip.get(transition_field)
                    if transition_value is None:
                        continue
                    if not isinstance(transition_value, dict):
                        error("TRANSITION_INVALID", f"{transition_field} 必须是对象", f"{cp}.{transition_field}")
                        continue
                    transition_type = str(transition_value.get("type", "")).lower().replace("-", "_")
                    if transition_type not in TRANSITION_TYPES:
                        error("TRANSITION_UNSUPPORTED", f"不支持的转场类型: {transition_type}", f"{cp}.{transition_field}.type")
                    try:
                        transition_duration = float(transition_value.get("duration", 0.25))
                    except (TypeError, ValueError):
                        transition_duration = math.nan
                    if not math.isfinite(transition_duration) or transition_duration <= 0:
                        error("TRANSITION_DURATION_INVALID", "转场 duration 必须是有限正数", f"{cp}.{transition_field}.duration")
                    if "auto_handle" in transition_value and not isinstance(transition_value.get("auto_handle"), bool):
                        error("TRANSITION_AUTO_HANDLE_INVALID", "转场 auto_handle 必须是布尔值", f"{cp}.{transition_field}.auto_handle")
                    handle_policy = transition_value.get("handle_policy")
                    if handle_policy is not None and str(handle_policy).lower() not in {"manual", "auto"}:
                        error("TRANSITION_HANDLE_POLICY_INVALID", "转场 handle_policy 只能是 manual 或 auto", f"{cp}.{transition_field}.handle_policy")
                occupied.append((start, start + dur, str(cid)))
                for old_start, old_end, old_id in occupied[:-1]:
                    if start < old_end and old_start < start + dur and track.get("overlap_policy") != "allow":
                        error("TRACK_OVERLAP", f"轨道片段重叠: {old_id} 与 {cid}", cp)
                for keyframe_track in clip.get("keyframes", []):
                    previous = -1
                    for keyframe in keyframe_track.get("keyframes", []):
                        property_name = str(keyframe_track.get("property", ""))
                        if property_name in {"transform.opacity", "opacity", "blend.opacity", "blend_opacity"}:
                            value = keyframe.get("value")
                            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                                error("OPACITY_KEYFRAME_INVALID", "透明度关键帧 value 必须是有限数字", f"{cp}.keyframes")
                            elif not 0.0 <= value <= 1.0:
                                error("OPACITY_KEYFRAME_RANGE", "透明度关键帧 value 必须位于 0 到 1", f"{cp}.keyframes")
                        if property_name in {"audio.pan", "pan"}:
                            value = keyframe.get("value")
                            try:
                                pan_value = float(value)
                            except (TypeError, ValueError):
                                pan_value = math.nan
                            if isinstance(value, bool) or not math.isfinite(pan_value):
                                error("PAN_KEYFRAME_INVALID", "声像关键帧 value 必须是有限数字", f"{cp}.keyframes")
                            elif not -1.0 <= pan_value <= 1.0:
                                error("PAN_KEYFRAME_RANGE", "声像关键帧 value 必须位于 -1 到 1", f"{cp}.keyframes")
                        if property_name in {'audio.volume','volume'}:
                            value=keyframe.get('value')
                            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not 0 <= value <= 4:
                                error('AUDIO_VOLUME_KEYFRAME_INVALID','音量关键帧必须是 0..4 的有限数字',f'{cp}.keyframes')
                        if property_name in {"transform.anchor.x", "anchor.x", "anchor_x", "transform.anchor.y", "anchor.y", "anchor_y"}:
                            value = keyframe.get("value")
                            try:
                                anchor_value = float(value)
                            except (TypeError, ValueError):
                                anchor_value = math.nan
                            if isinstance(value, bool) or not math.isfinite(anchor_value):
                                error("TRANSFORM_ANCHOR_KEYFRAME_INVALID", "锚点关键帧 value 必须是有限数字", f"{cp}.keyframes")
                            elif not 0.0 <= anchor_value <= 1.0:
                                error("TRANSFORM_ANCHOR_KEYFRAME_RANGE", "锚点关键帧 value 必须位于 0 到 1", f"{cp}.keyframes")
                        at = _int(keyframe.get("at_tick"), -1)
                        if at < previous or at > authored_dur:
                            error("KEYFRAME_INVALID", "关键帧必须单调且位于片段内", f"{cp}.keyframes")
                        interpolation = keyframe.get("interpolation")
                        if interpolation not in {"hold", "linear", "ease_in", "ease_out", "ease_in_out", "bezier"}:
                            error("INTERPOLATION_INVALID", "关键帧插值类型无效", f"{cp}.keyframes")
                        if interpolation == "bezier":
                            controls = keyframe.get("control_points")
                            kp_path = f"{cp}.keyframes"
                            if not isinstance(controls, list):
                                error("BEZIER_CONTROL_POINTS_MISSING", "Bezier 关键帧必须提供 control_points", kp_path)
                            elif len(controls) not in {2, 4}:
                                error("BEZIER_CONTROL_POINTS_INVALID", "Bezier control_points 必须是 2 个纵向控制值或 4 个归一化 x/y 控制值", kp_path)
                            else:
                                numeric = True
                                for control_index, value in enumerate(controls):
                                    if isinstance(value, bool):
                                        numeric = False
                                        break
                                    try:
                                        number = float(value)
                                    except (TypeError, ValueError):
                                        numeric = False
                                        break
                                    if not math.isfinite(number):
                                        numeric = False
                                        break
                                    if len(controls) == 4 and control_index in {0, 2} and not 0.0 <= number <= 1.0:
                                        error("BEZIER_CONTROL_POINT_RANGE", "Bezier 四元控制点中的 x 必须位于 0 到 1", kp_path)
                                if not numeric:
                                    error("BEZIER_CONTROL_POINTS_INVALID", "Bezier control_points 必须全部是有限数字", kp_path)
                        previous = at
                mask = clip.get("mask")
                if mask is not None:
                    if not isinstance(mask, dict):
                        error("MASK_INVALID", "mask 必须是对象", f"{cp}.mask")
                    else:
                        mask_type = str(mask.get("type", "rectangle")).lower().replace("-", "_")
                        if mask_type not in {"none", "rectangle", "circle", "ellipse", "path", "polygon"}:
                            error("MASK_TYPE_UNSUPPORTED", "mask.type 只支持 none、rectangle、circle、ellipse、path、polygon", f"{cp}.mask.type")
                        if mask_type in {"path", "polygon"}:
                            points = mask.get("points")
                            curve_segments = mask.get("segments", mask.get("curve_segments", mask.get("curves")))
                            if curve_segments is not None:
                                if points is not None:
                                    error("MASK_PATH_INVALID", "path/polygon 不能同时声明 points 和曲线 segments", f"{cp}.mask")
                                if not isinstance(curve_segments, list) or not curve_segments:
                                    error("MASK_PATH_INVALID", "曲线路径 segments 必须是非空数组", f"{cp}.mask.segments")
                                else:
                                    estimated_points = 1
                                    for segment_index, segment in enumerate(curve_segments):
                                        segment_path = f"{cp}.mask.segments[{segment_index}]"
                                        if not isinstance(segment, dict):
                                            error("MASK_PATH_INVALID", "曲线路径段必须是对象", segment_path)
                                            continue
                                        segment_type = str(segment.get("type", "cubic")).lower().replace("-", "_")
                                        if segment_type in {"line", "linear"}:
                                            point_names = (("from", "p0", "start"), ("to", "p1", "end"))
                                            estimated_points += 1
                                        elif segment_type in {"cubic", "bezier", "cubic_bezier"}:
                                            point_names = (("from", "p0", "start"), ("control1", "p1", "c1"), ("control2", "p2", "c2"), ("to", "p3", "end"))
                                            try:
                                                samples = int(segment.get("samples", 8))
                                            except (TypeError, ValueError):
                                                samples = -1
                                            if samples < 2 or samples > 16:
                                                error("MASK_PATH_INVALID", "cubic 曲线 samples 必须位于 2 到 16", f"{segment_path}.samples")
                                            estimated_points += max(2, min(16, samples if samples >= 2 else 2))
                                        else:
                                            error("MASK_PATH_INVALID", "曲线路径段 type 只支持 line 或 cubic", f"{segment_path}.type")
                                            continue
                                        for aliases in point_names:
                                            raw_point = next((segment[name] for name in aliases if name in segment), None)
                                            values = (raw_point.get("x"), raw_point.get("y")) if isinstance(raw_point, dict) else (raw_point[0], raw_point[1]) if isinstance(raw_point, (list, tuple)) and len(raw_point) >= 2 else (None, None)
                                            for axis, value in zip(("x", "y"), values):
                                                try:
                                                    number = float(value)
                                                except (TypeError, ValueError):
                                                    error("MASK_PATH_INVALID", f"曲线路径段 {segment_index} 的 {axis} 必须是数字", segment_path)
                                                    continue
                                                if not math.isfinite(number) or not 0.0 <= number <= 1.0:
                                                    error("MASK_PATH_INVALID", f"曲线路径段 {segment_index} 的 {axis} 必须位于 0 到 1", segment_path)
                                    if estimated_points < 3 or estimated_points > 32:
                                        error("MASK_PATH_INVALID", "曲线路径采样点数必须位于 3 到 32", f"{cp}.mask.segments")
                            elif not isinstance(points, list) or len(points) < 3:
                                error("MASK_PATH_INVALID", "path/polygon 遮罩至少需要三个点或有效曲线 segments", f"{cp}.mask.points")
                            elif len(points) > 32:
                                error("MASK_PATH_INVALID", "path/polygon 遮罩最多支持 32 个点", f"{cp}.mask.points")
                            else:
                                for point_index, point in enumerate(points):
                                    values = (point.get("x"), point.get("y")) if isinstance(point, dict) else (point[0], point[1]) if isinstance(point, (list, tuple)) and len(point) >= 2 else (None, None)
                                    for axis, value in zip(("x", "y"), values):
                                        try:
                                            number = float(value)
                                        except (TypeError, ValueError):
                                            error("MASK_PATH_INVALID", f"path 点 {point_index} 的 {axis} 必须是数字", f"{cp}.mask.points[{point_index}]")
                                            continue
                                        if not math.isfinite(number) or not 0.0 <= number <= 1.0:
                                            error("MASK_PATH_INVALID", f"path 点 {point_index} 的 {axis} 必须位于 0 到 1", f"{cp}.mask.points[{point_index}]")
                        for field in ("x", "y", "width", "height", "cx", "cy", "radius", "rx", "ry", "feather"):
                            if field not in mask:
                                continue
                            try:
                                value = float(mask[field])
                            except (TypeError, ValueError):
                                error("MASK_PARAMETER_INVALID", f"mask.{field} 必须是有限数字", f"{cp}.mask.{field}")
                                continue
                            if not math.isfinite(value):
                                error("MASK_PARAMETER_INVALID", f"mask.{field} 必须是有限数字", f"{cp}.mask.{field}")
                            elif field != "feather" and not 0.0 <= value <= 1.0:
                                error("MASK_PARAMETER_RANGE", f"mask.{field} 必须位于 0 到 1", f"{cp}.mask.{field}")
                            elif field == "feather" and not 0.0 <= value <= 0.5:
                                error("MASK_PARAMETER_RANGE", "mask.feather 必须位于 0 到 0.5", f"{cp}.mask.{field}")
                        if "invert" in mask and not isinstance(mask.get("invert"), bool):
                            error("MASK_PARAMETER_INVALID", "mask.invert 必须是布尔值", f"{cp}.mask.invert")
                        mask_keyframe_aliases = {
                            "x", "y", "width", "height", "w", "h", "cx", "cy", "center_x", "center_y",
                            "radius", "rx", "ry", "radius_x", "radius_y",
                            "mask.x", "mask.y", "mask.width", "mask.height", "mask.w", "mask.h",
                            "mask.cx", "mask.cy", "mask.center_x", "mask.center_y", "mask.radius",
                            "mask.rx", "mask.ry", "mask.radius_x", "mask.radius_y", "feather", "mask.feather",
                            "mask.position.x", "mask.position.y",
                        }

                        def validate_mask_keyframes(tracks: Any, tracks_path: str) -> None:
                            if tracks is None:
                                return
                            if not isinstance(tracks, list):
                                error("MASK_KEYFRAMES_INVALID", "mask keyframes 必须是数组", tracks_path)
                                return
                            for track_index, track_value in enumerate(tracks):
                                track_path = f"{tracks_path}[{track_index}]"
                                if not isinstance(track_value, dict):
                                    error("MASK_KEYFRAMES_INVALID", "mask keyframe track 必须是对象", track_path)
                                    continue
                                property_name = str(track_value.get("property", ""))
                                point_match = re.fullmatch(r"(?:mask\.)?(?:points|point)(?:\.(\d+)|\[(\d+)\])\.(?:x|y)", property_name)
                                dynamic_point_property = point_match is not None
                                segment_match = re.fullmatch(r"(?:mask\.)?(?:segments|curve_segments|curves)\.(\d+)\.(from|p0|start|control1|p1|c1|control2|p2|c2|to|p3|end)\.(x|y)", property_name)
                                dynamic_segment_property = segment_match is not None
                                if property_name not in mask_keyframe_aliases and not dynamic_point_property and not dynamic_segment_property:
                                    error("MASK_KEYFRAME_PROPERTY_UNSUPPORTED", "mask keyframe property 不是受支持的几何或羽化属性", f"{track_path}.property")
                                normalized_property_name = property_name.removeprefix("mask.")
                                if normalized_property_name == "feather" and mask_type not in {"rectangle", "circle", "ellipse", "path", "polygon"}:
                                    error("MASK_KEYFRAME_PROPERTY_UNSUPPORTED", "动态 feather 目前只支持 rectangle、circle、ellipse、path、polygon 遮罩", f"{track_path}.property")
                                if point_match:
                                    point_count = len(mask.get("points", [])) if isinstance(mask.get("points"), list) else 0
                                    if mask_type not in {"path", "polygon"} or int(point_match.group(1) or point_match.group(2)) >= point_count:
                                        error("MASK_KEYFRAME_POINT_INVALID", "mask 点坐标关键帧必须引用已有 path/polygon 顶点", f"{track_path}.property")
                                if segment_match:
                                    segment_values = mask.get("segments", mask.get("curve_segments", mask.get("curves")))
                                    segment_index = int(segment_match.group(1))
                                    point_name = segment_match.group(2)
                                    if mask_type not in {"path", "polygon"} or not isinstance(segment_values, list) or segment_index >= len(segment_values):
                                        error("MASK_KEYFRAME_SEGMENT_INVALID", "mask 曲线关键帧必须引用已有 path/polygon 曲线段", f"{track_path}.property")
                                    elif isinstance(segment_values[segment_index], dict):
                                        segment_type = str(segment_values[segment_index].get("type", "cubic")).lower().replace("-", "_")
                                        allowed_points = {"from", "p0", "start", "to", "p1", "end"} if segment_type in {"line", "linear"} else {"from", "p0", "start", "control1", "p1", "c1", "control2", "p2", "c2", "to", "p3", "end"}
                                        if point_name not in allowed_points:
                                            error("MASK_KEYFRAME_SEGMENT_POINT_INVALID", "曲线段关键帧引用的控制点与段类型不匹配", f"{track_path}.property")
                                keyframes = track_value.get("keyframes")
                                if not isinstance(keyframes, list) or not keyframes:
                                    error("MASK_KEYFRAMES_INVALID", "mask keyframe track 必须包含非空 keyframes", f"{track_path}.keyframes")
                                    continue
                                previous_at = -1
                                for keyframe_index, keyframe_value in enumerate(keyframes):
                                    keyframe_path = f"{track_path}.keyframes[{keyframe_index}]"
                                    if not isinstance(keyframe_value, dict):
                                        error("MASK_KEYFRAMES_INVALID", "mask keyframe 必须是对象", keyframe_path)
                                        continue
                                    at = _int(keyframe_value.get("at_tick"), -1)
                                    if at < 0 or at > authored_dur or at < previous_at:
                                        error("MASK_KEYFRAME_TIME_INVALID", "mask keyframe at_tick 必须单调且位于片段内", f"{keyframe_path}.at_tick")
                                    previous_at = at
                                    interpolation = keyframe_value.get("interpolation")
                                    if interpolation not in {"hold", "linear", "ease_in", "ease_out", "ease_in_out", "bezier"}:
                                        error("INTERPOLATION_INVALID", "mask 关键帧插值类型无效", f"{keyframe_path}.interpolation")
                                    if interpolation == "bezier":
                                        controls = keyframe_value.get("control_points")
                                        if not isinstance(controls, list) or len(controls) not in {2, 4} or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in controls):
                                            error("BEZIER_CONTROL_POINTS_INVALID", "mask Bezier 控制点必须为 2 或 4 个有限数字", f"{keyframe_path}.control_points")
                                        elif len(controls) == 4 and not (0.0 <= controls[0] <= 1.0 and 0.0 <= controls[2] <= 1.0):
                                            error("BEZIER_CONTROL_POINT_RANGE", "Bezier x 控制点必须位于 0 到 1", f"{keyframe_path}.control_points")
                                    try:
                                        numeric_value = float(keyframe_value.get("value"))
                                    except (TypeError, ValueError):
                                        numeric_value = math.nan
                                    if isinstance(keyframe_value.get("value"), bool) or not math.isfinite(numeric_value):
                                        error("MASK_KEYFRAME_VALUE_INVALID", "mask keyframe value 必须是有限数字", f"{keyframe_path}.value")
                                    else:
                                        normalized_name = property_name.removeprefix("mask.")
                                        if normalized_name not in {"feather"} and not 0.0 <= numeric_value <= 1.0:
                                            error("MASK_KEYFRAME_RANGE", "mask 几何关键帧 value 必须位于 0 到 1", f"{keyframe_path}.value")
                                        elif normalized_name == "feather" and not 0.0 <= numeric_value <= 0.5:
                                            error("MASK_KEYFRAME_RANGE", "mask.feather 关键帧 value 必须位于 0 到 0.5", f"{keyframe_path}.value")

                        clip_mask_tracks = [
                            item for item in clip.get("keyframes", [])
                            if isinstance(item, dict) and (
                                str(item.get("property", "")).startswith("mask.")
                                        or str(item.get("property", "")) in mask_keyframe_aliases | {"feather"}
                                or re.fullmatch(r"(?:points|point)(?:\.\d+|\[\d+\])\.(?:x|y)", str(item.get("property", "")))
                                or re.fullmatch(r"(?:segments|curve_segments|curves)\.\d+\.(?:from|p0|start|control1|p1|c1|control2|p2|c2|to|p3|end)\.(?:x|y)", str(item.get("property", "")))
                            )
                        ]
                        validate_mask_keyframes(clip_mask_tracks, f"{cp}.keyframes")
                        validate_mask_keyframes(mask.get("keyframes"), f"{cp}.mask.keyframes")
                blend = clip.get("blend")
                if blend is not None:
                    if not isinstance(blend, dict):
                        error("BLEND_INVALID", "blend 必须是对象", f"{cp}.blend")
                    else:
                        mode = str(blend.get("mode", "normal")).lower().replace("-", "_")
                        allowed_modes = {"normal", "source_over", "addition", "addition128", "and", "average", "burn", "darken", "difference", "divide", "dodge", "exclusion", "freeze", "glow", "hardlight", "hard_mix", "lighten", "multiply", "negation", "or", "phoenix", "pinlight", "reflect", "screen", "softlight", "subtract", "vivid", "xor"}
                        if mode not in allowed_modes:
                            error("BLEND_MODE_UNSUPPORTED", "blend.mode 不是本地 FFmpeg 支持的模式", f"{cp}.blend.mode")
                        if 'opacity_animation' in blend:
                            from .blend_automation import OpacityClock
                            try:
                                OpacityClock(blend['opacity_animation'], project['settings'])
                            except AppError as exc:
                                error(exc.code, exc.message, f'{cp}.blend.opacity_animation')
                        if "opacity" in blend:
                            try:
                                opacity = float(blend["opacity"])
                            except (TypeError, ValueError):
                                error("BLEND_OPACITY_INVALID", "blend.opacity 必须是有限数字", f"{cp}.blend.opacity")
                            else:
                                if not math.isfinite(opacity) or not 0.0 <= opacity <= 1.0:
                                    error("BLEND_OPACITY_RANGE", "blend.opacity 必须位于 0 到 1", f"{cp}.blend.opacity")
                audio_settings = clip.get("audio")
                if isinstance(audio_settings,dict):validate_audio_processing(audio_settings,f'{cp}.audio')
                if audio_settings is not None:
                    if not isinstance(audio_settings, dict):
                        error("AUDIO_INVALID", "audio 必须是对象", f"{cp}.audio")
                    elif "pan" in audio_settings and audio_settings.get("pan") is not None:
                        raw_pan = audio_settings.get("pan")
                        try:
                            static_pan = float(raw_pan)
                        except (TypeError, ValueError):
                            static_pan = math.nan
                        # Preserve the existing raw FFmpeg pan syntax while
                        # making numeric pan deterministic and range checked.
                        if isinstance(raw_pan, str) and "|" in raw_pan:
                            static_pan = 0.0
                        if not math.isfinite(static_pan) or not -1.0 <= static_pan <= 1.0:
                            if not (isinstance(raw_pan, str) and "|" in raw_pan):
                                error("PAN_RANGE", "audio.pan 必须是 -1 到 1 的数字或 FFmpeg pan 表达式", f"{cp}.audio.pan")
                subtitle = clip.get("subtitle")
                if subtitle is not None:
                    if not isinstance(subtitle, dict):
                        error("SUBTITLE_INVALID", "subtitle 必须是对象", f"{cp}.subtitle")
                    else:
                        style = subtitle.get("style") if isinstance(subtitle.get("style"), dict) else {}
                        subtitle_time_base = subtitle.get('asset_time_base', 'sequence')
                        if not isinstance(subtitle_time_base, str) or subtitle_time_base not in {'sequence', 'clip'}:
                            error('SUBTITLE_ASSET_TIME_BASE_INVALID', 'asset_time_base 只支持 sequence 或 clip', f'{cp}.subtitle.asset_time_base')
                        subtitle_numeric_ranges = {
                            "fontsize": (1.0, 4096.0),
                            "line_spacing": (-2000.0, 2000.0),
                            "borderw": (0.0, 100.0),
                            "shadowx": (-2000.0, 2000.0),
                            "shadowy": (-2000.0, 2000.0),
                            "boxw": (0.0, 10000.0),
                            "boxh": (0.0, 10000.0),
                            "boxborderw": (0.0, 1000.0),
                            "box_padding": (0.0, 1000.0),
                            "tabsize": (0.0, 256.0),
                            "max_width": (1.0, 100000.0),
                            "wrap_width": (1.0, 100000.0),
                        }
                        for style_key, (style_low, style_high) in subtitle_numeric_ranges.items():
                            if style_key not in style:
                                continue
                            raw_style_value = style.get(style_key)
                            try:
                                style_number = float(raw_style_value)
                            except (TypeError, ValueError):
                                style_number = math.nan
                            if isinstance(raw_style_value, bool) or not math.isfinite(style_number) or not style_low <= style_number <= style_high:
                                error("SUBTITLE_STYLE_RANGE", f"字幕 style.{style_key} 必须位于 {style_low:g} 到 {style_high:g}", f"{cp}.subtitle.style.{style_key}")
                        text_align_value = style.get("text_align", style.get("align"))
                        if text_align_value is not None:
                            align_tokens = [token.strip().lower() for token in re.split(r"[+|, ]+", str(text_align_value)) if token.strip()]
                            allowed_align = {"left", "right", "center", "top", "bottom", "middle", "l", "r", "c", "t", "b", "m"}
                            if not align_tokens or any(token not in allowed_align for token in align_tokens):
                                error("SUBTITLE_ALIGN_UNSUPPORTED", "字幕 text_align 方向无效", f"{cp}.subtitle.style.text_align")
                        expansion_value = style.get("expansion")
                        if expansion_value is not None and str(expansion_value).lower() not in {"none", "normal", "strftime"}:
                            error("SUBTITLE_EXPANSION_UNSUPPORTED", "字幕 expansion 只支持 none、normal 或 strftime", f"{cp}.subtitle.style.expansion")
                        font_asset_id = style.get("font_asset_id")
                        if font_asset_id is not None:
                            font_asset = asset_map(project).get(str(font_asset_id))
                            if not font_asset or font_asset.get("kind") != "font":
                                error("SUBTITLE_FONT_REFERENCE_INVALID", "font_asset_id 必须引用 font 资产", f"{cp}.subtitle.style.font_asset_id")
                        fontfile = style.get("fontfile")
                        if fontfile is not None:
                            if reference_kind(fontfile) in {"remote", "provider"}:
                                error("SUBTITLE_FONT_REMOTE", "字幕 fontfile 只允许本地路径", f"{cp}.subtitle.style.fontfile")
                            else:
                                font_path = resolve_local_path(root, fontfile, field=f"{cp}.subtitle.style.fontfile")
                                if not font_path.is_file():
                                    error("SUBTITLE_FONT_MISSING", "字幕 fontfile 不存在", f"{cp}.subtitle.style.fontfile")
                        word_timing = subtitle.get("word_timing")
                        if word_timing is not None:
                            if not isinstance(word_timing, list):
                                error("SUBTITLE_WORD_TIMING_INVALID", "word_timing 必须是数组", f"{cp}.subtitle.word_timing")
                            else:
                                previous_word_end = -1.0
                                for word_index, word_item in enumerate(word_timing):
                                    if not isinstance(word_item, dict):
                                        error("SUBTITLE_WORD_TIMING_INVALID", "word_timing 项必须是对象", f"{cp}.subtitle.word_timing[{word_index}]")
                                        continue
                                    start_char = word_item.get("start_char")
                                    if start_char is not None and (isinstance(start_char, bool) or not isinstance(start_char, int) or start_char < 0):
                                        error("SUBTITLE_WORD_INDEX_INVALID", "word_timing start_char 必须是非负整数", f"{cp}.subtitle.word_timing[{word_index}].start_char")
                                    start_value = word_item.get("start", word_item.get("start_seconds"))
                                    end_value = word_item.get("end", word_item.get("end_seconds"))
                                    if start_value is None and word_item.get("start_tick") is not None:
                                        start_value = _int(word_item.get("start_tick"), -1)
                                        end_value = _int(word_item.get("end_tick"), -1)
                                    try:
                                        start_number = float(start_value)
                                        end_number = float(end_value)
                                    except (TypeError, ValueError):
                                        start_number, end_number = -1.0, -1.0
                                    if not math.isfinite(start_number) or not math.isfinite(end_number) or start_number < 0 or end_number <= start_number or start_number < previous_word_end:
                                        error("SUBTITLE_WORD_TIMING_INVALID", "word_timing 必须是单调的正时间范围", f"{cp}.subtitle.word_timing[{word_index}]")
                                    previous_word_end = end_number
                        animation = subtitle.get("animation") if isinstance(subtitle.get("animation"), dict) else style.get("animation") if isinstance(style.get("animation"), dict) else None
                        if animation is not None:
                            animation_type = str(animation.get("type", "")).lower().replace("-", "_")
                            if animation_type not in {"fade_in", "fade_out", "fade", "slide_up", "slide_down", "slide_left", "slide_right", "typewriter", "typing", "pop", "bounce", "rotate"}:
                                error("SUBTITLE_ANIMATION_UNSUPPORTED", "字幕动画类型无效", f"{cp}.subtitle.animation.type")
                            if "duration" in animation:
                                try:
                                    animation_duration = float(animation["duration"])
                                except (TypeError, ValueError):
                                    error("SUBTITLE_ANIMATION_DURATION_INVALID", "字幕动画 duration 必须是有限正数", f"{cp}.subtitle.animation.duration")
                                else:
                                    if not math.isfinite(animation_duration) or animation_duration <= 0:
                                        error("SUBTITLE_ANIMATION_DURATION_INVALID", "字幕动画 duration 必须是有限正数", f"{cp}.subtitle.animation.duration")
                            if animation_type == "rotate":
                                for angle_key in ("from_degrees", "to_degrees", "from", "to", "angle", "degrees"):
                                    if angle_key not in animation:
                                        continue
                                    try:
                                        angle_value = float(animation[angle_key])
                                    except (TypeError, ValueError):
                                        angle_value = math.nan
                                    if isinstance(animation[angle_key], bool) or not math.isfinite(angle_value) or abs(angle_value) > 3600:
                                        error("SUBTITLE_ROTATION_INVALID", "字幕旋转角度必须是绝对值不超过 3600 的有限数字", f"{cp}.subtitle.animation.{angle_key}")
                                if "delay" in animation:
                                    try:
                                        delay = float(animation["delay"])
                                    except (TypeError, ValueError):
                                        delay = math.nan
                                    if isinstance(animation["delay"], bool) or not math.isfinite(delay) or delay < 0:
                                        error("SUBTITLE_ANIMATION_DELAY_INVALID", "字幕动画 delay 必须是有限非负数字", f"{cp}.subtitle.animation.delay")
        if not sequence.get("tracks"):
            warning("SEQUENCE_EMPTY", "序列没有轨道", sp)

    sequence_map = {str(item.get("id")): item for item in project.get("sequences", []) if item.get("id")}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit_sequence(sequence_id: str, path: str) -> None:
        if sequence_id in visiting:
            error("SEQUENCE_CYCLE", "嵌套序列存在循环引用", path)
            return
        if sequence_id in visited:
            return
        sequence_value = sequence_map.get(sequence_id)
        if not sequence_value:
            return
        visiting.add(sequence_id)
        for track_value in sequence_value.get("tracks", []):
            for clip_value in track_value.get("clips", []):
                child_id = clip_value.get("sequence_id")
                if child_id:
                    visit_sequence(str(child_id), f"{path}.tracks[].clips[{clip_value.get('id')}].sequence_id")
        visiting.remove(sequence_id)
        visited.add(sequence_id)

    for sequence_id in sequence_map:
        visit_sequence(sequence_id, f"sequences[{sequence_id}]")

    from .bindings import validate_project_bindings
    errors.extend(validate_project_bindings(project,root))
    rights = check_project_rights(project, load_ledger(root) if rights_ledger is None else rights_ledger, target, strict=strict_rights)
    if strict_rights:
        errors.extend({**item, "path": f"rights[{item.get('asset_id')}]"} for item in rights.get("failures", []))
    else:
        warnings.extend(rights.get("warnings", []))
    return {"ok": not errors, "errors": errors, "warnings": warnings, "rights": rights, "schema_engine": schema_engine, "asset_count": len(project.get("assets", [])), "sequence_count": len(project.get("sequences", []))}
