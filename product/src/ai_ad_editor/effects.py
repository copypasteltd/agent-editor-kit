"""Local FFmpeg effect catalog exposed to Agent planners.

The catalog is deliberately data-first: it documents the canonical effect id,
the local FFmpeg filter used by the renderer, supported parameters, and the
current keyframe contract.  It does not download assets or call a remote
registry, so an Agent can plan against the exact capabilities of this build.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from .effect_automation import SPECS as AUTOMATION_SPECS
from .selective_hsl import SPECS as HSL_SPECS, ENGINE as HSL_ENGINE


EFFECT_CATALOG_VERSION = "0.11.0"


def _parameter(
    kind: str,
    default: Any,
    *,
    minimum: float | int | None = None,
    maximum: float | int | None = None,
    description: str = "",
) -> dict[str, Any]:
    item: dict[str, Any] = {"type": kind, "default": default}
    if minimum is not None:
        item["minimum"] = minimum
    if maximum is not None:
        item["maximum"] = maximum
    if description:
        item["description"] = description
    return item


def _effect(
    effect_id: str,
    *,
    backend: str,
    category: str,
    aliases: tuple[str, ...] = (),
    keyframable: bool = False,
    parameters: dict[str, dict[str, Any]] | None = None,
    limits: tuple[str, ...] = (),
) -> dict[str, Any]:
    item = {
        "id": effect_id,
        "aliases": list(aliases),
        "category": category,
        "backend": backend,
        "source": "ffmpeg-local",
        "license": "inherit-local-ffmpeg-build",
        "keyframable": keyframable,
        "parameters": parameters or {},
        "limits": list(limits),
    }
    if effect_id in AUTOMATION_SPECS:
        item.update(keyframable=True,
                    keyframe_parameters=list(AUTOMATION_SPECS[effect_id]),
                    keyframe_engine='native-color-command-cfr-v1')
        item['limits'].extend(['numeric_channels_only_bool_and_enum_stay_static',
                               'complete_author_clock_at_CFR_samples',
                               'recursive_command_and_sampling_budgets'])
    if effect_id == 'selective_hsl':
        item.update(keyframable=True, keyframe_parameters=list(HSL_SPECS), keyframe_engine=HSL_ENGINE)
        item.update(fallback_backends=['ffmpeg:geq'],backend_selection='verified-native-auto',
                    implementation_license='MIT (original C kernel)',implementation_license_file='NATIVE_HSL_LICENSE.txt')
    if effect_id in {'curves', 'rgb_curves'}:
        item.update(keyframable=True, keyframe_engine='native-curve-points-cfr-v1',
                    keyframe_parameters=[f'{c}.<index>.{axis}' for c in (('all',) if effect_id == 'curves' else ('all', 'red', 'green', 'blue')) for axis in ('x', 'y')],
                    keyframe_point_index={'minimum': 0, 'maximum': 255, 'topology': 'static-point-count'},
                    keyframe_coordinate_range=[0, 1])
    return item


_EFFECTS: tuple[dict[str, Any], ...] = (
    _effect("avgblur", backend="ffmpeg:avgblur", category="blur", aliases=("average_blur",), parameters={
        "size_x": _parameter("number", 2.0, minimum=1.0, maximum=1024.0),
        "size_y": _parameter("number", 2.0, minimum=0.0, maximum=1024.0),
        "planes": _parameter("integer", 15, minimum=0, maximum=15),
    }),
    _effect("blur", backend="ffmpeg:gblur", category="blur", aliases=("gaussian_blur", "gblur"), parameters={"radius": _parameter("number", 4.0, minimum=0.0, maximum=128.0)}, limits=("radius_sets_both_sigma_and_sigmaV", "blur_filters_RGB_and_alpha_planes")),
    _effect("box_blur", backend="ffmpeg:boxblur", category="blur", aliases=("boxblur",), parameters={
        "radius": _parameter("number", 4.0, minimum=1.0, maximum=128.0),
        "power": _parameter("number", 1.0, minimum=1.0, maximum=4.0),
    }),
    _effect("brightness", backend="ffmpeg:eq", category="color", aliases=("lightness",), keyframable=True, parameters={"amount": _parameter("number", 0.0, minimum=-1.0, maximum=1.0)}),
    _effect("chroma_key", backend="ffmpeg:colorkey", category="keying", aliases=("chromakey", "green_screen"), parameters={
        "color": _parameter("color", "0x00ff00"),
        "similarity": _parameter("number", 0.1, minimum=0.00001, maximum=1.0),
        "blend": _parameter("number", 0.0, minimum=0.0, maximum=1.0),
    }, limits=("native_RGB_distance_key_coverage_multiplies_input_alpha", "not_semantic_matting_or_despill")),
    _effect("color_balance", backend="ffmpeg:colorbalance", category="color", aliases=("colorbalance",), parameters={
        "red": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "green": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "blue": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
    }),
    _effect("color", backend="ffmpeg:eq", category="color", parameters={
        "brightness": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "contrast": _parameter("number", 1.0, minimum=0.0, maximum=4.0),
        "saturation": _parameter("number", 1.0, minimum=0.0, maximum=4.0),
    }),
    _effect("color_contrast", backend="ffmpeg:colorcontrast", category="color", aliases=("colorcontrast",), parameters={
        "red": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "green": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "blue": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "red_weight": _parameter("number", 0.0, minimum=0.0, maximum=1.0),
        "green_weight": _parameter("number", 0.0, minimum=0.0, maximum=1.0),
        "blue_weight": _parameter("number", 0.0, minimum=0.0, maximum=1.0),
        "preserve_luma": _parameter("number", 0.0, minimum=0.0, maximum=1.0),
    }),
    _effect("color_levels", backend="ffmpeg:colorlevels", category="color", aliases=("levels", "colorlevels"), parameters={
        "input_black": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "input_white": _parameter("number", 1.0, minimum=-1.0, maximum=1.0),
        "output_black": _parameter("number", 0.0, minimum=0.0, maximum=1.0),
        "output_white": _parameter("number", 1.0, minimum=0.0, maximum=1.0),
        "preserve": _parameter("enum", "none", description="none, lum, max, avg, sum, nrm or pwr"),
    }),
    _effect("color_temperature", backend="ffmpeg:colorbalance", category="color", aliases=("temperature", "warmth"), parameters={"kelvin": _parameter("number", 6500.0, minimum=1000.0, maximum=40000.0)}),
    _effect("color_wheel", backend="ffmpeg:colorbalance", category="color", aliases=("three_way_color", "three_way_wheel"), parameters={
        "shadows_red": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "shadows_green": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "shadows_blue": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "midtones_red": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "midtones_green": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "midtones_blue": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "highlights_red": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "highlights_green": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "highlights_blue": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "preserve_luma": _parameter("boolean", False),
    }, limits=("maps_to_ffmpeg_colorbalance_three_way_wheel",)),
    _effect("contrast", backend="ffmpeg:eq", category="color", keyframable=True, parameters={"amount": _parameter("number", 1.0, minimum=0.0, maximum=4.0)}),
    _effect("curves", backend="ffmpeg:curves", category="color", aliases=("curve",), parameters={
        "all": _parameter("string", "0/0 1/1", description="FFmpeg curves points, for example 0/0 0.5/0.4 1/1"),
        "master": _parameter("string", "", description="Alias for the all/master curve"),
    }, limits=("fixed_point_count_1_to_256", "six_decimal_8bit_x_bins_must_increase", "master_is_all_alias_not_post_master", "point_string_is_whitelist_validated")),
    _effect("deband", backend="ffmpeg:deband", category="repair", aliases=("debanding",), parameters={
        "threshold": _parameter("number", 0.02, minimum=0.001, maximum=0.5),
        "range": _parameter("integer", 16, minimum=1, maximum=64),
    }),
    _effect("deflicker", backend="ffmpeg:deflicker", category="repair", parameters={
        "size": _parameter("integer", 5, minimum=2, maximum=129),
        "mode": _parameter("enum", "am", description="am, gm, hm, qm, cm, pm or median"),
    }),
    _effect("deshake", backend="ffmpeg:deshake", category="repair", aliases=("stabilize",), parameters={"radius": _parameter("integer", 16, minimum=1, maximum=128)}),
    _effect("dctdnoiz", backend="ffmpeg:dctdnoiz", category="repair", parameters={
        "sigma": _parameter("number", 0.0, minimum=0.0, maximum=999.0),
        "overlap": _parameter("integer", -1, minimum=-1, maximum=15),
        "block_bits": _parameter("integer", 3, minimum=3, maximum=4, description="FFmpeg block size expressed as log2, 3=8px or 4=16px"),
    }),
    _effect("draw_box", backend="ffmpeg:drawbox", category="overlay", aliases=("drawbox", "rectangle"), parameters={
        "x": _parameter("number", 0.05, minimum=0.0, maximum=1.0),
        "y": _parameter("number", 0.05, minimum=0.0, maximum=1.0),
        "width": _parameter("number", 0.9, minimum=0.0, maximum=1.0),
        "height": _parameter("number", 0.9, minimum=0.0, maximum=1.0),
        "color": _parameter("color", "white@0.8"),
        "thickness": _parameter("integer", 4, minimum=1, maximum=256),
    }),
    _effect("edgedetect", backend="ffmpeg:edgedetect", category="stylize", aliases=("edge", "edges"), parameters={
        "low": _parameter("number", 0.1, minimum=0.0, maximum=1.0),
        "high": _parameter("number", 0.4, minimum=0.0, maximum=1.0),
    }),
    _effect("exposure", backend="ffmpeg:exposure", category="color", parameters={
        "amount": _parameter("number", 0.0, minimum=-3.0, maximum=3.0),
        "black": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
    }),
    _effect("frame_interpolation", backend="ffmpeg:minterpolate", category="motion", aliases=("minterpolate", "optical_flow", "smooth_slow_motion", "slow_motion"), parameters={
        "fps": _parameter("number", 60.0, minimum=1.0, maximum=240.0, description="目标输出帧率"),
        "mi_mode": _parameter("enum", "mci", description="dup、blend 或 mci"),
        "mc_mode": _parameter("enum", "obmc", description="obmc 或 aobmc"),
        "me_mode": _parameter("enum", "bilat", description="bidir 或 bilat"),
        "me": _parameter("enum", "epzs", description="esa、tss、tdls、ntss、fss、ds、hexbs、epzs 或 umh"),
        "mb_size": _parameter("integer", 16, minimum=4, maximum=16),
        "search_param": _parameter("integer", 32, minimum=4, maximum=512),
        "vsbmc": _parameter("boolean", False),
        "scd": _parameter("enum", "fdiff", description="none 或 fdiff"),
        "scd_threshold": _parameter("number", 10.0, minimum=0.0, maximum=100.0),
    }, limits=("uses_local_ffmpeg_minterpolate", "motion_compensation_can_be_cpu_expensive", "scene_change_detection_is_filter_heuristic")),
    _effect("gamma", backend="ffmpeg:eq", category="color", aliases=("gamma_adjust",), keyframable=True, parameters={"amount": _parameter("number", 1.0, minimum=0.1, maximum=10.0)}),
    _effect("gradfun", backend="ffmpeg:gradfun", category="repair", aliases=("gradient_smooth",), parameters={
        "threshold": _parameter("number", 1.2, minimum=0.1, maximum=64.0),
        "radius": _parameter("integer", 8, minimum=1, maximum=32),
    }),
    _effect("grayscale", backend="ffmpeg:hue", category="stylize", aliases=("black_white", "blackandwhite")),
    _effect("hsl", backend="ffmpeg:hue", category="color", aliases=("hsl_adjust",), keyframable=True, parameters={
        "hue": _parameter("number", 0.0, minimum=-360.0, maximum=360.0, description="全局色相角度"),
        "saturation": _parameter("number", 1.0, minimum=0.0, maximum=4.0, description="全局饱和度倍率"),
        "lightness": _parameter("number", 0.0, minimum=-1.0, maximum=1.0, description="映射到本地 FFmpeg hue brightness 的明度偏移"),
    }, limits=("lightness_uses_ffmpeg_hue_brightness_mapping",)),
    _effect("hqdn3d", backend="ffmpeg:hqdn3d", category="repair", parameters={
        "luma_spatial": _parameter("number", 4.0, minimum=0.0, maximum=30.0),
        "chroma_spatial": _parameter("number", 3.0, minimum=0.0, maximum=30.0),
        "luma_temporal": _parameter("number", 6.0, minimum=0.0, maximum=30.0),
        "chroma_temporal": _parameter("number", 4.5, minimum=0.0, maximum=30.0),
    }),
    _effect("histeq", backend="ffmpeg:histeq", category="color", aliases=("histogram_equalize",)),
    _effect("hflip", backend="ffmpeg:hflip", category="transform", aliases=("flip", "horizontal_flip")),
    _effect("hue", backend="ffmpeg:hue", category="color", aliases=("hue_rotate",), keyframable=True, parameters={"degrees": _parameter("number", 0.0, minimum=-360.0, maximum=360.0)}),
    _effect("invert", backend="ffmpeg:negate", category="stylize", aliases=("negative", "negate")),
    _effect("lens_correction", backend="ffmpeg:lenscorrection", category="distortion", aliases=("lenscorrection",), parameters={
        "k1": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "k2": _parameter("number", 0.0, minimum=-1.0, maximum=1.0),
        "cx": _parameter("number", 0.5, minimum=0.0, maximum=1.0),
        "cy": _parameter("number", 0.5, minimum=0.0, maximum=1.0),
    }),
    _effect("lut3d", backend="ffmpeg:lut3d+blend", category="color", aliases=("lut", "cube", "look"), parameters={
        "path": _parameter("path", ""),
        "lut_id": _parameter("string", "", description="项目内 lut register 生成的稳定资源 ID"),
        "interpolation": _parameter("enum", "tetrahedral", description="nearest, trilinear, tetrahedral, pyramid or prism"),
        "intensity": _parameter("number", 1.0, minimum=0.0, maximum=1.0, description="0..1 强度关键帧；动态为 8-bit 编码 RGB 像素混合并保持 alpha；静态部分强度为 CUBE 网格混合"),
    }, limits=("path_or_registered_lut_id_must_be_project_local", "dynamic_mix_is_8bit_encoded_RGB_not_linear_light_or_HDR", "static_partial_strength_requires_complete_3D_cube")),
    _effect("noise", backend="ffmpeg:noise", category="stylize", aliases=("film_grain",), parameters={"amount": _parameter("integer", 8, minimum=1, maximum=100)}),
    _effect("posterize", backend="ffmpeg:lutrgb", category="stylize", aliases=("posterization",), parameters={"levels": _parameter("integer", 8, minimum=2, maximum=256)}),
    _effect("rgb_curves", backend="ffmpeg:curves", category="color", aliases=("rgb_curve", "channel_curves"), parameters={
        "all": _parameter("string", "0/0 1/1", description="未独立声明的 RGB 通道继承该曲线；不是后置 master"),
        "red": _parameter("string", "", description="红色通道曲线"),
        "green": _parameter("string", "", description="绿色通道曲线"),
        "blue": _parameter("string", "", description="蓝色通道曲线"),
    }, limits=("fixed_point_count_1_to_256", "six_decimal_8bit_x_bins_must_increase", "animated_channel_forks_static_all_if_no_own_points", "each_channel_is_whitelist_validated")),
    _effect("selective_hsl", backend="ffmpeg:frei0r", category="color", aliases=("hsl_bands", "eight_band_hsl"),
            parameters={name: _parameter("number", spec[1], minimum=spec[2], maximum=spec[3]) for name, spec in HSL_SPECS.items()},
            limits=("eight_fixed_hue_centers_with_circular_triangular_partition", "weights_use_original_hue_simultaneously",
                    "encoded_RGB_8bit_HSL_not_linear_light_HDR_or_vendor_look_equivalence", "achromatic_pixels_and_input_alpha_unchanged",
                    "64KiB_per_kernel_16MiB_recursive_expression_budget", "shared_recursive_instances_and_state_samples")),
    _effect("sepia", backend="ffmpeg:colorchannelmixer", category="stylize"),
    _effect("sharpen", backend="ffmpeg:unsharp", category="detail", aliases=("unsharp",), parameters={"amount": _parameter("number", 1.0, minimum=0.0, maximum=10.0)}),
    _effect("smartblur", backend="ffmpeg:smartblur", category="blur", parameters={
        "radius": _parameter("number", 1.0, minimum=0.1, maximum=5.0),
        "strength": _parameter("number", 1.0, minimum=-1.0, maximum=1.0),
        "threshold": _parameter("integer", 0, minimum=-30, maximum=30),
    }),
    _effect("solarize", backend="ffmpeg:lutrgb", category="stylize", parameters={"threshold": _parameter("integer", 128, minimum=0, maximum=255)}),
    _effect("saturation", backend="ffmpeg:eq", category="color", keyframable=True, parameters={"amount": _parameter("number", 1.0, minimum=0.0, maximum=4.0)}),
    _effect("tblend", backend="ffmpeg:tblend", category="temporal", parameters={"mode": _parameter("enum", "average", description="FFmpeg tblend blend mode")}),
    _effect("threshold", backend="ffmpeg:lutyuv", category="stylize", parameters={"value": _parameter("integer", 128, minimum=0, maximum=255)}),
    _effect("tmix", backend="ffmpeg:tmix", category="temporal", parameters={
        "frames": _parameter("integer", 3, minimum=2, maximum=128),
        "scale": _parameter("number", 0.0, minimum=0.0, maximum=1000.0),
    }),
    _effect("vflip", backend="ffmpeg:vflip", category="transform", aliases=("vertical_flip",)),
    _effect("vignette", backend="ffmpeg:vignette", category="stylize", keyframable=True, parameters={"angle": _parameter("number", 0.785398, minimum=0.0, maximum=3.141593)}),
)


def _optical_catalog():
    from .float_optics import SPECS,ALIASES,PROTOCOL
    rows=[]
    for name,parameters in SPECS.items():
        p={k:_parameter('number',v[0],minimum=v[1],maximum=v[2]) for k,v in parameters.items()}
        if name=='lens_flare':p['ghosts']=_parameter('integer',6,minimum=0,maximum=12)
        if name=='chromatic_aberration':p['edge']=_parameter('enum','clamp',description='clamp or transparent; static')
        rows.append(dict(id=name,aliases=[k for k,v in ALIASES.items() if v==name and k!=name],category='optical',
            backend='native:float32-optics',source='agent-editor-kit-original',license='MIT',keyframable=True,
            keyframe_parameters=list(parameters),keyframe_engine=PROTOCOL,parameters=p,
            limits=['explicit_native_linear_working_RGB','coverage_bits_preserved','no_integer_intermediate',
                'CPU_or_probed_render_owned_OpenCL','no_automatic_light_detection_or_physical_lens_solve',
                'ghost_count_and_edge_mode_static','extended_RGB_requires_explicit_delivery_range_policy']))
    return tuple(rows)

_EFFECTS += _optical_catalog()


def _glow_catalog():
    from .float_glow import SPECS,ALIASES,PROTOCOL
    rows=[]
    for name,parameters in SPECS.items():
        p={k:_parameter('number',v[0],minimum=v[1],maximum=v[2]) for k,v in parameters.items()}
        p['edge']=_parameter('enum','transparent',description='transparent or clamp; static')
        rows.append(dict(id=name,aliases=[k for k,v in ALIASES.items() if v==name and k!=name],category='optical',
            backend='native:float32-glow',source='agent-editor-kit-original',license='MIT',keyframable=True,
            keyframe_parameters=list(parameters),keyframe_engine=PROTOCOL,parameters=p,
            limits=['explicit_native_linear_working_RGB','actual_coverage_weighted_highlight_extraction',
                'relative_D65_luminance_soft_knee','normalized_separable_three_sigma_Gaussian_FIR',
                'sigma_0_to_32_source_pixels','Float32_stage_boundaries_binary64_accumulation',
                'coverage_bits_preserved','four_OpenCL_kernels_per_active_operation_or_CPU_reference',
                'bounded_full_spatial_workspace_and_neighbor_visits','no_physical_film_or_HDR_acceptance',
                'extended_RGB_requires_explicit_delivery_range_policy']))
    return tuple(rows)


_EFFECTS += _glow_catalog()
_ALIASES = {alias: item["id"] for item in _EFFECTS for alias in [item["id"], *item["aliases"]]}


def effect_catalog() -> dict[str, Any]:
    """Return a defensive copy of the local effect catalog."""
    effects = deepcopy(list(_EFFECTS))
    return {
        "catalog_version": EFFECT_CATALOG_VERSION,
        "source": "native-and-ffmpeg-local",
        "network": "disabled",
        "count": len(effects),
        "effects": effects,
    }


def list_effects(query: str | None = None, *, keyframable_only: bool = False) -> list[dict[str, Any]]:
    normalized = str(query or "").strip().lower()
    items = []
    for item in _EFFECTS:
        if keyframable_only and not item["keyframable"]:
            continue
        if normalized:
            haystack = " ".join([item["id"], *item["aliases"], item["category"], item["backend"]]).lower()
            if normalized not in haystack:
                continue
        items.append(deepcopy(item))
    return items


def get_effect(name: str) -> dict[str, Any] | None:
    canonical = _ALIASES.get(str(name).strip().lower().replace("-", "_"))
    if canonical is None:
        return None
    for item in _EFFECTS:
        if item["id"] == canonical:
            return deepcopy(item)
    return None


def canonical_effect_id(name: str) -> str | None:
    """Normalize a user-facing effect name without changing project JSON."""
    return _ALIASES.get(str(name).strip().lower().replace("-", "_"))

