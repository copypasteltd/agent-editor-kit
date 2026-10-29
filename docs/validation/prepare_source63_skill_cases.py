"""Derive actual CLI63 PowerShell checks, keeping prior failed cases intact."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/validation'
for name in ('loop','gpu','lipsync'):
 source=DOC/f'run_staged61_{name}_case.py'
 text=source.read_text(encoding='utf-8')
 for old,new in [('lipsync-timeout-20261029-r1','job-enumeration-20261029-r1'),
                 ('source61','source63'),('installed61','installed63'),('staged61','staged63'),
                 ('loop61','loop63'),('CLI61','CLI63'),('0.1.61','0.1.63'),
                 ('installed403','installed406')]:text=text.replace(old,new)
 if name=='loop':
  text=text.replace("assert stage['status'] in ('unregistered-candidate','unregistered-draft')", "assert stage['status']=='unregistered-candidate'")
  text=text.replace("    if stage['status']=='unregistered-draft':assert stage['requires_installed406_before_activation']\n",'')
 text=text.replace("installed406_accepted=stage.get('installed406_accepted',True)","installed406_accepted=stage['requires_installed406']")
 target=DOC/f'run_staged63_{name}_case.py';compile(text,str(target),'exec')
 if target.exists():assert target.read_text(encoding='utf-8')==text
 else:target.write_text(text,encoding='utf-8',newline='\n')
print('Prepared three CLI63 PowerShell case runners; no execution or activation.',flush=True)
