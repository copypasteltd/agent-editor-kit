"""Author eight MIT editable optical templates without changing frozen core code."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = ROOT / 'docs/content/effect-packs/optical-v1'


def keys(prop, values):
    return dict(property=prop, keyframes=[dict(at_tick=at, value=value, interpolation='ease_in_out')
                                         for at, value in values])


def pulse(low, high):
    return keys('intensity', [(0, low), ('{{middle_tick}}', high), ('{{end_tick}}', low)])


def effect(kind, parameters, *animation):
    return dict(type=kind, parameters=parameters, keyframes=list(animation))


PRESETS = [
    ('OP01', 'warm-memory', '暖光回忆', 'Warm memory', '文旅／复古产品',
     '暖色椭圆漏光从左上移向右侧；高光产生暖红晕边。',
     'Moving amber light leak with warm highlight halation.',
     [effect('light_leak', dict(intensity=.55, x=.1, y=.25, radius=.35, aspect=1.8, angle=-25,
                               red=1.0, green=.32, blue=.08, brightness=.45),
             keys('x', [(0, -.2), ('{{end_tick}}', 1.15)]), pulse(.15, .62)),
      effect('halation', dict(intensity=.45, threshold=.48, knee=.12, radius=4,
                             gain=1.3, red=1, green=.15, blue=.03))]),
    ('OP02', 'pearl-soft', '珍珠柔光', 'Pearl soft', '珠宝／静物产品',
     '中性偏冷高光柔化；低强度白色漏光缓缓移过。不是皮肤美颜。',
     'Soft neutral highlights and a faint moving white leak; no skin retouch.',
     [effect('bloom', dict(intensity=.65, threshold=.52, knee=.15, radius=5,
                          gain=.85, red=.90, green=.95, blue=1)),
      effect('light_leak', dict(intensity=.22, x=.2, y=.2, radius=.5, aspect=1.6,
                               red=.9, green=.95, blue=1, brightness=.22),
             keys('x', [(0, -.3), ('{{end_tick}}', 1.3)]))]),
    ('OP03', 'cyan-tech', '青蓝科技', 'Cyan tech', '电子产品／科技发布',
     '青蓝镜头星芒斜向扫过，红蓝通道小幅径向分离并在中段增强。',
     'Sweeping cyan flare with a small radial red/blue split peaking at mid-shot.',
     [effect('lens_flare', dict(intensity=.55, x=.2, y=.18, radius=.05, red=.08, green=.7,
                               blue=1, brightness=.6, streak=1.5, streak_width=.004,
                               halo=.2, ghosts=3, ghost_spacing=.55, angle=-18),
             keys('x', [(0, -.12), ('{{end_tick}}', 1.12)]), pulse(.12, .8)),
      effect('chromatic_aberration', dict(intensity=.35, red_shift=2, blue_shift=-2,
                                         falloff=1.5, edge='clamp'), pulse(.12, .4))]),
    ('OP04', 'gold-launch', '鎏金发布', 'Gold launch', '新品发布／品牌片',
     '金色横向长星芒由暗转亮再回落；叠加少量暖色高光扩散。',
     'A long golden flare rises and falls over gentle warm highlight bloom.',
     [effect('lens_flare', dict(intensity=.6, x=.75, y=.28, radius=.06, red=1, green=.65,
                               blue=.18, brightness=.55, streak=2.2, streak_width=.003,
                               halo=.25, ghosts=5, ghost_spacing=.48), pulse(.05, .9)),
      effect('bloom', dict(intensity=.4, threshold=.6, knee=.15, radius=4,
                          gain=.7, red=1, green=.8, blue=.45))]),
    ('OP05', 'rose-dream', '玫瑰梦境', 'Rose dream', '香氛／生活方式',
     '玫瑰紫漏光对角流动，与偏粉高光扩散组成梦境氛围。',
     'Diagonal rose-purple light leak and pink-tinted bloom.',
     [effect('light_leak', dict(intensity=.52, x=.1, y=.2, radius=.38, aspect=2.1, angle=40,
                               red=1, green=.12, blue=.45, brightness=.4),
             keys('x', [(0, -.2), ('{{end_tick}}', 1.1)]),
             keys('y', [(0, -.1), ('{{end_tick}}', 1.05)])),
      effect('bloom', dict(intensity=.45, threshold=.5, knee=.2, radius=6,
                          gain=.65, red=1, green=.6, blue=.8))]),
    ('OP06', 'prism-pulse', '棱镜脉冲', 'Prism pulse', '运动／节奏产品展示',
     '红蓝径向分离在中段快速增强，配合冷白星芒脉冲。不是语义节拍检测。',
     'A timed radial RGB pulse and cool white flare; no automatic beat detection.',
     [effect('chromatic_aberration', dict(intensity=.8, red_shift=4, blue_shift=-4,
                                         x=.5, y=.5, falloff=1, edge='clamp'), pulse(.05, .95)),
      effect('lens_flare', dict(intensity=.4, x=.6, y=.22, radius=.045, red=.75, green=.9,
                               blue=1, brightness=.4, streak=1, streak_width=.004,
                               halo=.12, ghosts=2, ghost_spacing=.65), pulse(.03, .65))]),
    ('OP07', 'silver-glass', '银色玻璃', 'Silver glass', '玻璃器皿／极简品牌',
     '细窄冷白横向星芒与柔和中性高光；亮点从右上移向左侧。',
     'A thin cool-white streak moves right to left above neutral bloom.',
     [effect('lens_flare', dict(intensity=.5, x=.8, y=.18, radius=.035, red=.75, green=.88,
                               blue=1, brightness=.5, streak=2.6, streak_width=.002,
                               halo=.08, ghosts=2, ghost_spacing=.6),
             keys('x', [(0, 1.15), ('{{end_tick}}', -.15)])),
      effect('bloom', dict(intensity=.35, threshold=.7, knee=.1, radius=2.5,
                          gain=.6, red=1, green=1, blue=1))]),
    ('OP08', 'sunset-halo', '落日光晕', 'Sunset halo', '户外／旅行氛围',
     '偏橙低角度圆光源缓缓下落，亮部叠加暖色边缘晕光。不是日光重打光。',
     'A low orange flare descends over warm highlight edges; no scene relighting.',
     [effect('lens_flare', dict(intensity=.45, x=.85, y=.3, radius=.1, red=1, green=.28,
                               blue=.04, brightness=.5, streak=.3, streak_width=.01,
                               halo=.6, ghosts=4, ghost_spacing=.4),
             keys('y', [(0, .1), ('{{end_tick}}', .55)])),
      effect('halation', dict(intensity=.6, threshold=.5, knee=.15, radius=5,
                             gain=1.4, red=1, green=.2, blue=.03))]),
]


def main():
    HOME.mkdir(parents=True, exist_ok=False)
    rows = []
    for code, slug, zh, en, use, description, english, effects in PRESETS:
        template = dict(id='aek.optical.' + slug, version='1.0.0',
                        name=dict(zh=zh, en=en), license_spdx='MIT',
                        author='agent editor kit',
                        variables=[dict(name='clip_id', type='string', required=True),
                                   dict(name='middle_tick', type='integer', min=1, required=True),
                                   dict(name='end_tick', type='integer', min=2, required=True)],
                        operations=[dict(op='update_clip', clip_id='{{clip_id}}', patch=dict(effects=effects))])
        path = HOME / (code + '-' + slug + '.json')
        path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        rows.append(dict(id=code, template_id=template['id'], version='1.0.0', name_zh=zh,
                         name_en=en, use_cases_zh=use, description_zh=description, description_en=english,
                         template=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                         license_spdx='MIT', effects=[e['type'] for e in effects],
                         prerequisites=['float32-native-v1', 'explicit source/working/output signals',
                                        'existing target clip; reviewed replacement of its full effects array',
                                        'original author-clock middle_tick/end_tick; no automatic retiming'],
                         reference_source_pixels=[480, 270], reference_duration_ticks=360000,
                         automatic_scene_or_subject_analysis=False, natural_quality_accepted=False))
    catalog = dict(format='agent-optical-template-pack-v1', version='1.0.0',
                   minimum_core_version='0.1.39', template_count=len(rows),
                   core_changes=0, external_models=0, items=rows)
    (HOME / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (HOME / 'LICENSE').write_bytes((ROOT / 'skills/agent-ffmpeg-local-editor/LICENSE').read_bytes())
    print(json.dumps(dict(status='authored-awaiting-real-CLI-validation', templates=len(rows),
                         folder=str(HOME), core_changed=False, accepted=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
