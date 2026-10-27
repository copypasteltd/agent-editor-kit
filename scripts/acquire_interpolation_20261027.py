"""Acquire pinned official MIT Practical-RIFE code and its explicitly linked model."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,base64,hashlib,json,time,urllib.request,urllib.error,zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-interpolation-20261027-r1'
MODEL=ROOT/'product/.runtime/models/rife-v4.25-20261027'
DRIVE_ID='1ZKjcbmt1hypiFprJPIKW0Tt0lr_2i7bg'
def save(p,data):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def fetch(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30) as response:return response.read()
        except (OSError,urllib.error.URLError):
            if attempt==2:raise
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--weights',action='store_true');a=ap.parse_args()
    BASE.mkdir(parents=True,exist_ok=True);MODEL.mkdir(parents=True,exist_ok=True)
    path=BASE/'acquisition-metadata.json'
    if path.exists():meta=json.loads(path.read_bytes())
    else:
        commit=json.loads(fetch('https://api.github.com/repos/hzwer/Practical-RIFE/commits/main'))['sha']
        meta=dict(status='metadata',at_utc=datetime.now(timezone.utc).isoformat(),repository='hzwer/Practical-RIFE',commit=commit,model='4.25',official_drive_id=DRIVE_ID,files=[])
        save(path,(json.dumps(meta,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
    rows=[]
    for name in ('LICENSE','README.md','model/warplayer.py','inference_video.py'):
        p=BASE/'upstream-code'/name
        if not p.exists():
            d=json.loads(fetch('https://api.github.com/repos/hzwer/Practical-RIFE/contents/'+name+'?ref='+meta['commit']));assert d['encoding']=='base64';save(p,base64.b64decode(d['content']))
        rows.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
    readme=(BASE/'upstream-code/README.md').read_text('utf8');assert DRIVE_ID in readme and 'under the same MIT license' in readme
    if a.weights:
        archive=MODEL/'upstream/RIFEv4.25_0919.zip';archive.parent.mkdir(parents=True,exist_ok=True)
        if not archive.exists():
            partial=archive.with_suffix('.partial')
            url='https://drive.usercontent.google.com/download?id='+DRIVE_ID+'&export=download&authuser=0&confirm=t'
            started=time.monotonic();last=started
            with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=60) as response,partial.open('wb') as output:
                content_type=response.headers.get('Content-Type','');assert 'text/html' not in content_type,content_type
                while chunk:=response.read(1024**2):
                    output.write(chunk);assert output.tell()<=256*1024**2,'archive budget'
                    if time.monotonic()-last>=10:print(json.dumps(dict(stage='download',bytes=output.tell())),flush=True);last=time.monotonic()
            assert zipfile.is_zipfile(partial);partial.rename(archive)
        with zipfile.ZipFile(archive) as z:
            names=z.namelist();assert len(names)<=100
            for info in z.infolist():
                p=Path(info.filename)
                assert not p.is_absolute() and '..' not in p.parts and ':' not in info.filename and info.file_size<=256*1024**2
                if info.is_dir():continue
                data=z.read(info)
                target=MODEL/'upstream/unpacked'/p
                if target.exists():assert target.read_bytes()==data
                else:save(target,data)
        meta.update(status='official-archive-acquired',archive=dict(path=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,members=names))
    meta['files']=rows;save(path,(json.dumps(meta,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps({k:meta[k] for k in ('status','commit','model')}) ,flush=True)
if __name__=='__main__':main()
