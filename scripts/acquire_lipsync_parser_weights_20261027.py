"""Acquire the checkpoint linked by official MuseTalk, with frozen HF digest."""
import json,urllib.request
from acquire_lipsync_20261027 import BASE,MODEL,fetch,save,sha
meta_path=BASE/'parser-acquisition.json';endpoint='https://hf-mirror.com';repo='ManyOtherFunctions/face-parse-bisent'
if meta_path.exists():meta=json.loads(meta_path.read_bytes())
else:
    meta=json.loads(fetch(endpoint+'/api/models/'+repo+'?blobs=true'))
    save(meta_path,(json.dumps(meta,indent=2)+'\n').encode())
info=next(r for r in meta['siblings'] if r['rfilename']=='79999_iter.pth');expected=info['lfs']['sha256']
target=MODEL/'upstream/face-parser.pth';target.parent.mkdir(parents=True,exist_ok=True)
if not target.exists():
    url=endpoint+'/'+repo+'/resolve/'+meta['sha']+'/79999_iter.pth'
    request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    partial=target.with_suffix('.partial')
    with urllib.request.urlopen(request,timeout=60) as stream,partial.open('wb') as f:
        while block:=stream.read(4*1024**2):f.write(block)
    assert partial.stat().st_size==info['lfs']['size'] and sha(partial)==expected
    partial.rename(target)
assert sha(target)==expected
save(BASE/'parser-weights.json',(json.dumps({'repo':repo,'revision':meta['sha'],'file':'79999_iter.pth',
    'bytes':target.stat().st_size,'sha256':expected,'source_reference':'official MuseTalk download_weights.bat',
    'license_reference':'official MuseTalk LICENSE, MIT face-parsing.PyTorch'},indent=2)+'\n').encode())
print(json.dumps({'status':'acquired','bytes':target.stat().st_size,'sha256':expected}))
