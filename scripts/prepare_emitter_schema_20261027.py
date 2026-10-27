"""Pin full typed emitter animation values in both offline schema copies."""
from pathlib import Path
import copy,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.particle_animation import PROPERTIES,INTERPOLATIONS,MAX_POINTS

path=ROOT/'docs/specs/agent-project.schema.json'
schema=json.loads(path.read_bytes());properties=schema['$defs']['particleEmitter']['properties']
properties['rate']['minimum']=0
tracks=[]
for key in sorted(PROPERTIES):
    point={'type':'object','additionalProperties':False,'required':['at_tick','value'],
        'properties':{'at_tick':{'type':'integer','minimum':0},'value':copy.deepcopy(properties[key]),
            'interpolation':{'enum':list(INTERPOLATIONS)},
            'control_points':{'type':'array','minItems':2,'maxItems':4,'items':{'type':'number','minimum':0,'maximum':1},
                              'oneOf':[{'minItems':2,'maxItems':2},{'minItems':4,'maxItems':4}]}}}
    tracks.append({'type':'object','additionalProperties':False,'required':['property','keyframes'],
        'properties':{'property':{'const':key},'keyframes':{'type':'array','minItems':1,'maxItems':MAX_POINTS,'items':point}}})
properties['keyframes']={'type':'array','minItems':1,'maxItems':len(PROPERTIES),'items':{'oneOf':tracks}}
data=(json.dumps(schema,ensure_ascii=False,indent=2)+'\n').encode('utf8')
path.write_bytes(data);(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').write_bytes(data)
path=ROOT/'product/src/ai_ad_editor/schema_contract.py';code=path.read_text('utf8')
code,count=re.subn(r"SCHEMA_SHA256='[0-9a-f]{64}'","SCHEMA_SHA256='"+hashlib.sha256(data).hexdigest()+"'",code);assert count==1
path.write_text(code,encoding='utf8',newline='\n')
print(json.dumps(dict(schema_sha256=hashlib.sha256(data).hexdigest(),properties=len(PROPERTIES),bytes=len(data))))
