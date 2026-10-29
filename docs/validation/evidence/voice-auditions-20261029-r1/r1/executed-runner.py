"""Generate all 103 actual local CUDA voice auditions through installed public CLI.

Audio remains internal/unverified; a local gallery is not publication approval.
"""
import argparse
from array import array
import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/voice-auditions-20261029-r1'
PYTHON='C:/Python313/python.exe'


def load(path):return json.loads(path.read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def clock(seconds):
    minutes,second=divmod(seconds,60);hour,minute=divmod(minutes,60)
    return f'{hour:02}:{minute:02}:{second:02},000'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True)
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    installation=load(ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1/installation-candidate-r1/verification.json')
    assert installation['status']=='installed-and-byte-verified' and installation['cli_version']=='0.1.61'
    installed=Path(installation['installed']);package=installed/'site/ai_ad_editor'
    source=ROOT/'product/src/ai_ad_editor'
    pins={p.name:sha(p) for p in package.glob('*.py')}
    assert len(pins)==283 and pins=={p.name:sha(p) for p in source.glob('*.py')}
    guard=installation['registered_skill_file_hashes']
    assert len(guard)==95 and all(sha(p)==h for p,h in guard.items())
    out=BASE/args.run;out.mkdir(parents=True,exist_ok=False)
    work=ROOT/'local/agent-ffmpeg'/('voice-preview61-'+args.run);work.mkdir(exist_ok=False)
    gallery=work/'preview';gallery.mkdir();(gallery/'audio').mkdir()
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    calls=[];rows=[];batches=[]
    def cli(name,*argv):
        command=[PYTHON,'-I','-S','-B','-u','-X','utf8',str(installed/'run.py'),*map(str,argv)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=3900,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout')).write_bytes(result.stdout);(out/(name+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name,command=command,exit_code=result.returncode));save(out/'calls.json',calls)
        print(json.dumps(dict(phase=name,exit_code=result.returncode)),flush=True)
        assert result.returncode==0,(name,result.stdout[-1800:],result.stderr[-1800:])
        response=json.loads(result.stdout);assert response['ok'] and response['provenance']['cli_version']=='0.1.61'
        return response['data']
    try:
        voices=cli('voices','voice','list')['voices']
        assert len(voices)==103 and len({row['id'] for row in voices})==103
        assert {row['speaker_id'] for row in voices}==set(range(103))
        for language,count,text in [('en',3,'This is a local voice preview. Please listen before choosing.'),
                                    ('zh',100,'这是本地语音试听，请听清每个字，再选择适合的声音。')]:
            selected=[v for v in voices if v['language']==language];assert len(selected)==count
            project=work/(language+'-project');cli(language+'-init','project','init',project)
            srt=work/(language+'.srt');mapping=work/(language+'-voices.json')
            srt.write_text('\n\n'.join(f'{i}\n{clock((i-1)*30)} --> {clock(i*30)}\n{text}'
                                      for i in range(1,count+1))+'\n',encoding='utf-8')
            save(mapping,dict(cues={str(i):v['id'] for i,v in enumerate(selected,1)}))
            tag='en' if language=='en' else 'zh-Hans'
            result=cli(language+'-synthesize','dub','subtitles','--project',project,'--input',srt,
                       '--from',tag,'--to',tag,'--id',language+'_auditions','--voice-map',mapping,
                       '--voice-device','cuda','--device','cuda','--fit','reject','--speed','1',
                       '--timeout-seconds','3600')
            assert result['cue_count']==count and result['total_generations']==count and result['model_initializations']==1
            assert result['fit_status']=='fits' and not result['truncation']
            assert result['devices']['voice']['selected']=='cuda' and not result['devices']['voice'].get('fallback_reason')
            assert 'translation' not in result['devices']
            report=load(Path(result['report']));assert report['text_mode']=='preserve-original' and not report['translation_attempts']
            attempts=report['voice_attempts'];assert len(attempts)==1
            engine=attempts[0]['result'];assert engine['provider']=='cuda' and engine['cuda_provider_dll_loaded']
            assert engine['model_initializations']==1 and engine['total_generations']==count and engine['network']=='disabled'
            assert len(report['cues'])==count
            author=load(project/'project.json');assets={a['id']:a for a in author['assets']}
            ledger=load(project/'rights-ledger.json')
            archive=work/(language+'-auditions.zip')
            cli(language+'-export','convert','export','--project',project,'--output',archive,'--target-format','package')
            replay=work/(language+'-replay');cli(language+'-import','convert','import','--input',archive,'--output',replay)
            restored={a['id']:a for a in load(replay/'project.json')['assets']}
            for voice,cue in zip(selected,report['cues']):
                assert cue['voice']['id']==voice['id'] and cue['voice']['speaker_id']==voice['speaker_id']
                assert cue['source_text']==cue['translation']==text and len(cue['attempts'])==1
                asset=assets[cue['final_asset_id']];path=project/asset['uri']
                assert 'sha256:'+sha(path)==asset['sha256']==restored[asset['id']]['sha256']
                assert sha(path)==sha(replay/restored[asset['id']]['uri'])
                with wave.open(str(path),'rb') as wav:
                    assert (wav.getframerate(),wav.getnchannels(),wav.getsampwidth())==(24000,1,2)
                    frames=wav.getnframes();raw=wav.readframes(frames)
                    assert 0<frames<=720000 and len(raw)==frames*2 and not wav.readframes(1)
                samples=array('h');samples.frombytes(raw)
                rms=math.sqrt(sum(v*v for v in samples)/frames)/32768
                assert math.isfinite(rms) and rms>.0001 and frames==cue['final_samples']
                # Keep generated audio local, with its original unverified ledger.
                destination=gallery/'audio'/(voice['id']+'.wav');shutil.copyfile(path,destination)
                rows.append(dict(number=voice['speaker_id']+1,voice_id=voice['id'],speaker_id=voice['speaker_id'],
                                 language=language,gender=voice['gender'],text=text,frames=frames,
                                 duration_seconds=frames/24000,PCM_bytes=len(raw),PCM_sha256=hashlib.sha256(raw).hexdigest(),
                                 WAV_sha256=sha(destination),rms=rms,preview=destination.relative_to(gallery).as_posix(),
                                 asset_id=asset['id'],project=str(project),full_package_PCM_equal=True,
                                 human_listening=False,naturalness_accepted=False,rights='internal-unverified'))
            batches.append(dict(language=language,voices=count,model_initializations=1,total_generations=count,
                                device='cuda',CPU_fallback=False,CUDA_provider_loaded=True,
                                translation_inference=False,report=str(result['report']),archive=str(archive),
                                pack=engine['pack'],rights_ledger_sha256=sha(project/'rights-ledger.json')))
            save(out/'progress.json',dict(status='running',completed_voices=len(rows),batches=batches))
        assert len(rows)==103 and {r['voice_id'] for r in rows}=={r['id'] for r in voices}
        assert pins=={p.name:sha(p) for p in source.glob('*.py')}=={p.name:sha(p) for p in package.glob('*.py')}
        assert all(sha(p)==h for p,h in guard.items())
        rows.sort(key=lambda r:r['number']);save(gallery/'voices.json',dict(voices=rows,rights='internal-unverified',human_listening=False))
        cards='\n'.join('<article><h2>'+html.escape(r['voice_id'])+'</h2><p>'+html.escape(r['language']+' / '+r['gender'])+
                        f' / {r["duration_seconds"]:.2f}s</p><audio controls preload="none" src="'+r['preview']+
                        '"></audio><p>'+html.escape(r['text'])+'</p></article>' for r in rows)
        (gallery/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>103 local voice auditions</title>'
            '<style>body{font:16px system-ui;background:#111827;color:#f1f5f9;padding:28px}main{display:grid;'
            'grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}article{background:#1e293b;padding:16px;'
            'border-radius:12px}audio{max-width:100%}</style><h1>103 本地 CUDA 音色试听</h1>'
            '<p>内部／权利未核验。未完成人类听审、发音或自然度验收；请先试听并明确选择。未使用真人参考克隆。'
            'Internal / unverified rights. Generated previews do not establish naturalness or pronunciation quality.</p><main>'+cards+'</main>',encoding='utf-8')
        summary=dict(status='passed',cli_version='0.1.61',installed=str(installed),source_fallback=False,
                     voices=103,Chinese_voices=100,English_voices=3,total_model_initializations=2,
                     actual_CUDA_generations=103,CPU_fallback=False,translation_inference=False,
                     all_full_PCM_package_replay_equal=True,protected_files_unchanged=95,
                     source_installed_283_modules_frozen=True,local_gallery=str(gallery/'index.html'),
                     audio_published=False,human_listening=False,naturalness_accepted=False,
                     rights='internal-unverified',batches=batches,voice_records=rows)
        save(out/'verification.json',summary)
        print(json.dumps({k:v for k,v in summary.items() if k not in ['voice_records','batches']},ensure_ascii=False),flush=True)
    except BaseException as error:
        save(out/'verification.json',dict(status='failed',error=repr(error),completed_voices=len(rows),batches=batches))
        raise


if __name__=='__main__':main()
