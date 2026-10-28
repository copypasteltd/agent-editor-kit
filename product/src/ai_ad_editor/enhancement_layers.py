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

class Conv2dNormAct(nn.Sequential):

    def __init__(self, in_ch: int, out_ch: int, kernel_size: Union[int, Iterable[int]], fstride: int=1, dilation: int=1, fpad: bool=True, bias: bool=True, separable: bool=False, norm_layer: Optional[Callable[..., torch.nn.Module]]=torch.nn.BatchNorm2d, activation_layer: Optional[Callable[..., torch.nn.Module]]=torch.nn.ReLU):
        """Causal Conv2d by delaying the signal for any lookahead.

        Expected input format: [B, C, T, F]
        """
        lookahead = 0
        kernel_size = (kernel_size, kernel_size) if isinstance(kernel_size, int) else tuple(kernel_size)
        if fpad:
            fpad_ = kernel_size[1] // 2 + dilation - 1
        else:
            fpad_ = 0
        pad = (0, 0, kernel_size[0] - 1 - lookahead, lookahead)
        layers = []
        if any((x > 0 for x in pad)):
            layers.append(nn.ConstantPad2d(pad, 0.0))
        groups = math.gcd(in_ch, out_ch) if separable else 1
        if groups == 1:
            separable = False
        if max(kernel_size) == 1:
            separable = False
        layers.append(nn.Conv2d(in_ch, out_ch, kernel_size=kernel_size, padding=(0, fpad_), stride=(1, fstride), dilation=(1, dilation), groups=groups, bias=bias))
        if separable:
            layers.append(nn.Conv2d(out_ch, out_ch, kernel_size=1, bias=False))
        if norm_layer is not None:
            layers.append(norm_layer(out_ch))
        if activation_layer is not None:
            layers.append(activation_layer())
        super().__init__(*layers)

class ConvTranspose2dNormAct(nn.Sequential):

    def __init__(self, in_ch: int, out_ch: int, kernel_size: Union[int, Tuple[int, int]], fstride: int=1, dilation: int=1, fpad: bool=True, bias: bool=True, separable: bool=False, norm_layer: Optional[Callable[..., torch.nn.Module]]=torch.nn.BatchNorm2d, activation_layer: Optional[Callable[..., torch.nn.Module]]=torch.nn.ReLU):
        """Causal ConvTranspose2d.

        Expected input format: [B, C, T, F]
        """
        lookahead = 0
        kernel_size = (kernel_size, kernel_size) if isinstance(kernel_size, int) else kernel_size
        if fpad:
            fpad_ = kernel_size[1] // 2
        else:
            fpad_ = 0
        pad = (0, 0, kernel_size[0] - 1 - lookahead, lookahead)
        layers = []
        if any((x > 0 for x in pad)):
            layers.append(nn.ConstantPad2d(pad, 0.0))
        groups = math.gcd(in_ch, out_ch) if separable else 1
        if groups == 1:
            separable = False
        layers.append(nn.ConvTranspose2d(in_ch, out_ch, kernel_size=kernel_size, padding=(kernel_size[0] - 1, fpad_ + dilation - 1), output_padding=(0, fpad_), stride=(1, fstride), dilation=(1, dilation), groups=groups, bias=bias))
        if separable:
            layers.append(nn.Conv2d(out_ch, out_ch, kernel_size=1, bias=False))
        if norm_layer is not None:
            layers.append(norm_layer(out_ch))
        if activation_layer is not None:
            layers.append(activation_layer())
        super().__init__(*layers)

class SqueezedGRU_S(nn.Module):
    input_size: Final[int]
    hidden_size: Final[int]

    def __init__(self, input_size: int, hidden_size: int, output_size: Optional[int]=None, num_layers: int=1, linear_groups: int=8, batch_first: bool=True, gru_skip_op: Optional[Callable[..., torch.nn.Module]]=None, linear_act_layer: Callable[..., torch.nn.Module]=nn.Identity):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.linear_in = nn.Sequential(GroupedLinearEinsum(input_size, hidden_size, linear_groups), linear_act_layer())
        self.gru = nn.GRU(hidden_size, hidden_size, num_layers=num_layers, batch_first=batch_first)
        self.gru_skip = gru_skip_op() if gru_skip_op is not None else None
        if output_size is not None:
            self.linear_out = nn.Sequential(GroupedLinearEinsum(hidden_size, output_size, linear_groups), linear_act_layer())
        else:
            self.linear_out = nn.Identity()

    def forward(self, input: Tensor, h: Optional[Tensor]=None) -> Tuple[Tensor, Tensor]:
        x = self.linear_in(input)
        x, h = self.gru(x, h)
        x = self.linear_out(x)
        if self.gru_skip is not None:
            x = x + self.gru_skip(input)
        return (x, h)

class GroupedLinearEinsum(nn.Module):
    input_size: Final[int]
    hidden_size: Final[int]
    groups: Final[int]

    def __init__(self, input_size: int, hidden_size: int, groups: int=1):
        super().__init__()
        self.input_size = input_size
        self.hidden_size = hidden_size
        self.groups = groups
        assert input_size % groups == 0, f'Input size {input_size} not divisible by {groups}'
        assert hidden_size % groups == 0, f'Hidden size {hidden_size} not divisible by {groups}'
        self.ws = input_size // groups
        self.register_parameter('weight', Parameter(torch.zeros(groups, input_size // groups, hidden_size // groups), requires_grad=True))
        self.reset_parameters()

    def reset_parameters(self):
        init.kaiming_uniform_(self.weight, a=math.sqrt(5))

    def forward(self, x: Tensor) -> Tensor:
        b, t, _ = x.shape
        new_shape = (b, t, self.groups, self.ws)
        x = x.view(new_shape)
        x = torch.einsum('btgi,gih->btgh', x, self.weight)
        x = x.flatten(2, 3)
        return x

    def __repr__(self):
        cls = self.__class__.__name__
        return f'{cls}(input_size: {self.input_size}, hidden_size: {self.hidden_size}, groups: {self.groups})'

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
