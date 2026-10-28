"""Vendor only reviewed fixed inference classes from official dual-licensed DF3."""
from pathlib import Path
import ast
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
UP=BASE/'upstream-code/DeepFilterNet/df'
TARGET=ROOT/'product/src/ai_ad_editor'

def selected(name, names):
    tree=ast.parse((UP/name).read_bytes()); nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    assert {n.name for n in nodes}==set(names)
    return '\n\n'.join(ast.unparse(n) for n in nodes)+'\n'

def main():
    header='''"""Fixed DeepFilterNet3 inference, adapted from Rikorose/DeepFilterNet.

Copyright (c) 2021 Hendrik Schroeter. MIT OR Apache-2.0.
See DEEPFILTER_LICENSE_MIT.txt / DEEPFILTER_LICENSE_APACHE.txt.
No model-directory Python, configurable plugins or downloaded runtime code.
"""
from functools import partial
from typing import Callable, Iterable, List, Optional, Tuple, Union, Final
import math
import torch
from torch import Tensor, nn
from torch.nn import init
from torch.nn.parameter import Parameter

'''
    layers=header+selected('modules.py', ['Conv2dNormAct','ConvTranspose2dNormAct','SqueezedGRU_S','GroupedLinearEinsum'])
    layers+='''
class Mask(nn.Module):
    def __init__(self, erb_inv_fb):
        super().__init__()
        self.register_buffer('erb_inv_fb', erb_inv_fb)
    def forward(self, spec, mask):
        return spec * mask.matmul(self.erb_inv_fb).unsqueeze(-1)

class DeepFilter(nn.Module):
    def __init__(self, num_freqs, frame_size, lookahead):
        super().__init__()
        self.num_freqs, self.frame_size = num_freqs, frame_size
        self.pad = nn.ConstantPad2d((0, 0, frame_size-1-lookahead, lookahead), 0.)
    def forward(self, spec, coefs):
        spectrum = self.pad(torch.view_as_complex(spec)).unfold(2, self.frame_size, 1)
        coefficients = torch.view_as_complex(coefs).view(coefs.shape[0], -1, self.frame_size, coefs.shape[2], coefs.shape[3])
        filtered = torch.einsum('...tfn,...ntf->...tf', spectrum[..., :self.num_freqs, :], coefficients)
        result = spec.clone()
        result[..., :self.num_freqs, :] = torch.view_as_real(filtered)
        return result
'''
    params=dict(sr=48000, fft_size=960, hop_size=480, nb_erb=32, nb_df=96, norm_tau=1,
        lsnr_max=35,lsnr_min=-15,min_nb_erb_freqs=2,df_order=5,df_lookahead=2,
        conv_lookahead=2,conv_ch=64,conv_depthwise=True,convt_depthwise=False,
        conv_kernel=[1,3],convt_kernel=[1,3],conv_kernel_inp=[3,3],emb_hidden_dim=256,
        emb_num_layers=3,emb_gru_skip_enc='none',emb_gru_skip='none',df_hidden_dim=256,
        df_gru_skip='groupedlinear',df_pathway_kernel_size_t=5,enc_concat=False,df_num_layers=2,
        df_n_iter=1,lin_groups=16,enc_lin_groups=32,mask_pf=False,pf_beta=.02,lsnr_dropout=False)
    graph=header+'from .enhancement_layers import Conv2dNormAct, ConvTranspose2dNormAct, GroupedLinearEinsum, Mask, SqueezedGRU_S, DeepFilter\nPI=math.pi\n\n'
    graph+='class ModelParams:\n'+''.join('    '+k+' = '+repr(v)+'\n' for k,v in params.items())+'\n'
    graph+=selected('deepfilternet3.py', ['Add','Concat','Encoder','ErbDecoder','DfOutputReshapeMF','DfDecoder','DfNet'])
    graph=graph.replace('MF.DF(', 'DeepFilter(').replace('as_complex(spec_e)','torch.view_as_complex(spec_e.contiguous())').replace('as_complex(spec)','torch.view_as_complex(spec.contiguous())')
    # Fixed model settings make warning/training-only branches unreachable.
    graph=graph.replace("logger.warning('Running without ERB stage')",'pass').replace("logger.warning('Running without DF stage')",'pass')
    for name,data in [('enhancement_layers.py',layers),('enhancement_graph.py',graph)]:
        ast.parse(data); (TARGET/name).write_text(data,encoding='utf-8',newline='\n')
    for source,dest in [('LICENSE-MIT','DEEPFILTER_LICENSE_MIT.txt'),('LICENSE-APACHE','DEEPFILTER_LICENSE_APACHE.txt')]:
        (TARGET/dest).write_bytes((BASE/'upstream-code'/source).read_bytes())
    report=dict(status='fixed-inference-graph-vendored',repository='https://github.com/Rikorose/DeepFilterNet',
        commit='d375b2d8309e0935d165700c91da9de862a99c31',license='MIT OR Apache-2.0',
        fixed_parameters=params,training=False,model_directory_code=False,
        files={n:hashlib.sha256((TARGET/n).read_bytes()).hexdigest() for n in ['enhancement_layers.py','enhancement_graph.py']})
    (BASE/'vendoring.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=report['status'],files=report['files'])),flush=True)
if __name__=='__main__': main()
