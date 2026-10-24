"""Verify installed CUDA voice/translation and explicit CPU fallback on Windows."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed',type=Path,required=True)
    parser.add_argument('--cpu-packs',type=Path,required=True)
    parser.add_argument('--gpu-packs',type=Path,required=True)
    parser.add_argument('--voice-cuda-lib',type=Path,required=True)
    parser.add_argument('--translation-cuda-lib',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    prefix=[sys.executable,'-I','-S','-B','-u','-X','utf8',str(a.installed.resolve()/'run.py')]
    rows=[]
    def cli(name,args,error=None):
        start=time.perf_counter();argv=[*prefix,*map(str,args)]
        r=subprocess.run(argv,capture_output=True,timeout=360,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.json')).write_bytes(r.stdout);(out/(name+'.stderr.txt')).write_bytes(r.stderr)
        d=json.loads(r.stdout)
        rows.append(dict(id=name,argv=argv,exit_code=r.returncode,ok=d['ok'],seconds=time.perf_counter()-start))
        (out/'commands.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(json.dumps(rows[-1],ensure_ascii=False),flush=True)
        if error:assert r.returncode and d['errors'][0]['code']==error,d
        else:assert r.returncode==0 and d['ok'],d
        return d.get('data',{})
    gpu=cli('gpu-inspect',['gpu','inspect']);assert gpu['available']
    project=out/'GPU 本地可编辑工程';cli('init',['project','init',project])
    base=['--project',project];voicepack=a.cpu_packs.resolve()/'kokoro-zh-en-int8';mtpack=a.cpu_packs.resolve()/'opus-zh-en-cpu-int8'
    gv=a.gpu_packs.resolve()/'kokoro-zh-en-cuda13';gt=a.gpu_packs.resolve()/'opus-zh-en-cuda12-int8'
    cli('gpu-voice-pack-verify',['model-pack','verify','--id',gv.name,'--pack',gv])
    cli('gpu-translation-pack-verify',['model-pack','verify','--id',gt.name,'--pack',gt])
    voiceargs=['voice','synthesize',*base,'--pack',voicepack,'--gpu-pack',gv,'--voice','zf_001',
               '--text','本地显卡配音测试，保留原声与独立字幕。','--cuda-library-directory',a.voice_cuda_lib.resolve()]
    voice=cli('voice-cuda',[*voiceargs,'--device','cuda','--asset-id','asset_voice_cuda'])
    assert voice['device']['selected']=='cuda' and voice['synthesis']['provider']=='cuda'
    assert voice['synthesis']['cuda_provider_dll_loaded'] and voice['synthesis']['rms']>0.001
    translation=['translate','text',*base,'--pack',mtpack,'--gpu-pack',gt,'--from','zh-Hans','--to','en',
                 '--text','保留原声、字幕和背景音乐。','--cuda-library-directory',a.translation_cuda_lib.resolve()]
    translated=cli('translate-auto-cuda',[*translation,'--device','auto','--output','exports/gpu.txt'])
    assert translated['device']['selected']=='cuda' and translated['inference']['provider']=='cuda'
    assert translated['inference']['compute_type']=='int8_float16'
    subtitle=out/'gpu-input.srt';subtitle.write_text('1\n00:00:00,123 --> 00:00:01,987\nKeep the background music.\n',encoding='utf8')
    sub=cli('translate-gpu-subtitles',['translate','subtitles',*base,'--pack',mtpack,'--gpu-pack',gt,
        '--device','cuda','--from','en','--to','zh-Hant','--input',subtitle,'--output','exports/gpu.srt',
        '--cuda-library-directory',a.translation_cuda_lib.resolve()])
    assert sub['device']['selected']=='cuda' and sub['source_cues'][0]['start']==sub['output_cues'][0]['start']==0.123
    # Model-pair and file protection remain explicit with device routing.
    missing=cli('strict-cuda-no-pack',['translate','text',*base,'--pack',mtpack,'--device','cuda',
        '--from','en','--to','zh-Hans','--text','Preview the edit.','--output','exports/refused.txt'],error='GPU_PACK_REQUIRED')
    cli('strict-cuda-invalid-device',[*translation,'--device','cuda','--device-index','999',
        '--output','exports/refused-device.txt'],error='GPU_UNAVAILABLE')
    fallback=cli('auto-cpu-unavailable-device',[*translation,'--device','auto','--device-index','999',
        '--output','exports/cpu-fallback.txt'])
    assert fallback['device']['selected']=='cpu' and fallback['device']['fallback_reason']=='gpu_not_available'
    empty=out/'missing-cuda-libraries';empty.mkdir()
    broken=['translate','text',*base,'--pack',mtpack,'--gpu-pack',gt,'--from','en','--to','zh-Hans',
            '--text','Keep the background music.','--cuda-library-directory',empty]
    retry=cli('auto-cpu-worker-failure',[*broken,'--device','auto','--output','exports/cpu-worker-fallback.txt'])
    assert retry['device']['selected']=='cpu' and retry['device']['fallback_reason']=='cuda_inference_failed'
    cli('strict-cuda-worker-failure',[*broken,'--device','cuda','--output','exports/refused-worker.txt'],error='COMMUNITY_MODEL_FAILED')
    assert not (project/'exports/refused-worker.txt').exists()
    cpu=cli('explicit-cpu',[*translation,'--device','cpu','--output','exports/explicit-cpu.txt'])
    assert cpu['inference']['provider']=='cpu'
    cli('validate',['validate',*base]);cli('policy',['policy','audit',*base])
    report=dict(status='passed-with-review-limits',installed=str(a.installed.resolve()),commands=len(rows),gpu=gpu,
        cuda_voice=True,cuda_translation=True,gpu_subtitle_time_preserved=True,auto_gpu_preferred=True,
        explicit_cpu=True,unavailable_device_fallback=True,failed_gpu_worker_fallback=True,strict_cuda_failure=True,
        source_fallback=False,native_windows=True,virtualization=False,network=False,
        voice_output=str(project/voice['asset']['uri']),voice_output_sha256=hashlib.sha256((project/voice['asset']['uri']).read_bytes()).hexdigest(),
        human_listening=False,human_translation_acceptance=False,all_gpu_faster_claim=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
