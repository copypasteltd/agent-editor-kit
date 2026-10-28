"""Extend the byte/link/push auditor to the actual HLG black delivery."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];s=(ROOT/'scripts/audit_icc_20261028.py').read_text('utf8')
for a,b in [('native-ICC','native-HLG-black'),('native-icc','native-hlg-black'),('0.1.46','0.1.47'),('local.44','local.45'),
 ('66c25f8d5f9deec0cbbf5d58e46e0377b92ce3aa','404816054cbc659ca3acfa46288ce892969641f7'),
 ('==269','==270'),('product_files=269','product_files=270'),('==85','==86'),('capabilities=85','capabilities=86'),('skill_files=85','skill_files=86'),
 ("test_counts['installed-r1']==26","test_counts['installed-r1']==21"),("test_counts['installed-compat-r1']==287","test_counts['installed-compat-r1']==314"),
 ('<2e-4','<1e-6'),('activation-final-r2','activation-final-r1'),('r47','r48'),('==138','==140'),
 ('ICC_PROFILES.md','HLG_BLACK_LEVEL.md'),('icc-capabilities','hlg-black-capabilities'),
 ('==315','==321'),('R=315','R=321'),('==309','==315'),('prior_R_retained=309','prior_R_retained=315'),
 ('==72','==73'),('F=72','F=73'),("len(rows(s,'S'))==27","len(rows(s,'S'))==28"),
 ("len(rows(m,'S'))==27","len(rows(m,'S'))==28"),('S=27','S=28'),('原生ICC色彩管理实测','HLG显示黑位实测')]:s=s.replace(a,b)
s=s.replace("assert case['ICC_profile_parsed'] and not case['full_ACES_transform']","assert not case['ICC_profile_parsed'] and not case['full_ACES_transform']")
start=s.index("        assert pixel['working_signal']");stop=s.index("        gpu=pixel[",start)
s=s[:start]+'''        assert pixel['working_signal']==dict(primaries='bt2020',transfer='linear',reference_white_nits=203,display_peak_nits=None,system_gamma=None)
        boundary=pixel['source_receipts']['chart']['color_boundary']['HLG_black_level']
        assert boundary['source']['display_black_nits']==.5 and not boundary['black_luminance_inferred']
'''+s[stop:]
s=s.replace("for path in ('source-r1','source-r2'):","for path in ('source-r1',):")
p=ROOT/'scripts/audit_hlg_black_20261028.py';assert not p.exists();p.write_text(s,encoding='utf8',newline='\n');print(p)
