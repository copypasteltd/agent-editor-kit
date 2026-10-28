"""Small integration metadata updates, preserving all existing declarations."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'product/pyproject.toml';s=p.read_text('utf8');needle='ai_ad_editor = ["RIFE_LICENSE.txt",'
if '"DEEPFILTER_LICENSE_MIT.txt"' not in s:
    assert needle in s;s=s.replace(needle,'ai_ad_editor = ["DEEPFILTER_LICENSE_MIT.txt", "DEEPFILTER_LICENSE_APACHE.txt", "RIFE_LICENSE.txt",',1);p.write_text(s,encoding='utf8',newline='\n')
p=ROOT/'product/src/ai_ad_editor/cli.py';s=p.read_text('utf8')
needle='{("interpolate", "adapter"), ("lipsync", "adapter"), ("audio", "adapter"), ("media", "adapter")}'
replacement='{("audio", "enhancement-adapter"), ("interpolate", "adapter"), ("lipsync", "adapter"), ("audio", "adapter"), ("media", "adapter")}'
assert s.count(needle)==2 or s.count(replacement)==2
s=s.replace(needle,replacement);p.write_text(s,encoding='utf8',newline='\n')
print('updated package licenses and read-only adapter execution classification')
