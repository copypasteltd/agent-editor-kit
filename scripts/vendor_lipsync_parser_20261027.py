"""Vendor the reviewed MIT BiSeNet graph without pickle or backbone loading."""
from pathlib import Path
import ast,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
meta=json.loads((BASE/'acquisition-metadata.json').read_bytes())
assert meta['github_commit']=='0a89dec45a0192b824e3cf4daf96c239440c5ed8'
upstream=BASE/'upstream-code/musetalk/utils/face_parsing'
parts=[];sources=[]
for name in ('resnet.py','model.py'):
    raw=(upstream/name).read_bytes();text=raw.decode('utf8');lines=text.splitlines(True)
    changes=[]
    for node in ast.parse(text).body:
        if isinstance(node,(ast.Import,ast.ImportFrom)):
            changes.append((node.lineno,node.end_lineno,''))
        if isinstance(node,ast.If) and ast.unparse(node.test).startswith("__name__ =="):
            changes.append((node.lineno,node.end_lineno,''))
        if isinstance(node,ast.ClassDef):
            for method in node.body:
                if isinstance(method,ast.FunctionDef) and (method.name=='get_params' or node.name=='Resnet18' and method.name=='init_weight'):
                    changes.append((method.lineno,method.end_lineno,''))
    for start,end,new in sorted(changes,reverse=True):lines[start-1:end]=[new]
    text=''.join(lines).replace('        self.init_weight(model_path)\n','')
    text=text.replace("resnet18_url = 'https://download.pytorch.org/models/resnet18-5c106cde.pth'",'')
    assert 'torch.load' not in text and 'modelzoo' not in text
    parts.append(text);sources.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest()})
header='''"""MIT BiSeNet/ResNet18 graph adapted from MuseTalk face parsing.

Copyright (c) 2019 zll; Copyright (c) 2024 Tencent Music Entertainment Group.
See LIPSYNC_LICENSES.txt. Only architecture is retained: no backbone/pickle,
download, training utilities or remote code. Complete safetensors state is
loaded strictly by lipsync_model.py in the isolated offline worker.
"""
import torch
from torch import nn
from torch.nn import functional as F
'''
out=ROOT/'product/src/ai_ad_editor/lipsync_parser.py';out.write_text(header+'\n'.join(parts),encoding='utf8',newline='\n')
license=(BASE/'upstream-code/LICENSE').read_text('utf8')
notice='MuseTalk and BiSeNet face parsing attribution\n\n'+license+'\n\nBiSeNet original: https://github.com/zllrunning/face-parsing.PyTorch\nCopyright (c) 2019 zll; MIT License.\nArchitecture adapted to prohibit pickle loading and use strict complete safetensors.\n'
(ROOT/'product/src/ai_ad_editor/LIPSYNC_LICENSES.txt').write_text(notice,encoding='utf8',newline='\n')
(BASE/'vendoring.json').write_text(json.dumps({'upstream_commit':meta['github_commit'],'source_files':sources,
    'product_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'modified':'merged architecture; no pickle/backbone loads or training helpers',
    'license':'MIT'},indent=2)+'\n',encoding='utf8',newline='\n')
print('Vendored reviewed offline BiSeNet architecture')
