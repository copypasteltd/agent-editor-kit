"""Four independent model estimates with shared, disk-backed overlap/add."""
from __future__ import annotations

import math
from pathlib import Path

ROLES = ('drums', 'bass', 'other', 'vocals')


def separate_pcm(source: Path, outputs: dict[str, Path], *, window: int, overlap: float, infer) -> dict:
    """Keep all four model sources; never manufacture instruments as residuals.

    infer maps normalized (2, window) to (4, 2, window). All estimates use
    the same source normalization and OLA weights. The raw estimate sum is
    measured, without projecting its error onto another instrument.
    """
    import numpy as np
    from .separation_dsp import segment_ranges

    if (set(outputs) != set(ROLES) or len({source.resolve(), *(p.resolve() for p in outputs.values())}) != 5
            or any(p.exists() for p in outputs.values())):
        raise ValueError('Four different new output files are required')
    size = source.stat().st_size
    if not size or size % 8:
        raise ValueError('Expected interleaved float32 stereo PCM')
    count = size // 8
    ranges = segment_ranges(count, window, overlap)
    mixture = np.memmap(source, dtype='<f4', mode='r', shape=(count, 2))
    maps = {}; weights = None
    weight_path = outputs['drums'].with_suffix('.weights.f32')
    if weight_path.exists():
        mixture._mmap.close()
        raise ValueError('Existing weight file is preserved')
    created = []; succeeded = False
    try:
        sum_ref = sum_ref2 = sum_all2 = peak = 0.0
        for start in range(0, count, 262144):
            block = np.asarray(mixture[start:start+262144], dtype=np.float64)
            if not np.isfinite(block).all():
                raise ValueError('Nonfinite decoded audio')
            ref = block.mean(axis=1)
            sum_ref += float(ref.sum()); sum_ref2 += float((ref*ref).sum())
            sum_all2 += float((block*block).sum()); peak = max(peak, float(np.abs(block).max()))
        mean = sum_ref / count
        std = math.sqrt(max(0, sum_ref2/count-mean*mean))
        if std < 1e-8:
            std = math.sqrt(max(0, sum_all2/(count*2)-mean*mean))
        std = max(std, 1e-8)
        for role in ROLES:
            outputs[role].touch(exist_ok=False); created.append(outputs[role])
            maps[role] = np.memmap(outputs[role], dtype='<f4', mode='w+', shape=(count, 2))
            maps[role][:] = 0
        weight_path.touch(exist_ok=False); created.append(weight_path)
        weights = np.memmap(weight_path, dtype='<f4', mode='w+', shape=(count,))
        weights[:] = 0
        calls = 0
        if peak:
            indices = np.arange(window, dtype=np.float32)
            triangle = np.minimum(indices+1, window-indices)
            triangle /= triangle.max()
            for start, end in ranges:
                length = end-start
                chunk = np.zeros((2, window), dtype=np.float32)
                chunk[:, :length] = (mixture[start:end].T-mean)/std
                estimate = np.asarray(infer(chunk), dtype=np.float32)
                calls += 1
                if estimate.shape != (4, 2, window) or not np.isfinite(estimate).all():
                    raise ValueError('Invalid four-source model shape or samples')
                weight = triangle[:length]
                for index, role in enumerate(ROLES):
                    restored = estimate[index, :, :length].T*std+mean/4
                    maps[role][start:end] += restored*weight[:, None]
                weights[start:end] += weight
        else:
            weights[:] = 1
        peaks = dict.fromkeys(ROLES, 0.0)
        max_error = squared_error = squared_input = 0.0
        for start in range(0, count, 262144):
            end = min(count, start+262144); w = np.asarray(weights[start:end])
            if not np.isfinite(w).all() or not (w > 0).all():
                raise ValueError('Uncovered samples in overlap/add')
            summed = np.zeros((end-start, 2), dtype=np.float64)
            for role in ROLES:
                maps[role][start:end] /= w[:, None]
                block = np.asarray(maps[role][start:end])
                if not np.isfinite(block).all():
                    raise ValueError('Nonfinite separated output')
                peaks[role] = max(peaks[role], float(np.abs(block).max()))
                summed += block
            original = np.asarray(mixture[start:end], dtype=np.float64)
            difference = summed-original
            max_error = max(max_error, float(np.abs(difference).max()))
            squared_error += float((difference*difference).sum())
            squared_input += float((original*original).sum())
        for mapping in maps.values(): mapping.flush()
        succeeded = True
        return dict(samples=count, channels=2, segments=len(ranges), model_calls=calls,
                    normalization_mean=mean, normalization_std=std, peaks=peaks,
                    raw_sum_max_abs_error=max_error, raw_sum_rms_error=math.sqrt(squared_error/(count*2)),
                    input_rms=math.sqrt(squared_input/(count*2)), input_peak=peak,
                    source_order=list(ROLES), estimate_method='four_independent_model_sources',
                    mixture_projection='none', dc_method='shared_source_mean_divided_by_four',
                    silence_fast_path=peak == 0)
    finally:
        for mapping in (mixture, weights, *maps.values()):
            if mapping is not None: mapping._mmap.close()
        for path in created:
            if path == weight_path or not succeeded: path.unlink(missing_ok=True)
