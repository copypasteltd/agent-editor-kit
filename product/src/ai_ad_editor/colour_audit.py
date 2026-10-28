"""Bounded all-frame colour receipts; the last-frame receipt is not a total."""
import hashlib
import json

COUNTERS = ('hdr_input_components_clipped', 'hdr_output_components_clipped',
            'encoded_output_components_clipped', 'negative_components_clipped',
            'over_one_components_clipped', 'above_declared_peak_pixels')


class ColourAudit:
    def __init__(self):
        self.frames = 0
        self.first = self.last = None
        self.affected = 0
        self.first_affected = self.last_affected = None
        self.totals = {name: 0 for name in COUNTERS}
        self.maximum = {name: 0 for name in COUNTERS}
        self.digest = hashlib.sha256()

    def add(self, index, receipt):
        if type(index) is not int or index < 0 or (self.last is not None and index != self.last + 1):
            raise ValueError('Colour receipt frames must be contiguous nonnegative integers')
        counts = {name: receipt.get(name, 0) for name in COUNTERS}
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError('Colour receipt counters must be nonnegative integers')
        encoded = json.dumps(dict(frame=index, receipt=receipt), sort_keys=True,
                             separators=(',', ':'), allow_nan=False).encode('utf8')
        self.digest.update(len(encoded).to_bytes(8, 'big'))
        self.digest.update(encoded)
        if self.first is None: self.first = index
        self.last = index
        self.frames += 1
        if any(counts.values()):
            self.affected += 1
            if self.first_affected is None: self.first_affected = index
            self.last_affected = index
        for name, count in counts.items():
            self.totals[name] += count
            self.maximum[name] = max(self.maximum[name], count)

    def result(self):
        return dict(protocol='all-selected-frame-colour-audit-v1', frames=self.frames,
                    first_frame=self.first, last_frame=self.last,
                    frames_with_counted_events=self.affected,
                    first_affected_frame=self.first_affected, last_affected_frame=self.last_affected,
                    totals=dict(self.totals), maximum_per_frame=dict(self.maximum),
                    framed_receipts_sha256='sha256:' + self.digest.hexdigest(),
                    receipt_hash_covers_all_frames=True, whole_movie_receipt_cache=False,
                    native_CMM_internal_gamut_mapping_counted=False)
