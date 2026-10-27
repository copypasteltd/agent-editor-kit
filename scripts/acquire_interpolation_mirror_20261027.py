"""Acquire checksum-pinned model mirrors after official Drive transport timed out."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,urllib.request,zipfile
from acquire_interpolation_20261027 import ROOT,BASE,MODEL,fetch,save,sha
def main():
    report=BASE/'mirror-acquisition.json';assert not report.exists()
    recorded=dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),status='official-download-failed',
        command='scripts/acquire_interpolation_20261027.py --weights',error='URLError WinError10060 timeout connecting to drive.usercontent.google.com',
        scope='Recorded from actual terminal failure; no model bytes acquired from official Drive.')
    save(BASE/'drive-attempt-r1.json',(json.dumps(recorded,indent=2)+'\n').encode('utf8'))
    endpoint='https://hf-mirror.com';meta=dict(status='running',source='unofficial mirror of official MIT Practical-RIFE4.25',endpoint=endpoint,models={})
    for repo,names in {'Bash2X/RIFE-Models':['README.md','RIFE_v4.25.zip'],'simonri/saferife':['README.md','rife-4.25.safetensors']}.items():
        model=json.loads(fetch(endpoint+'/api/models/'+repo+'?blobs=true'));meta['models'][repo]=model
        siblings={r['rfilename']:r for r in model['siblings']}
        for name in names:
            if name not in siblings:continue
            entry=siblings[name];url=endpoint+'/'+repo+'/resolve/'+model['sha']+'/'+name
            p=MODEL/'mirrors'/repo.replace('/','_')/name;p.parent.mkdir(parents=True,exist_ok=True)
            if not p.exists():
                with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=60) as response,p.with_suffix(p.suffix+'.partial').open('wb') as output:
                    while data:=response.read(1024**2):output.write(data);assert output.tell()<=256*1024**2
                p.with_suffix(p.suffix+'.partial').rename(p)
            if entry.get('lfs'):assert sha(p)==entry['lfs']['sha256'] and p.stat().st_size==entry['lfs']['size']
            print(json.dumps(dict(file=name,sha256=sha(p),bytes=p.stat().st_size)),flush=True)
    archive=MODEL/'mirrors/Bash2X_RIFE-Models/RIFE_v4.25.zip'
    with zipfile.ZipFile(archive) as z:
        assert len(z.infolist())<=100
        for info in z.infolist():
            p=Path(info.filename);assert not p.is_absolute() and '..' not in p.parts and ':' not in info.filename and info.file_size<=256*1024**2
            if info.is_dir():continue
            save(MODEL/'upstream/unpacked'/p,z.read(info))
        meta['archive_members']=z.namelist()
    meta.update(status='mirrors-acquired',archive_sha256=sha(archive),official_archive_byte_equality_verified=False)
    save(report,(json.dumps(meta,ensure_ascii=False,indent=2)+'\n').encode('utf8'));print(json.dumps(dict(status=meta['status'],members=meta['archive_members'])),flush=True)
if __name__=='__main__':main()
