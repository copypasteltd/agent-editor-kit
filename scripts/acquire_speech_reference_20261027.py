"""Acquire official native CPU reference executable for independent DSP comparison."""
from pathlib import Path
import hashlib,json,urllib.request
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
DEST=ROOT/'product/.runtime/models/deepfilternet3-20261027/reference'
headers={'User-Agent':'agent-editor-kit-development'}
release=json.load(urllib.request.urlopen(urllib.request.Request('https://api.github.com/repos/Rikorose/DeepFilterNet/releases/tags/v0.5.6',headers=headers),timeout=25))
asset=next(a for a in release['assets'] if a['name']=='deep-filter-0.5.6-x86_64-pc-windows-msvc.exe')
DEST.mkdir(parents=True,exist_ok=True);target=DEST/asset['name']
if not target.exists():
    with urllib.request.urlopen(urllib.request.Request(asset['browser_download_url'],headers=headers),timeout=30) as response:data=response.read(32*1024**2)
    assert len(data)==asset['size'] and data[:2]==b'MZ';target.write_bytes(data)
record=dict(status='official-native-reference-acquired',release=release['html_url'],asset_id=asset['id'],url=asset['browser_download_url'],
    path=str(target),bytes=target.stat().st_size,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),executed=False)
(BASE/'reference-acquisition.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
print(json.dumps(record),flush=True)
