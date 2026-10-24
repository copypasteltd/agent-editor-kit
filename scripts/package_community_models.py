"""Archive the exact four optional packs pinned by the current CLI catalog."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as h:return hashlib.file_digest(h,'sha256').hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output.resolve()
    if not out.is_relative_to(ROOT) or out.exists():raise ValueError('Select a new owned output')
    out.mkdir(parents=True);rows=[]
    catalog=json.loads((ROOT/'product/src/ai_ad_editor/material_data/model-packs.json').read_bytes())
    for row in catalog['packs']:
        pack=ROOT/row['local_pack_path_hint'];assert sha(pack/'manifest.json')==row['manifest_sha256']
        manifest=json.loads((pack/'manifest.json').read_bytes())
        target=out/(row['id']+'.zip')
        with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in sorted([*(r['path'] for r in manifest['files']),'manifest.json']):
                path=pack/name
                if name!='manifest.json':
                    record=next(r for r in manifest['files'] if r['path']==name)
                    assert path.stat().st_size==record['bytes'] and sha(path)==record['sha256']
                info=zipfile.ZipInfo(name,date_time=(2026,10,24,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
                with path.open('rb') as source,z.open(info,'w',force_zip64=True) as dest:
                    while data:=source.read(1024*1024):dest.write(data)
        result=dict(id=row['id'],archive=str(target),bytes=target.stat().st_size,sha256=sha(target),
                    manifest_sha256=row['manifest_sha256'],files=row['files'],local_only=True)
        rows.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
    (out/'archives.json').write_text(json.dumps(dict(format='agent-community-model-archives-v1',packs=rows),ensure_ascii=False,indent=2)+'\n',encoding='utf8')


if __name__=='__main__':main()
