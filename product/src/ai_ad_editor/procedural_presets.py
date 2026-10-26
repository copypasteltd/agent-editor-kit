"""Original procedural recipes: editable numeric emitters, no licensed media."""
from __future__ import annotations
import copy
from .procedural_particles import normalize, fail, PROTOCOL

VERSION = '1.0.0'
PRESETS = {
    'snow': {
        'name': '柔雪 / Soft snow', 'description': '白色柔边圆片从上方向下飘落，轻微横向摆动，逐渐缩小并淡出。',
        'use': '冬季人物、节庆和安静场景；不会自动识别人像深度。',
        'emitters': [{'rate':38,'velocity':[[-.025,.025],[.1,.24]],'sway':[.018,.32],
            'lifetime':[3,6],'size':[.0025,.009],'size_end':.7,'softness':.5,'opacity':.75}]},
    'confetti': {
        'name': '彩纸 / Confetti', 'description': '五色硬边矩形纸片，随机旋转及自转、重力加速、缓慢缩小。',
        'use': '庆典、促销、结果揭晓；二维图形，不模拟三维翻面或碰撞。',
        'emitters': [{'rate':38,'lifetime':[2.5,4.5],'shape':'rectangle','aspect':.5,
            'size':[.004,.011],'softness':.1,'size_end':.65,'opacity':.95,'acceleration':[0,.06],
            'spin':[-200,200],'colors':['#ff4b69','#ffc83d','#41cfb7','#7494ff','#f5f0dc']}]},
    'embers': {
        'name': '余烬 / Embers', 'description': '底部橙黄色发光颗粒向上漂移，变红、缩小并闪烁消散。',
        'use': '暖色商品、火光和戏剧氛围；不会自动添加火焰或照亮真实物体。',
        'emitters': [{'rate':26,'position':[.5,1.08],'spread':[1.15,.15],
            'velocity':[[-.045,.045],[-.3,-.12]],'acceleration':[0,-.015],
            'size':[.0015,.006],'size_end':.15,'lifetime':[2,5],'glow':.75,
            'colors':['#fff2ae','#ffc35e','#f56f2c'],'color_end':'#8b190d',
            'twinkle':[.35,2.1],'sway':[.015,.5],'opacity':.9}]},
    'bokeh': {
        'name': '漂浮光斑 / Floating bokeh', 'description': '暖金、玫瑰和蓝色大圆光斑，低透明度、柔边与光晕，缓慢上升淡入淡出。',
        'use': '珠宝、美妆和梦幻背景；不是镜头真实景深或失焦恢复。',
        'emitters': [{'rate':5,'position':[.5,.6],'spread':[1.3,1.4],
            'velocity':[[-.012,.012],[-.028,-.008]],'acceleration':[0,0],
            'size':[.025,.08],'size_end':1.2,'lifetime':[4,8],'softness':.85,
            'glow':.3,'opacity':.28,'fade_in':.35,'fade_out':.5,
            'colors':['#ffd6a0','#f7b4c3','#b9d9ff']}]},
    'rain': {
        'name': '斜雨 / Slanted rain', 'description': '细长半透明蓝灰矩形，以倾斜角度快速落下；短生命周期，高发射率。',
        'use': '雨夜气氛；无水花、折射、湿润材质或遮挡判断。',
        'emitters': [{'rate':105,'lifetime':[.7,1.1],'position':[.5,-.15],'spread':[1.5,.3],
            'velocity':[[.18,.25],[1.1,1.5]],'acceleration':[0,.2],
            'shape':'rectangle','aspect':.06,'rotation':[-10,-10],'spin':[0,0],
            'size':[.00065,.0012],'size_end':1,'softness':.4,'opacity':.38,
            'colors':['#bacbdc','#e2eaf1'],'fade_in':.04,'fade_out':.08}]},
    'sparkles': {
        'name': '星芒 / Sparkles', 'description': '金白五角星在画面内缓慢旋转、缩小及闪烁，带柔和光晕。',
        'use': '产品高光、节日和魔法点缀；不自动跟踪物体高光。',
        'emitters': [{'rate':12,'lifetime':[1.2,3],'position':[.5,.5],'spread':[.95,.9],
            'velocity':[[-.015,.015],[-.02,.005]],'acceleration':[0,0],
            'shape':'star','size':[.003,.016],'size_end':.3,'spin':[-30,30],
            'colors':['#fff7de','#ffd67b'],'softness':.2,'glow':.4,'opacity':.85,
            'twinkle':[.8,1.8],'fade_in':.2,'fade_out':.45}]},
}


def get(name):
    if name not in PRESETS: raise fail('PRESET', '不存在的程序化特效预设', name=name)
    return {'id':name,'version':VERSION,'protocol':PROTOCOL,'license':'MIT',
        'author':'agent editor kit contributors','external_assets':[],**copy.deepcopy(PRESETS[name])}


def catalog(): return [get(name) for name in PRESETS]


def source(name, *, canvas, fps, duration_tick, ticks_per_second, seed=0):
    return normalize({'type':'particles','protocol':PROTOCOL,'seed':seed,'canvas':copy.deepcopy(canvas),
        'fps':copy.deepcopy(fps),'duration_tick':duration_tick,'ticks_per_second':ticks_per_second,
        'emitters':get(name)['emitters']})
