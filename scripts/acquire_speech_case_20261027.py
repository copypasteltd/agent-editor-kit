"""Acquire the specific LibriSpeech utterance linked by Qwen's official demo."""
from pathlib import Path
import json,hashlib,urllib.request
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
folder=ROOT/'product/.runtime/models/deepfilternet3-20261027/reference';folder.mkdir(parents=True,exist_ok=True)
url='https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen2-Audio/audio/1272-128104-0000.flac'
p=folder/'1272-128104-0000.flac'
if not p.exists():
    with urllib.request.urlopen(url,timeout=30) as response:data=response.read(4*1024**2)
    assert data[:4]==b'fLaC';p.write_bytes(data)
license_url='https://www.openslr.org/12'
with urllib.request.urlopen(license_url,timeout=25) as response:page=response.read(1024**2)
assert b'CC BY 4.0' in page
(BASE/'librispeech-license-page.html').write_bytes(page)
record=dict(status='licensed-human-speech-acquired',source=url,source_listing='https://github.com/QwenLM/Qwen2-Audio',
    original='LibriSpeech dev-clean/1272/128104/1272-128104-0000',creator='LibriSpeech / LibriVox contributors; corpus prepared by Vassil Panayotov et al.',
    license_spdx='CC-BY-4.0',license_url=license_url,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),bytes=p.stat().st_size,path=str(p),
    transcript='MISTER QUILTER IS THE APOSTLE OF THE MIDDLE CLASSES AND WE ARE GLAD TO WELCOME HIS GOSPEL')
(BASE/'human-speech-acquisition.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8');print(json.dumps(record),flush=True)
