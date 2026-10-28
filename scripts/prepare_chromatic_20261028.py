"""Reuse native build, activation and immutable-test mechanics for white management."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for source,target in [('build_hdr_metadata_20261028.py','build_chromatic_20261028.py'),('activate_hdr_metadata_20261028.py','activate_chromatic_20261028.py'),('test_hdr_metadata_20261028.py','test_chromatic_20261028.py')]:
    s=(ROOT/'scripts'/source).read_text('utf8')
    for a,b in [('native-hdr-metadata','native-chromatic'),('v0.1.0-alpha.4-local.42','v0.1.0-alpha.4-local.43'),('0.1.44','0.1.45')]:s=s.replace(a,b)
    if source.startswith('test_'):
        s=s.replace("'metadata':['test_hdr_metadata']","'chromatic':['test_float_chromatic']")
        s=s.replace("default='metadata'","default='chromatic'")
        s=s.replace("['test_float_hdr','test_float_standard_render','test_float_preview','test_schema_contract','test_queue_reuse']", "['test_float_color_signal','test_float_hdr','test_hdr_metadata','test_float_glow','test_float_standard_render','test_float_preview','test_float_bundle','test_float_bundle_source','test_float_lut','test_float_curves','test_schema_contract','test_queue_reuse']")
        s=s.replace("['test_float_hdr','test_float_standard_render']", "['test_float_hdr','test_float_standard_render','test_float_color_signal']")
    (ROOT/'scripts'/target).write_text(s,encoding='utf8',newline='\n')
print('prepared native white-management delivery scripts')
