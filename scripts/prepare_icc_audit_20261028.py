"""Extend the previous byte/link/push auditor to actual ICC source delivery."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=(ROOT/'scripts/audit_chromatic_20261028.py').read_text('utf8')
for a,b in [('native-white','native-ICC'),('native-chromatic','native-icc'),('0.1.45','0.1.46'),('local.43','local.44'),
            ('9ba52a7dee4d3f1d992c3c8a1cd137973ca2b4e0','66c25f8d5f9deec0cbbf5d58e46e0377b92ce3aa'),
            ('==268','==269'),('product_files=268','product_files=269'),('==84','==85'),('capabilities=84','capabilities=85'),('skill_files=84','skill_files=85'),
            ("test_counts['installed-r1']==20","test_counts['installed-r1']==26"),('case-r3','case-r1'),
            ('<1.3e-7','<2e-4'),('native-icc-20261028-r3','native-icc-20261028-r1'),("assert not case['ICC_profile_parsed']","assert case['ICC_profile_parsed']"),
            ("('source-r1','case-r1','case-r2')","('source-r1','source-r2')"),
            ('activation-final-r1','activation-final-r2'),('r46','r47'),('==136','==138'),('==135','==137'),
            ('CHROMATIC_ADAPTATION.md','ICC_PROFILES.md'),('chromatic-capabilities','icc-capabilities'),
            ('==309','==315'),('R=309','R=315'),('==303','==309'),('prior_R_retained=303','prior_R_retained=309'),
            ('==71','==72'),('F=71','F=72'),('==26 and len(rows','==27 and len(rows'),
            ("len(rows(m,'S'))==26","len(rows(m,'S'))==27"),('S=26','S=27'),
            ('明确白点色适应实测','原生ICC色彩管理实测')]:s=s.replace(a,b)
# S row in the full README assertion is followed by K and has been handled above.
s=s.replace("assert test_counts['source-r3']==test_counts['installed-r1']==26 and test_counts['installed-compat-r1']>100",
    "assert test_counts['source-r3']==test_counts['installed-r1']==26 and test_counts['installed-compat-r1']==287")
needle="        assert (source/'agent-project.schema.json').read_bytes()";assert needle in s
s=s.replace(needle,"        for name,digest in install['native_ICC_artifacts'].items():assert sha(source/name)==sha(installed/'site/ai_ad_editor'/name)==digest\n"+needle,1)
needle="        assert pixel['transport']['clipped_RGB_components']>0";assert needle in s
s=s.replace(needle,needle+"\n        cmm=pixel['source_receipts']['chart']['ICC_transform'];assert cmm['native_handles_closed'] and cmm['CMM_encoded_version']==2190 and cmm['rendering_intent']=='relative-colorimetric'\n"
    "        assert 'sha256:'+case['original_ICC_sha256']==cmm['source_profile']['sha256']\n"
    "        assert sha(Path(case['project'])/'assets/source.icc')==sha(Path(case['restored'])/'assets/source.icc')==case['original_ICC_sha256']",1)
needle='        checked=[]';assert needle in s
s=s.replace(needle,"        assert not any(name.startswith('sources/littlecms-2.19.1/') for name in changes)\n"+needle,1)
p=ROOT/'scripts/audit_icc_20261028.py';assert not p.exists();p.write_text(s,encoding='utf8',newline='\n')
print('Prepared ICC source/installed/evidence/kit/document/staged/push auditor.')
