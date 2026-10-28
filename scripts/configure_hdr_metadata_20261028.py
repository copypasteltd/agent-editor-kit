"""Add typed explicit HDR10 declarations and preserve the pinned JSON contract."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'product/src/ai_ad_editor/agent-project.schema.json';s=json.loads(p.read_bytes())
xy={'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':0,'maximum':1}}
display={'type':'object','additionalProperties':False,'required':['red_xy','green_xy','blue_xy','white_xy','min_luminance_nits','max_luminance_nits'],
    'properties':{**{name+'_xy':xy for name in ('red','green','blue','white')},
        'min_luminance_nits':{'type':'number','minimum':0,'maximum':10000},
        'max_luminance_nits':{'type':'number','minimum':.0001,'maximum':10000}}}
s['$defs']['hdr10StaticMetadata']={'type':'object','additionalProperties':False,
    'required':['mastering_display','content_light'],'properties':{'mastering_display':display,
        'content_light':{'type':'object','additionalProperties':False,'required':['max_cll_nits','max_fall_nits'],
            'properties':{name:{'type':'integer','minimum':0,'maximum':10000} for name in ('max_cll_nits','max_fall_nits')}}}}
settings=s['$defs']['settings'];settings['properties']['output']['properties']['hdr10']={'$ref':'#/$defs/hdr10StaticMetadata'}
settings.setdefault('allOf',[]).append({'if':{'required':['output'],'properties':{'output':{'required':['hdr10']}}},
    'then':{'required':['pixel_pipeline'],'properties':{'pixel_pipeline':{'type':'object'}}}})
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
digest=hashlib.sha256(p.read_bytes()).hexdigest();c=p.with_name('schema_contract.py')
t,n=re.subn(r"SCHEMA_SHA256='[a-f0-9]{64}'","SCHEMA_SHA256='"+digest+"'",c.read_text('utf8'));assert n==1
c.write_text(t,encoding='utf8',newline='\n');(ROOT/'docs/specs/agent-project.schema.json').write_bytes(p.read_bytes())
print(json.dumps(dict(status='updated',schema_sha256=digest)))
