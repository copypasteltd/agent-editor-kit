"""Prepare immutable r48 kit checks from the verified ICC delivery harness."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for source,target in [('publish_icc_20261028.py','publish_hlg_20261028.py'),('verify_icc_kit_20261028.py','verify_hlg_kit_20261028.py')]:
 s=(ROOT/'scripts'/source).read_text('utf8')
 for a,b in [('native-icc','native-hlg-black'),('0.1.46','0.1.47'),('r47','r48'),('==138','==140'),('files=138','files=140'),('==137','==139'),('==85','==86'),('skill_files=85','skill_files=86'),('editable-icc','editable-hlg-black'),('portable-icc','portable-hlg-black')]:s=s.replace(a,b)
 if source.startswith('verify_'):
  s=s.replace("assert caps['native_icc_source_profiles']['protocol']=='explicit-native-hlg-black-source-float32-v1'","assert caps['native_hlg_black_level']['protocol']=='explicit-HLG-display-black-float32-v1'")
  start=s.index("    assert load(project/'project.json')['settings']['pixel_pipeline']['working_signal']")
  stop=s.index("    assert plan['plan']['command']",start)
  s=s[:start]+'''    assert load(project/'project.json')['settings']['pixel_pipeline']['working_signal']==dict(primaries='bt2020',transfer='linear',reference_white_nits=203)
    signal=load(project/'project.json')['settings']['pixel_pipeline']['sources']['chart']['source_signal']
    assert signal['display_black_nits']==.5 and signal['display_peak_nits']==1000 and signal['system_gamma']==1.2
'''+s[stop:]
  s=s.replace('portable_ICC_profile_validated','portable_HLG_black_validated').replace('installed ICC','installed HLG black')
 p=ROOT/'scripts'/target;assert not p.exists();p.write_text(s,encoding='utf8',newline='\n')
p=ROOT/'scripts/package_community_skill.py';s=p.read_text('utf8');assert "'HLG_BLACK_LEVEL.md'" not in s
p.write_text(s.replace("'ICC_PROFILES.md',","'ICC_PROFILES.md', 'HLG_BLACK_LEVEL.md',",1),encoding='utf8',newline='\n')
p=ROOT/'.gitattributes';s=p.read_text('utf8');s+='''
# Preserve actual HLG black evidence/media and pinned capability bytes.
docs/validation/evidence/native-hlg-black-20261028-r1/** -text -whitespace
docs/assets/native-hlg-black-20261028-*/** -text -whitespace
docs/product/hlg-black-capabilities-cli-0.1.47.json -text -whitespace
scripts/*hlg*20261028.py text eol=lf
docs/product/HLG_BLACK_LEVEL.md text eol=lf
docs/releases/CLI_0.1.47_LOCAL.md text eol=lf
docs/validation/HLG显示黑位实测_2026-10-28.md text eol=lf
''';p.write_text(s,encoding='utf8',newline='\n')
print('Prepared r48 delivery checks.')
