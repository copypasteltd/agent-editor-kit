"""Prepare version-specific delivery checks, preserving CLI59 runners."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def write(name,text):
    path=ROOT/'docs/validation'/name
    assert not path.exists()
    compile(text,str(path),'exec');path.write_text(text,encoding='utf-8')

def main():
    text=(ROOT/'docs/validation/run_source59_gpu_case.py').read_text(encoding='utf-8')
    text=text.replace('CLI59','CLI60').replace('source59','source60').replace('installed59','installed60')
    text=text.replace('0.1.59','0.1.60').replace('music-score-20261029-r1','music-loop-20261029-r1')
    start=text.index('    audit=load(');end=text.index('    installed = ',start)
    text=text[:start]+'''    assert all(sha(ROOT/name)==pin for name,pin in gate['file_hashes'].items())
'''+text[end:]
    text=text.replace('len(pins) == 282','len(pins) == 283')
    write('run_source60_gpu_case.py',text)
    text=(ROOT/'docs/validation/run_source59_installed_regressions.py').read_text(encoding='utf-8')
    text=text.replace('CLI59','CLI60').replace('source59','source60').replace('installed59','installed60')
    text=text.replace('0.1.59','0.1.60').replace('music-score-20261029-r1','music-loop-20261029-r1')
    text=text.replace("GROUPS = {'score': ['test_music_score'],", "GROUPS = {'loop': ['test_music_loop', 'test_music_score'], 'score': ['test_music_score'],")
    text=text.replace("EXPECTED = {'score': 19,", "EXPECTED = {'loop': 37, 'score': 19,")
    text=text.replace("glob('*.py'))) == 282", "glob('*.py'))) == 283")
    write('run_source60_installed_regressions.py',text)
    print('Prepared source60 actual CUDA and independently installed regression runners.')

if __name__=='__main__':main()
