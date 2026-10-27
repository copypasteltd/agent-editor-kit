"""Extend the native Float32 JSON contract without rewriting historical data."""
from pathlib import Path
import json
import hashlib
import re

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'product/src/ai_ad_editor/agent-project.schema.json'
schema=json.loads(path.read_bytes())
definitions=schema['$defs']
signal={'type':'object','additionalProperties':False,'required':['primaries','transfer'],
    'properties':{
        'primaries':{'enum':['bt709','display-p3','bt2020']},
        'transfer':{'enum':['linear','srgb','bt709-oetf','gamma22','gamma24','pq-st2084','hlg-bt2100']},
        'reference_white_nits':{'type':'number','minimum':.01,'maximum':10000},
        'display_peak_nits':{'type':['number','null'],'minimum':100,'maximum':10000},
        'system_gamma':{'type':['number','null'],'minimum':.5,'maximum':3}},
    'allOf':[
        {'if':{'properties':{'transfer':{'enum':['pq-st2084','hlg-bt2100']}}},
         'then':{'required':['reference_white_nits'],'properties':{'primaries':{'const':'bt2020'}}}},
        {'if':{'properties':{'transfer':{'const':'hlg-bt2100'}}},
         'then':{'required':['display_peak_nits','system_gamma'],
                 'properties':{'display_peak_nits':{'type':'number'},'system_gamma':{'type':'number'}}},
         'else':{'properties':{'display_peak_nits':{'type':'null'},'system_gamma':{'type':'null'}}}},
        {'if':{'anyOf':[{'required':['display_peak_nits']},{'required':['system_gamma']}]},
         'then':{'required':['reference_white_nits']}}]}
mapping={'type':'object','additionalProperties':False,
    'required':['operator','source_peak_nits','target_peak_nits','exposure_stops','gamut_policy'],
    'properties':{'operator':{'const':'reinhard-luminance'},
        'source_peak_nits':{'type':'number','minimum':1,'maximum':10000},
        'target_peak_nits':{'type':'number','minimum':1,'maximum':1000},
        'exposure_stops':{'type':'number','minimum':-16,'maximum':16},
        'gamut_policy':{'enum':['reject','clip']}}}
definitions['nativeFloatSignal']=signal
definitions['nativeDisplayMapping']=mapping
pipeline=definitions['nativeFloatPipeline']['properties']
for field in ('working_signal','output_signal','background_signal'):
    pipeline[field]={'$ref':'#/$defs/nativeFloatSignal'}
for field in ('preview_mapping','display_mapping'):
    pipeline[field]={'$ref':'#/$defs/nativeDisplayMapping'}
source=pipeline['sources']['additionalProperties']['properties']
source['source_signal']={'$ref':'#/$defs/nativeFloatSignal'}
source['hdr_input_range_policy']={'enum':['reject','clip']}
path.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
digest=hashlib.sha256(path.read_bytes()).hexdigest()
contract=path.with_name('schema_contract.py')
text=contract.read_text(encoding='utf8')
text,n=re.subn(r"SCHEMA_SHA256='[a-f0-9]{64}'", "SCHEMA_SHA256='"+digest+"'",text)
assert n==1
contract.write_text(text,encoding='utf8',newline='\n')
(ROOT/'docs/specs/agent-project.schema.json').write_bytes(path.read_bytes())
print(json.dumps({'status':'updated','schema_sha256':digest,'definitions':['nativeFloatSignal','nativeDisplayMapping']}))
