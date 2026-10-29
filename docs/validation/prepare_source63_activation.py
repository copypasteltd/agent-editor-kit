"""Prepare the CLI63 guarded transition without editing the tested Skill."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/validation'
text=(DOC/'activate_source61_skill.py').read_text(encoding='utf-8')
for old,new in [('lipsync-timeout-20261029-r1','job-enumeration-20261029-r1'),
 ('source61','source63'),('installed61','installed63'),('staged61','staged63'),
 ('music61','music63'),('skill61','skill63'),('cli61','cli63'),('CLI61','CLI63'),
 ('0.1.61','0.1.63'),('v0.1.0-alpha.4-local.59','v0.1.0-alpha.4-local.61'),
 ("('control',19)","('control',26)"),("('contracts',403)","('contracts',406)")]:
 text=text.replace(old,new)
needle="    missing = [name for name,path in gates.items() if not path.is_file()]"
assert text.count(needle)==1
text=text.replace(needle,"    gates['skill_controller']=BASE/'skill-controller-r1/verification.json'\n"+needle)
old="    from source63_voice_skill_overlay import prepare\n    contents,registered_files,documentation_overlay=prepare(stage,files,reports['voice_auditions'])"
new="""    staging=load(stage.parents[1]/'STAGING.json')
    assert staging['status']=='unregistered-candidate' and staging['cli_version']=='0.1.63'
    assert staging['candidate_files']==files==reports['skill_controller']['candidate_files']
    assert reports['skill_controller']['installed406_accepted']
    assert reports['skill_controller']['actual_PowerShell_loop_DF3_MuseTalk_passed']
    assert reports['skill_controller']['voice_documentation_tested']
    assert staging['voice_auditions']['source_cli_version']=='0.1.61'
    assert staging['voice_auditions']['applied_before_candidate_tests']
    assert staging['voice_auditions']['voice_evidence_sha256']==sha(gates['voice_auditions'])
    assert all(sha(Path(path))==pin for path,pin in staging['gates'].items())
    # Documentation was included before candidate tests: register exact tested bytes.
    contents={name:(stage/name).read_bytes() for name in files}
    registered_files=dict(files)
    voice_auditions=staging['voice_auditions']"""
assert text.count(old)==1;text=text.replace(old,new)
text=text.replace('documentation_overlay=documentation_overlay','voice_auditions=voice_auditions,post_test_document_changes=False')
assert 'source63_voice_skill_overlay' not in text
old="            gates[mode+'_'+group] = BASE/(mode+'-'+group+'-r1/verification.json')"
new="            run='r2' if mode=='installed63' and group=='contracts' else 'r1'\n            gates[mode+'_'+group] = BASE/(mode+'-'+group+'-'+run+'/verification.json')"
assert text.count(old)==1;text=text.replace(old,new)
target=DOC/'activate_source63_skill.py';compile(text,str(target),'exec')
if target.exists():assert target.read_text(encoding='utf-8')==text
else:target.write_text(text,encoding='utf-8',newline='\n')
print('Prepared exact-tested-byte CLI63 activation with rollback;not applied.',flush=True)
