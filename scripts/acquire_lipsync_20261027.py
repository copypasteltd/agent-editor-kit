"""Acquire pinned official MuseTalk/Whisper/VAE artifacts on E, outside runtime.

Explicit developer acquisition only. Product inference never downloads weights.
Retain source licenses and upstream hashes, including weights-only conversion.
"""
from pathlib import Path
import argparse, base64, hashlib, json, time, urllib.request
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
MODEL=ROOT/'product/.runtime/models/musetalk-v15-20261027'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request,timeout=30) as f:return f.read()
        except (OSError,urllib.error.URLError):
            if attempt==2:raise

def save(p,data):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--weights',action='store_true')
    parser.add_argument('--endpoint',choices=('https://huggingface.co','https://hf-mirror.com'),default='https://huggingface.co');a=parser.parse_args()
    BASE.mkdir(parents=True,exist_ok=True);MODEL.mkdir(parents=True,exist_ok=True)
    meta=BASE/'acquisition-metadata.json'
    if meta.exists():inventory=json.loads(meta.read_bytes())
    else:
        git=json.loads(fetch('https://api.github.com/repos/TMElyralab/MuseTalk/commits/main'))
        inventory={'at_utc':datetime.now(timezone.utc).isoformat(),'github_commit':git['sha'],'transport_endpoint':a.endpoint,'models':{}}
        for repo in ('TMElyralab/MuseTalk','stabilityai/sd-vae-ft-mse','openai/whisper-tiny'):
            value=json.loads(fetch(a.endpoint+'/api/models/'+repo+'?blobs=true'))
            inventory['models'][repo]=value
        save(meta,(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    commit=inventory['github_commit']
    for name in ('LICENSE','README.md','musetalk/models/unet.py','musetalk/models/vae.py',
                 'musetalk/utils/audio_processor.py','musetalk/utils/blending.py','scripts/inference.py'):
        target=BASE/'upstream-code'/name
        if not target.exists():
            source=json.loads(fetch('https://api.github.com/repos/TMElyralab/MuseTalk/contents/'+name+'?ref='+commit))
            assert source['encoding']=='base64'
            save(target,base64.b64decode(source['content']))
    selected={
        'TMElyralab/MuseTalk':{'LICENSE.txt':'licenses/MuseTalk-LICENSE.txt','README.md':'licenses/MuseTalk-README.md',
            'musetalkV15/musetalk.json':'unet/config.json','musetalkV15/unet.pth':'upstream/unet.pth'},
        'stabilityai/sd-vae-ft-mse':{'README.md':'licenses/VAE-README.md','config.json':'vae/config.json',
            'diffusion_pytorch_model.safetensors':'vae/diffusion_pytorch_model.safetensors'},
        'openai/whisper-tiny':{'README.md':'licenses/Whisper-README.md','config.json':'whisper/config.json',
            'preprocessor_config.json':'whisper/preprocessor_config.json','model.safetensors':'whisper/model.safetensors'},
    }
    rows=[]
    for repo,names in selected.items():
        value=inventory['models'][repo];revision=value['sha'];siblings={r['rfilename']:r for r in value['siblings']}
        assert value.get('cardData',{}).get('license') in {'mit','apache-2.0'},(repo,value.get('cardData',{}).get('license'))
        for name,dest in names.items():
            info=siblings[name];lfs=info.get('lfs');target=MODEL/dest
            expected=lfs.get('sha256') if lfs else None
            url=a.endpoint+'/'+repo+'/resolve/'+revision+'/'+name
            if not lfs:
                if not target.exists():save(target,fetch(url))
            elif a.weights:
                if target.exists():assert sha(target)==expected
                else:
                    partial=target.with_suffix(target.suffix+'.partial');partial.parent.mkdir(parents=True,exist_ok=True)
                    for attempt in range(1,4):
                        offset=partial.stat().st_size if partial.exists() else 0
                        headers={'User-Agent':'Mozilla/5.0'}
                        if offset:headers['Range']='bytes='+str(offset)+'-'
                        try:
                            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=60) as stream:
                                mode='ab' if offset and stream.status==206 else 'wb'
                                with partial.open(mode) as f:
                                    last=time.monotonic()
                                    while chunk:=stream.read(4*1024**2):
                                        f.write(chunk)
                                        if time.monotonic()-last>=15:
                                            print(json.dumps({'file':dest,'bytes':f.tell(),'expected':lfs['size']}),flush=True);last=time.monotonic()
                            assert partial.stat().st_size==lfs['size'] and sha(partial)==expected
                            partial.rename(target);break
                        except BaseException:
                            if attempt==3:raise
            row={'repo':repo,'revision':revision,'source_file':name,'path':dest,'expected_sha256':expected,'upstream_size':info.get('size')}
            if target.exists():row.update(bytes=target.stat().st_size,sha256=sha(target))
            rows.append(row)
    save(BASE/'acquisition-files.json',(json.dumps(rows,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    print(json.dumps({'status':'weights-acquired' if a.weights else 'metadata-and-code-acquired','github_commit':commit,
        'model':str(MODEL),'files':len(rows),'downloaded':sum('sha256' in r for r in rows)},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
