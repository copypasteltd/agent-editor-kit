"""Development-only pinned SigLIP 2 acquisition; inference stays fully offline."""
from pathlib import Path
import json
import os
import time
import urllib.parse
import urllib.request

from acquire_qwen_aligner_20261025 import digest, save

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'google/siglip2-base-patch16-224'
REVISION = 'e8632ce825c01c31e138f83852c01b643941c2fe'
TARGET = ROOT/'product/.runtime/models/siglip2-base-patch16-224-20261025'
EVIDENCE = ROOT/'docs/validation/evidence/semantic-20261025-r1/acquisition'


def main():
    metadata_path = ROOT/'sources/semantic-20261025/google--siglip2-base-patch16-224.json'
    metadata = json.loads(metadata_path.read_bytes())
    rows = [row for row in metadata['Data']['Files'] if row['Type'] == 'blob']
    assert rows and all(Path(row['Path']).name == row['Path'] for row in rows)
    TARGET.mkdir(parents=True,exist_ok=True)
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    state = {'repository':REPOSITORY,'revision':REVISION,'metadata_sha256':digest(metadata_path),
             'source':'Google organization on ModelScope','development_network':True,
             'runtime_downloads':False,'weights_executed':False,'files':[]}
    for row in sorted(rows,key=lambda r:(r['Path']=='model.safetensors',r['Path'])):
        name = row['Path']; path = TARGET/name; part = TARGET/(name+'.part')
        # The hub can return an LFS pointer when a later non-LFS commit is used
        # for inherited LFS files. Fetch their fixed last-change commit and
        # retain the snapshot's independently pinned size/SHA-256 gate.
        url = 'https://modelscope.cn/api/v1/models/'+REPOSITORY+'/repo?'+urllib.parse.urlencode({'Revision':row['Revision'],'FilePath':name})
        entry = {'file':name,'expected_bytes':row['Size'],'sha256':row['Sha256'],'source_url':url,
                 'last_changed_revision':row['Revision'],'attempts':[]}
        if not path.exists():
            for attempt in range(4):
                offset = part.stat().st_size if part.exists() else 0
                assert offset <= row['Size']
                if offset == row['Size']:break
                step = {'offset':offset}; entry['attempts'].append(step)
                try:
                    headers = {'User-Agent':'agent-editor-kit-development-model-acquisition'}
                    if offset:headers['Range']=f'bytes={offset}-'
                    started = time.monotonic()
                    with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=30) as response:
                        if offset and (response.status != 206 or not response.headers.get('Content-Range','').startswith(f'bytes {offset}-')):
                            raise ValueError('Resume not honored; preserve partial')
                        with part.open('ab' if offset else 'xb') as stream:
                            reported=offset
                            while block:=response.read(4*1024**2):
                                if offset+len(block)>row['Size']:raise ValueError('Response exceeds pinned file size')
                                stream.write(block);offset+=len(block)
                                if offset-reported>=32*1024**2:
                                    save(EVIDENCE/'progress.json',{'file':name,'received':offset,'expected':row['Size'],
                                         'elapsed_seconds':round(time.monotonic()-started,3)})
                                    reported=offset
                            stream.flush();os.fsync(stream.fileno())
                    if offset!=row['Size']:raise ValueError('Incomplete pinned response')
                    break
                except Exception as exc:
                    step['error']=repr(exc);save(EVIDENCE/'current.json',entry)
                    if attempt==3:raise
            if part.stat().st_size!=row['Size'] or digest(part)!=row['Sha256']:raise ValueError('SHA-256 mismatch')
            part.rename(path)
        if path.stat().st_size!=row['Size'] or digest(path)!=row['Sha256']:raise ValueError('Existing file differs from fixed snapshot')
        entry['status']='verified';state['files'].append(entry);save(EVIDENCE/'inventory.json',state)
        print(json.dumps({'file':name,'bytes':row['Size'],'status':'verified'}),flush=True)
    state.update(status='downloaded_verified',generator_sha256=digest(Path(__file__)))
    save(EVIDENCE/'inventory.json',state)


if __name__=='__main__':
    main()
