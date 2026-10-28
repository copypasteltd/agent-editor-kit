"""Prepare immutable r47 kit verification and exact-byte ICC evidence rules."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for source,target in [('publish_chromatic_20261028.py','publish_icc_20261028.py'),('verify_chromatic_kit_20261028.py','verify_icc_kit_20261028.py')]:
    s=(ROOT/'scripts'/source).read_text('utf8')
    for a,b in [('native-chromatic','native-icc'),('0.1.45','0.1.46'),('r46','r47'),('==136','==138'),('files=136','files=138'),
                ('==135','==137'),('==84','==85'),('skill_files=84','skill_files=85'),
                ('native_chromatic_adaptation','native_icc_source_profiles'),('explicit-white-Bradford-float32-v1','explicit-native-icc-source-float32-v1'),
                ('native-icc-20261028-r3/editable-chromatic.aevpkg.zip','native-icc-20261028-r1/editable-icc.aevpkg.zip'),
                ('portable_white_signal_validated','portable_ICC_profile_validated'),('installed chromatic','installed ICC'),('portable-hdr10','portable-icc')]:s=s.replace(a,b)
    if source.startswith('verify_'):
        needle="    assert plan['plan']['command']";assert needle in s
        s=s.replace(needle,"    profile=load(project/'project.json')['settings']['pixel_pipeline']['sources']['chart']['source_signal']\n"
            "    assert 'sha256:'+sha(project/profile['icc_profile'])==profile['sha256']\n"
            "    inspected=cli('profile','surface','inspect-profile','--project',project,'--input',profile['icc_profile'])\n"
            "    assert inspected['native_handles_closed'] and inspected['CMM_encoded_version']==2190\n"+needle,1)
    p=ROOT/'scripts'/target;assert not p.exists();p.write_text(s,encoding='utf8',newline='\n')
p=ROOT/'scripts/package_community_skill.py';s=p.read_text('utf8');assert "'ICC_PROFILES.md'" not in s
s=s.replace("'CHROMATIC_ADAPTATION.md',","'CHROMATIC_ADAPTATION.md', 'ICC_PROFILES.md',",1);p.write_text(s,encoding='utf8',newline='\n')
p=ROOT/'.gitattributes';s=p.read_text('utf8');s+='''
# Preserve native CMM, profile and actual ICC evidence bytes.
product/src/ai_ad_editor/avk_lcms_*.dll -text -diff
product/src/ai_ad_editor/native_icc_manifest.json -text -whitespace
product/src/ai_ad_editor/LITTLECMS_LICENSE.txt -text -whitespace
docs/validation/evidence/native-icc-20261028-r1/** -text -whitespace
docs/assets/native-icc-20261028-*/** -text -whitespace
docs/product/icc-capabilities-cli-0.1.46.json -text -whitespace
scripts/*icc*20261028.py text eol=lf
docs/product/ICC_PROFILES.md text eol=lf
docs/releases/CLI_0.1.46_LOCAL.md text eol=lf
docs/validation/原生ICC色彩管理实测_2026-10-28.md text eol=lf
''';p.write_text(s,encoding='utf8',newline='\n')
print('Prepared r47 kit checks and exact-byte native ICC attributes.')
