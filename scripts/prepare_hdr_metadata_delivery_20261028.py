"""Derive native build/activation mechanics without rewriting previous evidence."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for source,target in [('build_speech_enhancement_20261027.py','build_hdr_metadata_20261028.py'),
                      ('activate_speech_enhancement_20261027.py','activate_hdr_metadata_20261028.py')]:
    text=(ROOT/'scripts'/source).read_text('utf8')
    for a,b in [('native-speech-enhancement-20261027-r1','native-hdr-metadata-20261028-r1'),
                ('v0.1.0-alpha.4-local.41','v0.1.0-alpha.4-local.42'),('0.1.43','0.1.44'),
                ('final-r3/installed','final-r1/installed')]:text=text.replace(a,b)
    (ROOT/'scripts'/target).write_text(text,encoding='utf8',newline='\n')
print('prepared native build and activation scripts')
