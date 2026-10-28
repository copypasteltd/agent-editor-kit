"""Fixed DeepFilterNet3 inference, adapted from Rikorose/DeepFilterNet.

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

from .enhancement_layers import Conv2dNormAct, ConvTranspose2dNormAct, GroupedLinearEinsum, Mask, SqueezedGRU_S, DeepFilter
PI=math.pi

class ModelParams:
    sr = 48000
    fft_size = 960
    hop_size = 480
    nb_erb = 32
    nb_df = 96
    norm_tau = 1
    lsnr_max = 35
    lsnr_min = -15
    min_nb_erb_freqs = 2
    df_order = 5
    df_lookahead = 2
    conv_lookahead = 2
    conv_ch = 64
    conv_depthwise = True
    convt_depthwise = False
    conv_kernel = [1, 3]
    convt_kernel = [1, 3]
    conv_kernel_inp = [3, 3]
    emb_hidden_dim = 256
    emb_num_layers = 3
    emb_gru_skip_enc = 'none'
    emb_gru_skip = 'none'
    df_hidden_dim = 256
    df_gru_skip = 'groupedlinear'
    df_pathway_kernel_size_t = 5
    enc_concat = False
    df_num_layers = 2
    df_n_iter = 1
    lin_groups = 16
    enc_lin_groups = 32
    mask_pf = False
    pf_beta = 0.02
    lsnr_dropout = False

class Add(nn.Module):

    def forward(self, a, b):
        return a + b

class Concat(nn.Module):

    def forward(self, a, b):
        return torch.cat((a, b), dim=-1)

class Encoder(nn.Module):

    def __init__(self):
        super().__init__()
        p = ModelParams()
        assert p.nb_erb % 4 == 0, 'erb_bins should be divisible by 4'
        self.erb_conv0 = Conv2dNormAct(1, p.conv_ch, kernel_size=p.conv_kernel_inp, bias=False, separable=True)
        conv_layer = partial(Conv2dNormAct, in_ch=p.conv_ch, out_ch=p.conv_ch, kernel_size=p.conv_kernel, bias=False, separable=True)
        self.erb_conv1 = conv_layer(fstride=2)
        self.erb_conv2 = conv_layer(fstride=2)
        self.erb_conv3 = conv_layer(fstride=1)
        self.df_conv0 = Conv2dNormAct(2, p.conv_ch, kernel_size=p.conv_kernel_inp, bias=False, separable=True)
        self.df_conv1 = conv_layer(fstride=2)
        self.erb_bins = p.nb_erb
        self.emb_in_dim = p.conv_ch * p.nb_erb // 4
        self.emb_dim = p.emb_hidden_dim
        self.emb_out_dim = p.conv_ch * p.nb_erb // 4
        df_fc_emb = GroupedLinearEinsum(p.conv_ch * p.nb_df // 2, self.emb_in_dim, groups=p.enc_lin_groups)
        self.df_fc_emb = nn.Sequential(df_fc_emb, nn.ReLU(inplace=True))
        if p.enc_concat:
            self.emb_in_dim *= 2
            self.combine = Concat()
        else:
            self.combine = Add()
        self.emb_n_layers = p.emb_num_layers
        if p.emb_gru_skip_enc == 'none':
            skip_op = None
        elif p.emb_gru_skip_enc == 'identity':
            assert self.emb_in_dim == self.emb_out_dim, 'Dimensions do not match'
            skip_op = partial(nn.Identity)
        elif p.emb_gru_skip_enc == 'groupedlinear':
            skip_op = partial(GroupedLinearEinsum, input_size=self.emb_out_dim, hidden_size=self.emb_out_dim, groups=p.lin_groups)
        else:
            raise NotImplementedError()
        self.emb_gru = SqueezedGRU_S(self.emb_in_dim, self.emb_dim, output_size=self.emb_out_dim, num_layers=1, batch_first=True, gru_skip_op=skip_op, linear_groups=p.lin_groups, linear_act_layer=partial(nn.ReLU, inplace=True))
        self.lsnr_fc = nn.Sequential(nn.Linear(self.emb_out_dim, 1), nn.Sigmoid())
        self.lsnr_scale = p.lsnr_max - p.lsnr_min
        self.lsnr_offset = p.lsnr_min

    def forward(self, feat_erb: Tensor, feat_spec: Tensor) -> Tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        e0 = self.erb_conv0(feat_erb)
        e1 = self.erb_conv1(e0)
        e2 = self.erb_conv2(e1)
        e3 = self.erb_conv3(e2)
        c0 = self.df_conv0(feat_spec)
        c1 = self.df_conv1(c0)
        cemb = c1.permute(0, 2, 3, 1).flatten(2)
        cemb = self.df_fc_emb(cemb)
        emb = e3.permute(0, 2, 3, 1).flatten(2)
        emb = self.combine(emb, cemb)
        emb, _ = self.emb_gru(emb)
        lsnr = self.lsnr_fc(emb) * self.lsnr_scale + self.lsnr_offset
        return (e0, e1, e2, e3, emb, c0, lsnr)

class ErbDecoder(nn.Module):

    def __init__(self):
        super().__init__()
        p = ModelParams()
        assert p.nb_erb % 8 == 0, 'erb_bins should be divisible by 8'
        self.emb_in_dim = p.conv_ch * p.nb_erb // 4
        self.emb_dim = p.emb_hidden_dim
        self.emb_out_dim = p.conv_ch * p.nb_erb // 4
        if p.emb_gru_skip == 'none':
            skip_op = None
        elif p.emb_gru_skip == 'identity':
            assert self.emb_in_dim == self.emb_out_dim, 'Dimensions do not match'
            skip_op = partial(nn.Identity)
        elif p.emb_gru_skip == 'groupedlinear':
            skip_op = partial(GroupedLinearEinsum, input_size=self.emb_in_dim, hidden_size=self.emb_out_dim, groups=p.lin_groups)
        else:
            raise NotImplementedError()
        self.emb_gru = SqueezedGRU_S(self.emb_in_dim, self.emb_dim, output_size=self.emb_out_dim, num_layers=p.emb_num_layers - 1, batch_first=True, gru_skip_op=skip_op, linear_groups=p.lin_groups, linear_act_layer=partial(nn.ReLU, inplace=True))
        tconv_layer = partial(ConvTranspose2dNormAct, kernel_size=p.convt_kernel, bias=False, separable=True)
        conv_layer = partial(Conv2dNormAct, bias=False, separable=True)
        self.conv3p = conv_layer(p.conv_ch, p.conv_ch, kernel_size=1)
        self.convt3 = conv_layer(p.conv_ch, p.conv_ch, kernel_size=p.conv_kernel)
        self.conv2p = conv_layer(p.conv_ch, p.conv_ch, kernel_size=1)
        self.convt2 = tconv_layer(p.conv_ch, p.conv_ch, fstride=2)
        self.conv1p = conv_layer(p.conv_ch, p.conv_ch, kernel_size=1)
        self.convt1 = tconv_layer(p.conv_ch, p.conv_ch, fstride=2)
        self.conv0p = conv_layer(p.conv_ch, p.conv_ch, kernel_size=1)
        self.conv0_out = conv_layer(p.conv_ch, 1, kernel_size=p.conv_kernel, activation_layer=nn.Sigmoid)

    def forward(self, emb: Tensor, e3: Tensor, e2: Tensor, e1: Tensor, e0: Tensor) -> Tensor:
        b, _, t, f8 = e3.shape
        emb, _ = self.emb_gru(emb)
        emb = emb.view(b, t, f8, -1).permute(0, 3, 1, 2)
        e3 = self.convt3(self.conv3p(e3) + emb)
        e2 = self.convt2(self.conv2p(e2) + e3)
        e1 = self.convt1(self.conv1p(e1) + e2)
        m = self.conv0_out(self.conv0p(e0) + e1)
        return m

class DfOutputReshapeMF(nn.Module):
    """Coefficients output reshape for multiframe/MultiFrameModule

    Requires input of shape B, C, T, F, 2.
    """

    def __init__(self, df_order: int, df_bins: int):
        super().__init__()
        self.df_order = df_order
        self.df_bins = df_bins

    def forward(self, coefs: Tensor) -> Tensor:
        new_shape = list(coefs.shape)
        new_shape[-1] = -1
        new_shape.append(2)
        coefs = coefs.view(new_shape)
        coefs = coefs.permute(0, 3, 1, 2, 4)
        return coefs

class DfDecoder(nn.Module):

    def __init__(self):
        super().__init__()
        p = ModelParams()
        layer_width = p.conv_ch
        self.emb_in_dim = p.conv_ch * p.nb_erb // 4
        self.emb_dim = p.df_hidden_dim
        self.df_n_hidden = p.df_hidden_dim
        self.df_n_layers = p.df_num_layers
        self.df_order = p.df_order
        self.df_bins = p.nb_df
        self.df_out_ch = p.df_order * 2
        conv_layer = partial(Conv2dNormAct, separable=True, bias=False)
        kt = p.df_pathway_kernel_size_t
        self.df_convp = conv_layer(layer_width, self.df_out_ch, fstride=1, kernel_size=(kt, 1))
        self.df_gru = SqueezedGRU_S(self.emb_in_dim, self.emb_dim, num_layers=self.df_n_layers, batch_first=True, gru_skip_op=None, linear_act_layer=partial(nn.ReLU, inplace=True))
        p.df_gru_skip = p.df_gru_skip.lower()
        assert p.df_gru_skip in ('none', 'identity', 'groupedlinear')
        self.df_skip: Optional[nn.Module]
        if p.df_gru_skip == 'none':
            self.df_skip = None
        elif p.df_gru_skip == 'identity':
            assert p.emb_hidden_dim == p.df_hidden_dim, 'Dimensions do not match'
            self.df_skip = nn.Identity()
        elif p.df_gru_skip == 'groupedlinear':
            self.df_skip = GroupedLinearEinsum(self.emb_in_dim, self.emb_dim, groups=p.lin_groups)
        else:
            raise NotImplementedError()
        self.df_out: nn.Module
        out_dim = self.df_bins * self.df_out_ch
        df_out = GroupedLinearEinsum(self.df_n_hidden, out_dim, groups=p.lin_groups)
        self.df_out = nn.Sequential(df_out, nn.Tanh())
        self.df_fc_a = nn.Sequential(nn.Linear(self.df_n_hidden, 1), nn.Sigmoid())

    def forward(self, emb: Tensor, c0: Tensor) -> Tensor:
        b, t, _ = emb.shape
        c, _ = self.df_gru(emb)
        if self.df_skip is not None:
            c = c + self.df_skip(emb)
        c0 = self.df_convp(c0).permute(0, 2, 3, 1)
        c = self.df_out(c)
        c = c.view(b, t, self.df_bins, self.df_out_ch) + c0
        return c

class DfNet(nn.Module):
    run_df: Final[bool]
    run_erb: Final[bool]
    lsnr_droput: Final[bool]
    post_filter: Final[bool]
    post_filter_beta: Final[float]

    def __init__(self, erb_fb: Tensor, erb_inv_fb: Tensor, run_df: bool=True, train_mask: bool=True):
        super().__init__()
        p = ModelParams()
        layer_width = p.conv_ch
        assert p.nb_erb % 8 == 0, 'erb_bins should be divisible by 8'
        self.df_lookahead = p.df_lookahead
        self.nb_df = p.nb_df
        self.freq_bins: int = p.fft_size // 2 + 1
        self.emb_dim: int = layer_width * p.nb_erb
        self.erb_bins: int = p.nb_erb
        if p.conv_lookahead > 0:
            assert p.conv_lookahead >= p.df_lookahead
            self.pad_feat = nn.ConstantPad2d((0, 0, -p.conv_lookahead, p.conv_lookahead), 0.0)
        else:
            self.pad_feat = nn.Identity()
        if p.df_lookahead > 0:
            self.pad_spec = nn.ConstantPad3d((0, 0, 0, 0, -p.df_lookahead, p.df_lookahead), 0.0)
        else:
            self.pad_spec = nn.Identity()
        self.register_buffer('erb_fb', erb_fb)
        self.enc = Encoder()
        self.erb_dec = ErbDecoder()
        self.mask = Mask(erb_inv_fb)
        self.erb_inv_fb = erb_inv_fb
        self.post_filter = p.mask_pf
        self.post_filter_beta = p.pf_beta
        self.df_order = p.df_order
        self.df_op = DeepFilter(num_freqs=p.nb_df, frame_size=p.df_order, lookahead=self.df_lookahead)
        self.df_dec = DfDecoder()
        self.df_out_transform = DfOutputReshapeMF(self.df_order, p.nb_df)
        self.run_erb = p.nb_df + 1 < self.freq_bins
        if not self.run_erb:
            pass
        self.run_df = run_df
        if not run_df:
            pass
        self.train_mask = train_mask
        self.lsnr_droput = p.lsnr_dropout
        assert p.df_n_iter == 1

    def forward(self, spec: Tensor, feat_erb: Tensor, feat_spec: Tensor) -> Tuple[Tensor, Tensor, Tensor, Tensor]:
        """Forward method of DeepFilterNet2.

        Args:
            spec (Tensor): Spectrum of shape [B, 1, T, F, 2]
            feat_erb (Tensor): ERB features of shape [B, 1, T, E]
            feat_spec (Tensor): Complex spectrogram features of shape [B, 1, T, F', 2]

        Returns:
            spec (Tensor): Enhanced spectrum of shape [B, 1, T, F, 2]
            m (Tensor): ERB mask estimate of shape [B, 1, T, E]
            lsnr (Tensor): Local SNR estimate of shape [B, T, 1]
        """
        feat_spec = feat_spec.squeeze(1).permute(0, 3, 1, 2)
        feat_erb = self.pad_feat(feat_erb)
        feat_spec = self.pad_feat(feat_spec)
        e0, e1, e2, e3, emb, c0, lsnr = self.enc(feat_erb, feat_spec)
        if self.lsnr_droput:
            idcs = lsnr.squeeze() > -10.0
            b, t = (spec.shape[0], spec.shape[2])
            m = torch.zeros((b, 1, t, self.erb_bins), device=spec.device)
            df_coefs = torch.zeros((b, t, self.nb_df, self.df_order * 2))
            spec_m = spec.clone()
            emb = emb[:, idcs]
            e0 = e0[:, :, idcs]
            e1 = e1[:, :, idcs]
            e2 = e2[:, :, idcs]
            e3 = e3[:, :, idcs]
            c0 = c0[:, :, idcs]
        if self.run_erb:
            if self.lsnr_droput:
                m[:, :, idcs] = self.erb_dec(emb, e3, e2, e1, e0)
            else:
                m = self.erb_dec(emb, e3, e2, e1, e0)
            spec_m = self.mask(spec, m)
        else:
            m = torch.zeros((), device=spec.device)
            spec_m = torch.zeros_like(spec)
        if self.run_df:
            if self.lsnr_droput:
                df_coefs[:, idcs] = self.df_dec(emb, c0)
            else:
                df_coefs = self.df_dec(emb, c0)
            df_coefs = self.df_out_transform(df_coefs)
            spec_e = self.df_op(spec.clone(), df_coefs)
            spec_e[..., self.nb_df:, :] = spec_m[..., self.nb_df:, :]
        else:
            df_coefs = torch.zeros((), device=spec.device)
            spec_e = spec_m
        if self.post_filter:
            beta = self.post_filter_beta
            eps = 1e-12
            mask = (torch.view_as_complex(spec_e.contiguous()).abs() / torch.view_as_complex(spec.contiguous()).abs().add(eps)).clamp(eps, 1)
            mask_sin = mask * torch.sin(PI * mask / 2).clamp_min(eps)
            pf = (1 + beta) / (1 + beta * mask.div(mask_sin).pow(2))
            spec_e = spec_e * pf.unsqueeze(-1)
        return (spec_e, m, lsnr, df_coefs)
