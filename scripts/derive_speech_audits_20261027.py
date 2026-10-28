"""Retarget existing staged and committed byte audits, keeping their checks."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for old,new in [('audit_interpolation_stage_20261027.py','audit_speech_enhancement_stage_20261027.py'),
                ('verify_interpolation_postpush_20261027.py','verify_speech_enhancement_postpush_20261027.py')]:
    s=(ROOT/'scripts'/old).read_text('utf8')
    for a,b in [('656d136f2677d7ce07c4bb9734370cc7f9147e50','009efac332aaa0099b4e694d13370463f2b9f3d8'),
                ('native-interpolation','native-speech-enhancement'),('0.1.42','0.1.43'),('257','266'),
                ("len(manifest['files'])==81","len(manifest['files'])==82"),("len(namespace['files'])==81","len(namespace['files'])==82"),
                ("'skill_files':81","'skill_files':82"),('skill_files=81','skill_files=82'),
                ('installed-interpolation-r1','installed-enhancement-r3'),('installation-final-r1','installation-final-r3'),
                ("tests['tests']==37","tests['tests']==33"),('unique_installed_tests=37','unique_installed_tests=33'),('total_test_executions=37','total_test_executions=33')]:s=s.replace(a,b)
    (ROOT/'scripts'/new).write_text(s,encoding='utf8',newline='\n')
print('Speech staged/committed byte audit scripts prepared.')
