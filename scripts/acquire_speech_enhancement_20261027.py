"""Acquire fixed official DeepFilterNet3 source/weights; no package installation."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import base64
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
MODEL = ROOT/'product/.runtime/models/deepfilternet3-20261027'
COMMIT = 'd375b2d8309e0935d165700c91da9de862a99c31'
REPO = 'https://github.com/Rikorose/DeepFilterNet'
FILES = ('LICENSE', 'LICENSE-MIT', 'LICENSE-APACHE', 'README.md',
    'DeepFilterNet/df/deepfilternet3.py', 'DeepFilterNet/df/modules.py',
    'DeepFilterNet/df/multiframe.py', 'DeepFilterNet/df/enhance.py',
    'DeepFilterNet/df/config.py', 'DeepFilterNet/df/checkpoint.py',
    'DeepFilterNet/df/model.py', 'DeepFilterNet/df/utils.py',
    'DeepFilterNet/df/scripts/export.py', 'libDF/src/lib.rs',
    'libDF/src/transforms.rs', 'libDF/src/tract.rs', 'libDF/src/bin/enhance_wav.rs', 'pyDF/src/lib.rs')

def fetch(name, target):
    url = f'https://raw.githubusercontent.com/Rikorose/DeepFilterNet/{COMMIT}/{name}'
    transport=url
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        # The local network intermittently resets raw.githubusercontent.com TLS.
        # GitHub's official fixed-commit API exposes identical Git blob bytes.
        transport=f'https://api.github.com/repos/Rikorose/DeepFilterNet/contents/{name}?ref={COMMIT}'
        headers={'User-Agent':'agent-editor-kit-development','Accept':'application/vnd.github+json'}
        with urllib.request.urlopen(urllib.request.Request(transport, headers=headers), timeout=30) as response:
            metadata=json.load(response)
        if metadata.get('encoding')!='base64':
            transport=f'https://api.github.com/repos/Rikorose/DeepFilterNet/git/blobs/{metadata["sha"]}'
            with urllib.request.urlopen(urllib.request.Request(transport, headers=headers), timeout=30) as response:
                metadata=json.load(response)
        assert metadata['encoding']=='base64'
        data=base64.b64decode(metadata['content'])
        if len(data)>64*1024**2: raise ValueError('download budget exceeded')
        target.write_bytes(data)
    return dict(source=url, transport=transport, path=target.relative_to(ROOT).as_posix(), bytes=target.stat().st_size,
                sha256=hashlib.sha256(target.read_bytes()).hexdigest())

def main():
    BASE.mkdir(parents=True, exist_ok=True)
    records=[]
    for name in FILES:
        records.append(fetch(name, BASE/'upstream-code'/name))
        print(json.dumps(dict(acquired=name, bytes=records[-1]['bytes'])), flush=True)
    archive=MODEL/'upstream/DeepFilterNet3.zip'
    records.append(fetch('models/DeepFilterNet3.zip', archive))
    members=[]
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            p=Path(info.filename)
            if p.is_absolute() or '..' in p.parts or ':' in info.filename or info.file_size>64*1024**2:
                raise ValueError('unsafe model member')
            members.append(dict(path=info.filename, bytes=info.file_size))
            if info.is_dir(): continue
            target=MODEL/'upstream/unpacked'/p
            data=z.read(info)
            if target.exists(): assert target.read_bytes()==data
            else:
                target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    record=dict(status='official-source-and-model-acquired', at_utc=datetime.now(timezone.utc).isoformat(),
                repository=REPO, commit=COMMIT, records=records, model_members=members)
    (BASE/'acquisition.json').write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(status=record['status'], model_members=members)), flush=True)

if __name__=='__main__': main()
