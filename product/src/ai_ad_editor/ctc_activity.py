"""Audio-conditioned word-region estimation, preserving original CTC anchors."""
from __future__ import annotations

import copy
import math
from bisect import bisect_left

from .ctc_alignment import MAX_SAMPLES, MAX_TOKENS, SAMPLE_RATE, fail

FRAME = 80
BLOCK_FRAMES = 2048
MAX_GAP = 8
MAX_SUPPORT_GAP = 24
MIN_FRAMES = 4
MAX_MOVEMENT = 12000
ALGORITHM = 'ctc-guided-activity-v3'


def refine_units(pcm, units, *, offset=0, checkpoint=lambda: None):
    """Estimate only isolated word regions; ambiguous continuous speech stays raw.

    No reference annotations, word durations or fixed time padding are inputs.
    All decisions are reproducible from signed-16 PCM and validated CTC units.
    """
    import numpy as np
    signal = np.asarray(pcm)
    if (signal.ndim != 1 or signal.dtype.kind != 'i' or signal.dtype.itemsize != 2
            or not 0 < signal.size <= MAX_SAMPLES or type(offset) is not int or offset < 0
            or not isinstance(units, list) or not 0 < len(units) <= MAX_TOKENS):
        raise fail('ALIGNMENT_ACTIVITY_INPUT_INVALID', '活动边界需要有界单声道 signed-16 PCM 与明确源偏移')
    count = (signal.size + FRAME - 1) // FRAME
    sample_step = max(1, signal.size // 64000)
    dc = int(np.median(signal[::sample_step]))
    energy = np.empty(count, dtype=np.int64)
    for begin in range(0, count, BLOCK_FRAMES):
        checkpoint()
        end = min(count, begin + BLOCK_FRAMES)
        piece = signal[begin * FRAME:min(signal.size, end * FRAME)].astype(np.int64)
        piece -= dc
        complete = len(piece) // FRAME
        if complete:
            block = piece[:complete * FRAME].reshape(complete, FRAME)
            sums = (block * block).sum(axis=1, dtype=np.int64)
            energy[begin:begin + complete] = np.fromiter(
                (math.isqrt(int(value) // FRAME) for value in sums), dtype=np.int64, count=complete)
        remainder = piece[complete * FRAME:]
        if len(remainder):
            energy[begin + complete] = math.isqrt(int((remainder * remainder).sum()) // len(remainder))
    low_index, reference_index = (count - 1) // 5, 95 * (count - 1) // 100
    ordered = np.partition(energy, (low_index, reference_index))
    noise, reference = int(ordered[low_index]), int(ordered[reference_index])
    # Weak consonants/onsets must not inherit a global vowel-relative floor.
    # Keep the stronger reference only for admitting a candidate region.
    high, low = max(4, 4 * noise, (reference + 99) // 100), max(2, 2 * noise)
    activity = energy >= low
    # Fill bounded internal holes, never add leading/trailing activity.
    changes = np.flatnonzero(np.diff(np.r_[True, activity, True].astype(np.int8)))
    for a, b in zip(changes[::2], changes[1::2]):
        if a > 0 and b < count and b - a <= MAX_GAP:
            activity[a:b] = True
    changes = np.flatnonzero(np.diff(np.r_[False, activity, False].astype(np.int8)))
    regions = [(int(a) * FRAME + offset, min(signal.size, int(b) * FRAME) + offset)
               for a, b in zip(changes[::2], changes[1::2])
               if b - a >= MIN_FRAMES]
    strong = [bool(np.any(energy[(a-offset)//FRAME:(b-offset+FRAME-1)//FRAME] >= high)) for a,b in regions]
    centers = []
    previous = offset
    for unit in units:
        if (not isinstance(unit, dict) or type(unit.get('start_sample')) is not int
                or type(unit.get('end_sample')) is not int
                or not previous <= unit['start_sample'] < unit['end_sample'] <= offset + signal.size):
            raise fail('ALIGNMENT_ACTIVITY_INPUT_INVALID', '活动边界的原 CTC 词样本须有序并在输入范围内')
        centers.append((unit['start_sample'] + unit['end_sample']) // 2)
        previous = unit['end_sample']
    owners, unit_region = [], [None] * len(units)
    for region, (a, b) in enumerate(regions):
        checkpoint()
        left, right = bisect_left(centers, a), bisect_left(centers, b)
        members = list(range(left, right))
        owners.append(members)
        if strong[region]:
            for index in members:
                unit_region[index] = region
    extended, supports = [list(bounds) for bounds in regions], []
    for region, (a, b) in enumerate(regions):
        checkpoint()
        if strong[region] or owners[region]:
            continue
        candidates = []
        for neighbor in (region - 1, region + 1):
            if not 0 <= neighbor < len(regions) or not strong[neighbor] or len(owners[neighbor]) != 1:
                continue
            gap = a - regions[neighbor][1] if neighbor < region else regions[neighbor][0] - b
            if gap <= MAX_SUPPORT_GAP * FRAME:
                candidates.append(neighbor)
        status = 'ambiguous_support_preserved' if len(candidates) > 1 else 'unanchored_support_preserved'
        target = candidates[0] if len(candidates) == 1 else None
        if target is not None:
            extended[target][0] = min(extended[target][0], a)
            extended[target][1] = max(extended[target][1], b)
            status = 'weak_support_attached'
        supports.append(dict(region_index=region, target_region=target, status=status))
    results, decisions = copy.deepcopy(units), []
    for index, unit in enumerate(units):
        checkpoint()
        status, candidate = 'no_activity_anchor', None
        if noise > 0 and reference <= 4 * noise:
            status = 'low_signal_to_noise_preserved'
        elif unit_region[index] is not None:
            region = unit_region[index]
            a, b = extended[region]
            candidate = dict(start_sample=a, end_sample=b)
            if len(owners[region]) != 1:
                status = 'shared_activity_preserved'
            elif not a - FRAME <= unit['start_sample'] < unit['end_sample'] <= b + FRAME:
                status = 'anchor_crosses_region_preserved'
            elif max(abs(a - unit['start_sample']), abs(b - unit['end_sample'])) > MAX_MOVEMENT:
                status = 'movement_budget_preserved'
            elif ((index and a < units[index - 1]['end_sample'])
                  or (index + 1 < len(units) and b > units[index + 1]['start_sample'])):
                status = 'neighbor_conflict_preserved'
            else:
                status = 'activity_estimated'
                results[index]['start_sample'], results[index]['end_sample'] = a, b
        decisions.append(dict(unit_index=index, status=status, candidate=candidate,
            changed=(results[index]['start_sample'], results[index]['end_sample']) != (unit['start_sample'], unit['end_sample'])))
    report = dict(algorithm=ALGORITHM, sample_rate=SAMPLE_RATE, frame_samples=FRAME,
        dc_offset=dc, dc_subsample_step=sample_step, noise_rms=noise, reference_rms=reference,
        low_threshold=low, high_threshold=high, max_internal_gap_frames=MAX_GAP,
        max_support_gap_frames=MAX_SUPPORT_GAP, min_region_frames=MIN_FRAMES, max_movement_samples=MAX_MOVEMENT,
        regions=[dict(start_sample=a, end_sample=b, anchored_units=members, strong_activity=has_high)
                 for (a, b), members, has_high in zip(regions, owners, strong)],
        support_attachments=supports,
        decisions=decisions, changed_units=sum(item['changed'] for item in decisions),
        review_required=True, continuous_speech_boundaries_not_inferred=True)
    return results, report
