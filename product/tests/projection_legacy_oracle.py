"""Frozen CLI 0.1.17 projection functions; native regression oracle only."""
from __future__ import annotations
from typing import Any
import re
from ai_ad_editor.render import _crop_keyframe_expr, _num, _expr_arg


def legacy_dynamic_crop_filters(
    clip: dict[str, Any],
    crop: dict[str, Any],
    canvas_width: int,
    canvas_height: int,
    source_width: int,
    source_height: int,
    clip_start: float,
    tps: int,
    *,
    alpha: bool = False,
) -> list[str]:
    """Animate a crop window while keeping every output frame the same size.

    geq samples RGB and alpha planes with bilinear interpolation. Alpha
    inputs stay premultiplied through both geq and the final resize.
    It keeps the native raster size until the final canvas resize, so small
    crop windows do not allocate an enormous zoomed intermediate frame. Fit
    bars follow the static crop/pad alpha contract. Each plane
    has its own expression state; registers are initialized for every pixel.
    """
    normalized = str(crop.get("unit", "pixels")).lower() in {"normalized", "relative"}
    default_width = 1.0 if normalized else float(source_width or canvas_width)
    default_height = 1.0 if normalized else float(source_height or canvas_height)

    def scalar(names: tuple[str, ...], default: float) -> str:
        return _crop_keyframe_expr(clip, crop, names, default, clip_start, tps, time_variable="T")

    window_width = scalar(("width", "w"), _num(crop.get("width", crop.get("w", default_width)), default_width))
    window_height = scalar(("height", "h"), _num(crop.get("height", crop.get("h", default_height)), default_height))
    origin_x = scalar(("x",), _num(crop.get("x", 0), 0))
    origin_y = scalar(("y",), _num(crop.get("y", 0), 0))
    if normalized:
        window_width, window_height = f"W*({window_width})", f"H*({window_height})"
        origin_x, origin_y = f"W*({origin_x})", f"H*({origin_y})"
    # Clamp size before position so overshooting easing or a moving origin
    # cannot sample beyond the source. Tiny positive windows have a two-pixel
    # floor, the same minimum as the native static crop implementation.
    setup = (
        f"st(0,min(W,max(2,({window_width}))));"
        f"st(1,min(H,max(2,({window_height}))));"
        f"st(2,clip(({origin_x}),0,W-ld(0)));"
        f"st(3,clip(({origin_y}),0,H-ld(1)));"
    )
    fit = str(crop.get("fit", crop.get("mode", "fit"))).lower()
    if fit == "stretch":
        setup += (
            "st(7,ld(2)+(X+0.5)*ld(0)/W-0.5);"
            "st(8,ld(3)+(Y+0.5)*ld(1)/H-0.5);st(9,1);"
        )
    else:
        scale_function = "max" if fit == "fill" else "min"
        destination_x = f"((X+0.5)*{canvas_width}/W)"
        destination_y = f"((Y+0.5)*{canvas_height}/H)"
        setup += (
            f"st(4,{scale_function}({canvas_width}/ld(0),{canvas_height}/ld(1)));"
            f"st(5,({canvas_width}-ld(0)*ld(4))/2);"
            f"st(6,({canvas_height}-ld(1)*ld(4))/2);"
            f"st(7,ld(2)+({destination_x}-ld(5))/ld(4)-0.5);"
            f"st(8,ld(3)+({destination_y}-ld(6))/ld(4)-0.5);"
        )
        if fit == "fill":
            setup += "st(9,1);"
        else:
            setup += (
                f"st(9,gte({destination_x},ld(5))*lt({destination_x},ld(5)+ld(0)*ld(4))"
                f"*gte({destination_y},ld(6))*lt({destination_y},ld(6)+ld(1)*ld(4)));"
            )
    sample_x = "clip(ld(7),ld(2),ld(2)+ld(0)-1)"
    sample_y = "clip(ld(8),ld(3),ld(3)+ld(1)-1)"

    def plane(name: str, outside: int) -> str:
        return _expr_arg(f"{setup}if(ld(9),{name}({sample_x},{sample_y}),{outside})")

    prefix = ['format=gbrapf32le', 'premultiply=inplace=1'] if alpha else ['format=gbrap']
    suffix = ['unpremultiply=inplace=1', 'format=rgba'] if alpha else []
    return prefix + [
        f"geq=r={plane('r', 0)}:g={plane('g', 0)}:b={plane('b', 0)}:a={plane('alpha', 0 if alpha else 255)}:interpolation=bilinear",
        f"scale={canvas_width}:{canvas_height}:flags=lanczos",
        "setsar=1",
    ] + suffix


def legacy_sequence_raster_filters(
    clip: dict[str, Any], transform: dict[str, str], source: dict[str, int], target: dict[str, int],
    start: float, tps: int, *, sampling: str = 'bilinear',
) -> list[str]:
    """Project a child raster into its parent's canvas around the child anchor.

    Retain the complete native texture on a padded working raster and sample
    its crop/fit/TRS coordinates once. Rotation may reveal source content
    hidden by fill at the resting pose. The output rectangle is cropped only
    after sampling; interpolation is premultiplied, before the parent mask.
    """
    sw, sh = source['width'], source['height']
    tw, th = target['width'], target['height']
    crop = clip.get('crop') or {}
    normalized = str(crop.get('unit', 'pixels')).lower() in {'normalized', 'relative'}
    def scalar(names: tuple[str, ...], default: float, extent: int) -> str:
        value = next((crop[n] for n in names if n in crop), default)
        result = _crop_keyframe_expr(clip, crop, names, _num(value, default), start, tps, time_variable='T')
        return f'({result})*{extent}' if normalized else result
    w = scalar(('width', 'w'), 1. if normalized else sw, sw)
    h = scalar(('height', 'h'), 1. if normalized else sh, sh)
    x = scalar(('x',), 0., sw)
    y = scalar(('y',), 0., sh)
    fit = str(crop.get('fit', crop.get('mode', 'fit'))).lower()
    if fit == 'stretch':
        fit_x, fit_y = f'{tw}/ld(0)', f'{th}/ld(1)'
    else:
        select = 'max' if fit == 'fill' else 'min'
        fit_x = fit_y = f'{select}({tw}/ld(0),{th}/ld(1))'
    values = {k: re.sub(r'\bt\b', 'T', v) for k,v in transform.items()}
    angle = f"({values['rotation']})*PI/180"
    dx, dy = f"(X+0.5-({values['position_x']})*{tw})", f"(Y+0.5-({values['position_y']})*{th})"
    scale = f"max(0.00000001,abs({values['scale']}))"
    setup = (
        f'st(0,clip(({w}),2,{sw}));st(1,clip(({h}),2,{sh}));'
        f'st(2,clip(({x}),0,{sw}-ld(0)));st(3,clip(({y}),0,{sh}-ld(1)));'
        f'st(4,{fit_x});st(5,{fit_y});'
        f"st(6,ld(2)+({values['anchor_x']})*ld(0)+({dx}*cos({angle})+{dy}*sin({angle}))/({scale}*ld(4))-0.5);"
        f"st(7,ld(3)+({values['anchor_y']})*ld(1)+(-{dx}*sin({angle})+{dy}*cos({angle}))/({scale}*ld(5))-0.5);"
    )
    sample_x = 'clip(ld(6),ld(2),ld(2)+ld(0)-1)'
    sample_y = 'clip(ld(7),ld(3),ld(3)+ld(1)-1)'
    def plane(name: str) -> str:
        if sampling == 'area':
            # Reuse registers only after their old values have been consumed.
            edges = (f'st(4,max(1,1/({scale}*ld(4))));st(5,max(1,1/({scale}*ld(5))));'
                     'st(8,clip(ld(6)+0.5-ld(4)/2,ld(2),ld(2)+ld(0)));'
                     'st(9,clip(ld(6)+0.5+ld(4)/2,ld(2),ld(2)+ld(0)));'
                     'st(2,clip(ld(7)+0.5-ld(5)/2,ld(3),ld(3)+ld(1)));'
                     'st(3,clip(ld(7)+0.5+ld(5)/2,ld(3),ld(3)+ld(1)));')
            return _expr_arg(f'if(lt(X,{tw})*lt(Y,{th}),'+setup+edges+area_rectangle(name)+',0)')
        inside = 'st(8,gte(ld(6),ld(2)-0.5)*lt(ld(6),ld(2)+ld(0)-0.5)*gte(ld(7),ld(3)-0.5)*lt(ld(7),ld(3)+ld(1)-0.5));'
        return _expr_arg(setup+inside+f'if(ld(8),{name}({sample_x},{sample_y}),0)')
    return ['format=rgba', f'pad={max(sw,tw)}:{max(sh,th)}:0:0:color=black@0', 'setsar=1',
            'format=gbrapf32le', 'premultiply=inplace=1',
            f"geq=r={plane('r')}:g={plane('g')}:b={plane('b')}:a={plane('alpha')}:interpolation=bilinear",
            f'crop={tw}:{th}:0:0:exact=1', 'unpremultiply=inplace=1', 'format=rgba']


def area_rectangle(name: str) -> str:
    """Integrate piecewise-constant premultiplied pixels over fractional edges.

    FFmpeg *sum() queries round coordinates to integers. Interpolate four
    integer prefixes at each continuous edge instead. Registers supplied by
    the caller: 8/9 = left/right, 2/3 = top/bottom, 4/5 = full kernel width/height.
    The rectangle is clipped to the crop but normalization includes transparency
    beyond it. No additional geq registers are needed (there are only ten).
    """
    def prefix(x: str, y: str) -> str:
        ix, iy = f'floor({x})', f'floor({y})'
        fx, fy = f'({x}-{ix})', f'({y}-{iy})'
        function = name+'sum'
        return (f'((1-{fx})*(1-{fy})*{function}({ix}-1,{iy}-1)'
                f'+{fx}*(1-{fy})*{function}({ix},{iy}-1)'
                f'+(1-{fx})*{fy}*{function}({ix}-1,{iy})'
                f'+{fx}*{fy}*{function}({ix},{iy}))')
    return (f"({prefix('ld(9)','ld(3)')}-{prefix('ld(8)','ld(3)')}"
            f"-{prefix('ld(9)','ld(2)')}+{prefix('ld(8)','ld(2)')})/(ld(4)*ld(5))")
