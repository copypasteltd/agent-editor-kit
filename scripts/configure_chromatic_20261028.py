"""Extend the pinned native signal contract with explicit reference whites."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];p=ROOT/'product/src/ai_ad_editor/agent-project.schema.json'
s=json.loads(p.read_bytes());v=s['$defs']['nativeFloatSignal']['properties']
v['primaries']['enum']+=['prophoto-rgb','aces-ap1'];v['transfer']['enum'].append('prophoto-rgb')
v['white_xy']={'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':.0001,'maximum':.9998}}
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
digest=hashlib.sha256(p.read_bytes()).hexdigest();c=p.with_name('schema_contract.py')
t,n=re.subn(r"SCHEMA_SHA256='[a-f0-9]{64}'","SCHEMA_SHA256='"+digest+"'",c.read_text('utf8'));assert n==1
c.write_text(t,encoding='utf8',newline='\n');(ROOT/'docs/specs/agent-project.schema.json').write_bytes(p.read_bytes())
print(json.dumps(dict(status='updated',schema_sha256=digest)))
