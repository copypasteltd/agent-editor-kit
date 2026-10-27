"""Vendor the reviewed MIT RIFE4.25 graph; never import model-directory code."""
from pathlib import Path
import ast,json
from acquire_interpolation_20261027 import ROOT,BASE,MODEL,save,sha
source=MODEL/'upstream/unpacked/train_log/IFNet_HDv3.py'
tree=ast.parse(source.read_text('utf8'));names={'conv','Head','ResConv','IFBlock','IFNet'}
nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
assert {n.name for n in nodes}==names
header='''"""Reviewed MIT Practical-RIFE4.25 inference graph; see RIFE_LICENSE.txt.

Graph classes adapted from the pinned archive. Training branches and remote
imports are removed; only the fixed graph below is instantiated by the worker.
"""
import torch
from torch import nn
import torch.nn.functional as F

_grid_key=None
_grid=None
def warp(image,flow):
    global _grid_key,_grid
    key=(str(flow.device),str(flow.dtype),flow.shape[0],flow.shape[2],flow.shape[3])
    if key!=_grid_key:
        h,w=flow.shape[2:]
        x=torch.linspace(-1.,1.,w,device=flow.device,dtype=flow.dtype).view(1,1,1,w).expand(flow.shape[0],-1,h,-1)
        y=torch.linspace(-1.,1.,h,device=flow.device,dtype=flow.dtype).view(1,1,h,1).expand(flow.shape[0],-1,-1,w)
        _grid=torch.cat((x,y),1);_grid_key=key
    normalized=torch.cat((flow[:,0:1]/((image.shape[3]-1.)/2),flow[:,1:2]/((image.shape[2]-1.)/2)),1)
    return F.grid_sample(image,(_grid+normalized).permute(0,2,3,1),mode='bilinear',padding_mode='border',align_corners=True)

'''
# Keep reviewed inference classes, removing only unreachable training/commented
# branches from the AST. The forward graph and strict parameter names stay fixed.
for node in nodes:
    if isinstance(node,ast.ClassDef) and node.name=='IFNet':
        for method in node.body:
            if not isinstance(method,ast.FunctionDef):continue
            method.body=[s for s in method.body if not isinstance(s,ast.Expr) or not isinstance(s.value,ast.Constant) or not isinstance(s.value.value,str)]
            if method.name=='forward':
                for item in ast.walk(method):
                    if isinstance(item,ast.If) and ast.unparse(item.test)=='not fastmode':item.body=[ast.Pass()]
graph=header+'\n\n'.join(ast.unparse(n) for n in nodes)+'\n'
ast.parse(graph)
target=ROOT/'product/src/ai_ad_editor/interpolation_graph.py';assert not target.exists();save(target,graph.encode('utf8'))
license_target=ROOT/'product/src/ai_ad_editor/RIFE_LICENSE.txt';assert not license_target.exists();save(license_target,(BASE/'upstream-code/LICENSE').read_bytes())
for name in ('IFNet_HDv3.py','RIFE_HDv3.py','refine.py'):
    save(BASE/'upstream-model-code'/name,(source.parent/name).read_bytes())
save(BASE/'vendoring.json',(json.dumps(dict(status='reviewed-graph-vendored',source_sha256=sha(source),output_sha256=sha(target),
    output=str(target.relative_to(ROOT)),source_license='MIT',remote_code_execution=False,training_and_unused_branches=False,
    bounded_grid_cache_entries=1,upstream_warp_grid_sample='bilinear/border/align_corners=True'),indent=2)+'\n').encode('utf8'))
print('vendored reviewed fixed RIFE4.25 inference graph')
