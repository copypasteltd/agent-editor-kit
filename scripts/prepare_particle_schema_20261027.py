"""Extend the offline pinned schema with actual editable particle source fields."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
schema_path=ROOT/'docs/specs/agent-project.schema.json'
s=json.loads(schema_path.read_text(encoding='utf8'))
def num(lo,hi):return {'type':'number','minimum':lo,'maximum':hi}
def pair(lo,hi):return {'type':'array','minItems':2,'maxItems':2,'items':num(lo,hi)}
hexcolor={'type':'string','pattern':'^#[a-fA-F0-9]{6}$'}
emitter={
    **{k:num(*v) for k,v in {'rate':(.01,1024),'size_end':(0,4),'aspect':(.05,20),
       **{k:(0,1) for k in ('softness','glow','opacity','fade_in','fade_out')}}.items()},
    **{k:pair(*v) for k,v in {'lifetime':(.01,120),'position':(-4,4),'spread':(0,8),
        'size':(.0001,.5),'rotation':(-36000,36000),'spin':(-36000,36000),
        'acceleration':(-8,8),'sway':(0,16),'twinkle':(0,16)}.items()},
    'velocity':{'type':'array','minItems':2,'maxItems':2,'items':pair(-8,8)},
    'shape':{'enum':['disc','rectangle','diamond','star','ring']},'prewarm':{'type':'boolean'},
    'colors':{'type':'array','minItems':1,'maxItems':32,'items':hexcolor},
    'color_end':{'oneOf':[hexcolor,{'type':'null'}]}}
s['$defs']['particleEmitter']={'type':'object','additionalProperties':False,'properties':emitter}
s['$defs']['particleGenerator']={'type':'object','additionalProperties':False,
    'required':['type','canvas','fps','duration_tick','ticks_per_second','emitters'],
    'properties':{'type':{'const':'particles'},'protocol':{'const':'analytic-seeded-particle-source-v1'},
        'seed':{'type':'integer','minimum':0,'maximum':2**63-1},
        'canvas':{'type':'object','additionalProperties':False,'required':['width','height'],
            'properties':{k:{'type':'integer','minimum':2,'maximum':8192} for k in ('width','height')}},
        'fps':{'type':'object','additionalProperties':False,'required':['num','den'],
            'properties':{k:{'type':'integer','minimum':1,'maximum':120000} for k in ('num','den')}},
        'duration_tick':{'type':'integer','minimum':1},'ticks_per_second':{'type':'integer','minimum':1,'maximum':1000000000},
        'emitters':{'type':'array','minItems':1,'maxItems':16,'items':{'$ref':'#/$defs/particleEmitter'}}}}
text={'type':'object','additionalProperties':False,'properties':{'type':{'const':'text'}},'required':['type']}
s['$defs']['clip']['properties']['generator']={'oneOf':[text,{'$ref':'#/$defs/particleGenerator'}]}
raw=(json.dumps(s,ensure_ascii=False,indent=2)+'\n').encode('utf8')
schema_path.write_bytes(raw)
(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').write_bytes(raw)
p=ROOT/'product/src/ai_ad_editor/schema_contract.py'
code=p.read_text(encoding='utf8')
code=re.sub(r"SCHEMA_SHA256='[0-9a-f]{64}'","SCHEMA_SHA256='"+hashlib.sha256(raw).hexdigest()+"'",code)
p.write_text(code,encoding='utf8',newline='\n')
print('Pinned schema',hashlib.sha256(raw).hexdigest())
