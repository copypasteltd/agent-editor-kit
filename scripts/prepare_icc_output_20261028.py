"""Apply the explicit soft-proof contract without touching historical evidence."""
import copy,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'product/src/ai_ad_editor/agent-project.schema.json';s=json.loads(p.read_bytes());defs=s['$defs']
profile=copy.deepcopy(defs['nativeICCSourceSignal']);profile['properties'].pop('reference_white_nits')
defs['nativeICCProofProfile']=profile
defs['nativeFloatPipeline']['properties']['proofing']={'type':'object','additionalProperties':False,
 'required':['profile','simulation_intent'],'properties':{'profile':{'$ref':'#/$defs/nativeICCProofProfile'},
 'simulation_intent':copy.deepcopy(profile['properties']['intent'])}}
data=(json.dumps(s,ensure_ascii=False,indent=2)+'\n').encode('utf8')
for path in (p,ROOT/'docs/specs/agent-project.schema.json'):path.write_bytes(data)
p=ROOT/'product/src/ai_ad_editor/schema_contract.py'
p.write_text(re.sub(r"SCHEMA_SHA256='[0-9a-f]+'","SCHEMA_SHA256='"+hashlib.sha256(data).hexdigest()+"'",p.read_text('utf8')),encoding='utf8',newline='\n')
