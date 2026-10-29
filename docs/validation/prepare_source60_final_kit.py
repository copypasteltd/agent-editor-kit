"""Prepare CLI60/r58 final kit checks, including actual loop recipe package replay."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def write(name,text):
    p=ROOT/'docs/validation'/name;assert not p.exists();compile(text,str(p),'exec');p.write_text(text,encoding='utf-8')

def main():
    text=(ROOT/'docs/validation/build_source59_final_kit.py').read_text(encoding='utf-8')
    text=text.replace('CLI59','CLI60').replace('r57','r58').replace('0.1.59','0.1.60')
    text=text.replace('music-score-20261029-r1','music-loop-20261029-r1')
    text=text.replace('skill59','skill60').replace('registered59','registered60').replace('music59','music60')
    text=text.replace("package['files'] == 160", "package['files'] == 161")
    write('build_source60_final_kit.py',text)
    text=(ROOT/'docs/validation/verify_source59_final_kit.py').read_text(encoding='utf-8')
    text=text.replace('CLI59','CLI60').replace('0.1.59','0.1.60').replace('music59','music60')
    text=text.replace('music-score-20261029-r1','music-loop-20261029-r1')
    text=text.replace('==159','==160').replace('==160 and len(z.namelist())==160','==160 and len(z.namelist())==161')
    text=text.replace('kit_entries=160,inventory_files=159','kit_entries=161,inventory_files=160')
    text=text.replace('==282','==283').replace('code_files=282','code_files=283')
    text=text.replace("{'docs/product/MUSIC_SCORE.md',", "{'docs/product/MUSIC_LOOP.md','docs/product/MUSIC_SCORE.md',")
    text=text.replace("load(BASE/'actual-case-r1/verification.json')['audio']['PCM_sha256']", "load(ROOT/'docs/validation/evidence/music-score-20261029-r1/actual-case-r1/verification.json')['audio']['PCM_sha256']")
    needle="    assert cli('catalog','surface','ocio-configs','--config','aces-2.1')['version']=='2.6.0'"
    assert needle in text
    text=text.replace(needle,'''    fixture=ROOT/'docs/assets/music-loop60-20261029-r1'
    cli('loop-ingest','media','ingest','--project',score_project,'--input',fixture/'source.wav',
        '--asset-id','loop_source','--license-spdx','CC0-1.0','--verification-status','verified',
        '--creator','Agent Editor Kit original C75 fragment','--evidence',fixture/'SOURCE.txt')
    loop=cli('loop-repair','music','repair-loop','--project',score_project,'--asset-id','loop_source',
        '--crossfade-ms','50','--new-asset-id','kit_loop')
    with wave.open(str(score_project/loop['asset']['uri']),'rb') as wav:
        assert (wav.getframerate(),wav.getnchannels(),wav.getnframes(),wav.getsampwidth())==(48000,2,639360,2)
        loop_pcm=wav.readframes(wav.getnframes())
    assert len(loop_pcm)==2557440 and hashlib.sha256(loop_pcm).hexdigest()==load(BASE/'actual-case-r1/verification.json')['complete_repaired_PCM_sha256']
    loop_zip=work/'score-loop.zip';cli('loop-export','convert','export','--project',score_project,'--output',loop_zip,'--target-format','package')
    loop_project=work/'score-loop-replay';cli('loop-import','convert','import','--input',loop_zip,'--output',loop_project)
    loop_again=cli('loop-repair-replay','music','repair-loop','--project',loop_project,
        '--input',loop_project/loop['recipe_uri'],'--new-asset-id','kit_loop_again')
    with wave.open(str(loop_project/loop_again['asset']['uri']),'rb') as wav:assert wav.readframes(wav.getnframes())==loop_pcm
'''+needle,1)
    text=text.replace('actual_music_compose=True,', 'actual_music_compose=True,actual_loop_repair=True,complete_loop_PCM_bytes=len(loop_pcm),complete_loop_package_repair_PCM_equal=True,')
    write('verify_source60_final_kit.py',text)
    print('Prepared r58 kit build and independent score/loop/ACES verification; not executed.')

if __name__=='__main__':main()
