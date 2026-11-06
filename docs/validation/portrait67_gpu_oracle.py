"""Independent scalar expectations for actual installed CUDA portrait operators."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import time


def run(installed, output):
    sys.path.insert(0, str(installed/'site'))
    import numpy as np
    import torch
    import ai_ad_editor
    from ai_ad_editor.portrait_pixels import apply_regions
    assert Path(ai_ad_editor.__file__).resolve() == (installed/'site/ai_ad_editor/__init__.py').resolve()
    assert torch.cuda.is_available(), 'Actual CUDA is required; no skip or fallback'
    torch.cuda.reset_peak_memory_stats(); began = time.monotonic()
    h, w = 2160, 3840
    source = np.full((h, w, 4), 128, np.uint8); source[..., 3] = 255; source[:, :8, 3] = 0; source[:, 8:16, 3] = 127
    labels = np.ones((h, w), np.uint8); labels[:, w//2:] = 17
    protect = np.zeros((h, w), np.uint8); protect[:, 80:100] = 1
    with torch.inference_mode():
        result, selected = apply_regions(torch.from_numpy(source).to('cuda'), torch.from_numpy(labels).to('cuda'), torch.from_numpy(protect).to('cuda'),
            dict(feather_pixels=0, regions=dict(skin=dict(exposure_ev=1))), 'srgb')
        actual, support = result.cpu().numpy(), selected.cpu().numpy()
    # Independently calculated in Python float64; no product transfer helper.
    encoded = 128/255; linear = encoded/12.92 if encoded <= .04045 else ((encoded+.055)/1.055)**2.4
    raised = min(1, linear*2); expected_value = round((raised*12.92 if raised <= .0031308 else 1.055*raised**(1/2.4)-.055)*255)
    expected_support = (labels == 1) & (protect == 0) & (source[..., 3] != 0)
    expected = source.copy(); expected[expected_support, :3] = expected_value
    np.testing.assert_array_equal(support, expected_support); np.testing.assert_array_equal(actual, expected)
    # Check a deliberately protected bright neighbour cannot bleed into smoothing.
    small = np.full((5, 5, 4), 64, np.uint8); small[..., 3] = 255; small[2, 2, :3] = 255
    mask = np.zeros((5, 5), np.uint8); mask[2, 2] = 1
    with torch.inference_mode():
        smooth, _ = apply_regions(torch.from_numpy(small).to('cuda'), torch.ones((5, 5), dtype=torch.uint8, device='cuda'),
            torch.from_numpy(mask).to('cuda'), dict(feather_pixels=0, regions=dict(skin=dict(smooth=1))), 'srgb')
        np.testing.assert_array_equal(smooth.cpu().numpy(), small)
    torch.cuda.synchronize()
    record = dict(status='passed', cli_version=ai_ad_editor.VERSION, device=torch.cuda.get_device_name(0), dimensions=[w, h],
        actual_CUDA=True, source_fallback=False, CPU_fallback=False, expected_srgb_EV1_value=expected_value,
        all_RGBA_equal_to_independent_scalar_reference=True, hidden_RGB_alpha_unselected_and_gray1_protection_equal=True,
        protected_neighbour_does_not_bleed=True, cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated(),
        elapsed_seconds=time.monotonic()-began, model_forwards=0, scope='one_4K_operator_frame_plus_small_protected_neighbour',
        long_video_throughput_accepted=False, natural_quality_accepted=False)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', 'utf-8'); print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--installed', type=Path, required=True); parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); run(args.installed, args.output)
