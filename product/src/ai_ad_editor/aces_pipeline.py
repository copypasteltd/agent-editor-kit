"""Explicit scene ACEScg to native OCIO display signals at the delivery edge."""
from . import ocio_runtime as ocio
from .errors import AppError
from .float_chromatic import white_of,D60
from .float_color_signal import ColorSignal
from .float_hdr import LuminanceSignal,has_luminance

DISPLAYS={
    'sRGB - Display':('bt709','srgb'),
    'Rec.1886 Rec.709 - Display':('bt709','gamma24'),
    'Gamma 2.2 Rec.709 - Display':('bt709','gamma22'),
    'Rec.2100-PQ - Display':('bt2020','pq-st2084'),
    'Rec.2100-HLG - Display':('bt2020','hlg-bt2100')}

def error(message):return AppError('ACES_PIPELINE_CONFIG',message,exit_code=2)

def validate(value,working,output,*,preview=False):
    value=ocio.configuration(value)
    if working.primaries!='aces-ap1' or working.transfer!='linear' or white_of(working)!=D60:
        raise error('ACES输入须明确为AP1/D60线性工作域；不是自动相机IDT')
    if value['display'] not in DISPLAYS:raise error('当前编码交付支持明确BT.709 SDR和BT.2100 PQ/HLG显示；其他显示尚待编码支持')
    c=ocio.config(value['config']);d=value['display'];v=value['view']
    if d not in list(c.getDisplays()) or v not in list(c.getViews(d)) or not c.getDisplayViewTransformName(d,v).startswith('ACES '):
        raise error('交付必须选择固定配置中的真实ACES Output Transform；Raw/未映射视图不作为ACES交付')
    primaries,transfer=DISPLAYS[d]
    if preview:
        if primaries!='bt709':raise error('ACES观看预览须明确BT.709 SDR视图；HDR作者交付保持独立')
    else:
        if primaries!=output.primaries:raise error('ACES显示基色须匹配作者编码输出')
        if primaries=='bt2020' and output.transfer!=transfer:raise error('ACES HDR显示传递函数须匹配PQ/HLG编码输出')
        if primaries=='bt709' and has_luminance(output) and output.reference_white_nits!=100:
            raise error('ACES SDR视图的显示白亮度须明确100 nit；相对输出可省略亮度单位')
        if transfer=='hlg-bt2100' and (output.display_peak_nits!=1000 or output.system_gamma!=1.2 or getattr(output,'display_black_nits',0)!=0):
            raise error('固定OCIO HLG显示使用1000 nit/系统gamma1.2/零黑位，不能静默改为其他显示条件')
    return value

def native_signal(value,output=None):
    primaries,transfer=DISPLAYS[value['display']]
    if primaries=='bt2020':return output
    return LuminanceSignal(primaries,transfer,100) if output is not None and has_luminance(output) else ColorSignal(primaries,transfer)

def dependency_paths(pipeline):
    from pathlib import Path
    return {*ocio.runtime_paths(),Path(__file__).resolve()} if isinstance(pipeline,dict) and any(k in pipeline for k in ('aces_display','aces_preview')) else set()
