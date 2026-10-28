"""Derive native-only immutable runners from the last shipped delivery tools."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
replacements=[('native-hlg-black','native-icc-output'),('hlg_black','icc_output'),('0.1.47','0.1.48'),('local.45','local.46')]
for old,new in [('test_hlg_black','test_icc_output'),('build_hlg_black','build_icc_output'),('activate_hlg_black','activate_icc_output')]:
    source=(ROOT/'scripts'/(old+'_20261028.py')).read_text('utf8')
    for a,b in replacements:source=source.replace(a,b)
    if new=='test_icc_output':
        source=source.replace("'black':['test_float_icc_output']","'output':['test_icc_output']")
        source=source.replace("'compat':['test_icc_profiles'","'compat':['test_float_hlg_black','test_icc_profiles'")
        source=source.replace("default='black'","default='output'")
    (ROOT/'scripts'/(new+'_20261028.py')).write_text(source,encoding='utf8',newline='\n')
