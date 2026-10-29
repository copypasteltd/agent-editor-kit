"""Prepare actual registered-entry checks against the exact tested CLI63 Skill."""
from pathlib import Path
import runpy
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/validation'
registered=runpy.run_path(str(DOC/'prepare_source61_registered_delivery.py'))['registered']
def write(name,text):
 p=DOC/name;compile(text,str(p),'exec')
 if p.exists():assert p.read_text(encoding='utf-8')==text
 else:p.write_text(text,encoding='utf-8',newline='\n')
for name,arg in [('loop','a'),('gpu','args'),('lipsync','args')]:
 text=registered((DOC/f'run_staged63_{name}_case.py').read_text(encoding='utf-8'),arg)
 for old,new in [('skill61','skill63'),('installed61','installed63'),('music61','music63'),
  ('registered61','registered63'),('0.1.61','0.1.63'),("contracts['tests']==403","contracts['tests']==406")]:text=text.replace(old,new)
 if name=='loop':
  text=text.replace('music-loop63-staged-case-','music-loop63-registered-case-')
  text=text.replace("('staged-actual-case-'+a.run)","('registered-actual-case-'+a.run)")
  text=text.replace("assert manifest['cli_version']=='0.1.59'","assert manifest['cli_version']=='0.1.63'")
 else:
  text=text.replace("mode = 'staged63'","mode = 'registered63'").replace("mode='staged63'","mode='registered63'")
  text=text.replace("BASE/'staged-actual-case-r1/verification.json'","BASE/'registered-actual-case-r1/verification.json'")
 assert 'source61_voice_skill_overlay' not in text and 'installed61' not in text
 text=text.replace('installed63-contracts-r1/verification.json','installed63-contracts-r2/verification.json')
 write(f'run_registered63_{name}_case.py',text)
text=(DOC/'run_source61_registered_acceptance.py').read_text(encoding='utf-8')
for old,new in [('lipsync-timeout-20261029-r1','job-enumeration-20261029-r1'),('CLI61','CLI63'),
 ('source61','source63'),('skill61','skill63'),('registered61','registered63'),('0.1.61','0.1.63')]:text=text.replace(old,new)
text=text.replace("activation['documentation_overlay']['actual_voice_samples']==103", "activation['voice_auditions']['actual_voice_samples']==103 and activation['post_test_document_changes'] is False")
write('run_source63_registered_acceptance.py',text)
for name in ['build_source61_final_kit.py','verify_source61_final_kit.py']:
 text=(DOC/name).read_text(encoding='utf-8')
 for old,new in [('lipsync-timeout-20261029-r1','job-enumeration-20261029-r1'),('CLI61','CLI63'),
  ('skill61','skill63'),('music61','music63'),('registered61','registered63'),('0.1.61','0.1.63')]:text=text.replace(old,new)
 if name.startswith('build_'):
  needle="    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'"
  guard="""    required=[BASE/'skill63-activation-r1/verification.json',BASE/'registered-controller-r1/verification.json']
    missing=[str(p.relative_to(ROOT)) for p in required if not p.is_file()]
    if missing:
        print(json.dumps(dict(status='pending',missing=missing,mutated=False)),flush=True)
        return 2
    assert load(required[0])['status']=='activated-and-entry-verified'
    controller=load(required[1]);assert controller['status']=='passed' and controller['actual_loop_DF3_MuseTalk_passed']
    assert load(required[0])['post_test_document_changes'] is False
"""
  assert text.count(needle)==1;text=text.replace(needle,guard+needle)
  assert text.endswith("    main()\n");text=text[:-len("    main()\n")]+"    raise SystemExit(main())\n"
 write(name.replace('source61','source63'),text)
print('Prepared real registered CLI63 loop/DF3/MuseTalk checks;not executed or activated.',flush=True)
