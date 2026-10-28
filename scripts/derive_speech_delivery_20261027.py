"""Reuse verified offline build/activation mechanics for the new native release."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for old,new in [('build_interpolation_20261027.py','build_speech_enhancement_20261027.py'),('activate_interpolation_20261027.py','activate_speech_enhancement_20261027.py')]:
    source=ROOT/'scripts'/old;target=ROOT/'scripts'/new;assert not target.exists()
    text=source.read_text('utf8').replace('native-interpolation-20261027-r1','native-speech-enhancement-20261027-r1').replace('v0.1.0-alpha.4-local.40','v0.1.0-alpha.4-local.41').replace('0.1.42','0.1.43')
    target.write_text(text,encoding='utf8',newline='\n')
print('created source-frozen offline build and activation scripts')
