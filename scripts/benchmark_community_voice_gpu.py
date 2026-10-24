"""Native CPU/CUDA Kokoro comparison with the same FP32 model and text.

This measures cold startup and two in-process generations separately. It does
not stop other GPU tasks or claim that every short CLI request gets faster.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def worker(args):
    pack=args.pack.resolve();sys.path[:0]=[str(pack/'site'),str(args.base_site.resolve())]
    holders=[os.add_dll_directory(str(pack/'bin')),os.add_dll_directory(str(args.cuda_lib.resolve()))]
    os.environ['PATH']=str(pack/'bin')+os.pathsep+str(args.cuda_lib.resolve())+os.pathsep+os.environ['PATH']
    import sherpa_onnx
    import numpy as np
    import wave
    os.chdir(pack/'models/kokoro')
    text='从本地素材开始，生成可编辑的视频。原声、字幕和配乐均可独立调整。'
    started=time.perf_counter()
    config=sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
        kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(model='model.onnx',voices='voices.bin',tokens='tokens.txt',lexicon='lexicon-zh.txt,lexicon-us-en.txt,lexicon-gb-en.txt'),
        num_threads=2,provider=args.worker,debug=args.worker=='cuda'),rule_fsts='date-zh.fst,number-zh.fst,phone-zh.fst',max_num_sentences=1)
    engine=sherpa_onnx.OfflineTts(config)
    rows=[];load=time.perf_counter()-started
    for index in range(2):
        t=time.perf_counter();audio=engine.generate(text,sid=3,speed=1.0);seconds=time.perf_counter()-t
        samples=np.asarray(audio.samples,dtype=np.float32);path=args.output/(args.worker+'-'+str(index)+'.wav')
        with wave.open(str(path),'wb') as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(audio.sample_rate)
            wav.writeframes((np.clip(samples,-1,1)*32767).round().astype('<i2').tobytes())
        rows.append(dict(run=index,seconds=seconds,audio_seconds=len(samples)/audio.sample_rate,rtf=seconds/(len(samples)/audio.sample_rate),rms=float(np.sqrt(np.mean(samples*samples)))))
    print(json.dumps(dict(provider=args.worker,load_seconds=load,text=text,same_fp32_model=True,generations=rows),ensure_ascii=False),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--pack',type=Path,required=True)
    p.add_argument('--base-site',type=Path,required=True);p.add_argument('--cuda-lib',type=Path,required=True)
    p.add_argument('--worker',choices=['cpu','cuda'])
    args=p.parse_args()
    if args.worker:return worker(args)
    args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=False)
    results=[]
    for device in ['cpu','cuda']:
        argv=[sys.executable,'-I','-S','-B','-u','-X','utf8',str(Path(__file__).resolve()),'--worker',device,
              '--pack',str(args.pack.resolve()),'--base-site',str(args.base_site.resolve()),'--cuda-lib',str(args.cuda_lib.resolve()),'--output',str(args.output)]
        r=subprocess.run(argv,capture_output=True,timeout=360,creationflags=subprocess.CREATE_NO_WINDOW)
        (args.output/(device+'.stdout.json')).write_bytes(r.stdout);(args.output/(device+'.stderr.txt')).write_bytes(r.stderr)
        if r.returncode:raise RuntimeError(r.stderr.decode('utf8',errors='replace')[-2000:])
        results.append(json.loads(r.stdout));print(json.dumps(results[-1],ensure_ascii=False),flush=True)
    (args.output/'benchmark.json').write_text(json.dumps(dict(results=results,human_listening=False,device_contention_uncontrolled=True),ensure_ascii=False,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
