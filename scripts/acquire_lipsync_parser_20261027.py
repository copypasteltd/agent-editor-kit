"""Capture pinned upstream face parsing architecture and acquisition references."""
import base64,json
from acquire_lipsync_20261027 import BASE,MODEL,fetch,save

meta=json.loads((BASE/'acquisition-metadata.json').read_bytes());revision=meta['github_commit']
tree=json.loads(fetch('https://api.github.com/repos/TMElyralab/MuseTalk/git/trees/'+revision+'?recursive=1'))
save(BASE/'upstream-tree.json',(json.dumps(tree,indent=2)+'\n').encode())
names=[r['path'] for r in tree['tree'] if r['type']=='blob' and
       (r['path'].startswith('musetalk/utils/face_parsing/') and r['path'].endswith('.py') or r['path']=='download_weights.bat')]
for name in names:
    p=BASE/'upstream-code'/name
    if not p.exists():
        info=json.loads(fetch('https://api.github.com/repos/TMElyralab/MuseTalk/contents/'+name+'?ref='+revision))
        save(p,base64.b64decode(info['content']))
print(json.dumps({'captured':names}))
