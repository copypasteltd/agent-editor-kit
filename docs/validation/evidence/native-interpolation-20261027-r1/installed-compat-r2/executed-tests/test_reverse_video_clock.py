"""Reverse source intervals against independently sampled native frame identities."""
from bisect import bisect_left
from fractions import Fraction
from decimal import Decimal, localcontext
import math
import unittest
import test_cfr_boundaries as helpers


class ReverseVideoClockTests(unittest.TestCase):
    setUp = helpers.CFRBoundaryTests.setUp
    run_native = helpers.CFRBoundaryTests.run_native
    source = helpers.CFRBoundaryTests.source
    project = helpers.CFRBoundaryTests.project
    render = helpers.CFRBoundaryTests.render

    def assert_reverse(self, *, vfr=None, source_in=0, source_out=90000, speed=Fraction(1),
                       start=2970, offset=None, curve=False, alpha=False):
        path, colors, times = self.source(count=len(vfr) if vfr else 55, vfr=vfr)
        if offset is not None or alpha:
            transformed = self.work / 'transformed.nut'
            command = ['ffmpeg', '-v', 'error', '-i', path]
            if offset is not None:
                command += ['-output_ts_offset', offset]
            if alpha:
                command += ['-vf', 'colorchannelmixer=aa=0.75']
                colors = [(r, g, b, 191) for r, g, b, _ in colors]
            self.run_native([*command, '-fps_mode', 'passthrough', '-enc_time_base', 'filter',
                             '-c:v', 'ffv1', '-pix_fmt', 'bgra', transformed])
            path = transformed
        patch = {'reverse': True, 'speed': float(speed)}
        duration = round(Fraction(source_out-source_in) / speed)
        if curve:
            span_tick = source_out-source_in
            duration = round(Fraction(str(math.log(3)))*span_tick)
            patch['speed_curve'] = {'keyframes': [{'at_tick': 0, 'speed': .5},
                                                  {'at_tick': span_tick, 'speed': 1.5}]}
        project, sequence, _ = self.project(path, start=start, duration=duration,
            source_in=source_in, source_out=source_out, patch=patch)
        actual, _, _ = self.render(project, sequence)
        rate = Fraction(30000, 1001)
        expected, identities = [], []
        for index in range(len(actual)):
            now = Fraction(index) / rate
            selected = -1
            if Fraction(start, 90000) <= now < Fraction(start+duration, 90000):
                # Reverse of [a,b) uses the frame immediately before b at t=0,
                # and swaps covering frames on exact original boundaries.
                elapsed = now-Fraction(start, 90000)
                source_time = Fraction(source_out, 90000) - elapsed*speed
                if curve:
                    with localcontext() as context:
                        context.prec = 50
                        span = Decimal(source_out-source_in)/90000
                        time = Decimal(elapsed.numerator)/elapsed.denominator
                        source_time = Decimal(source_out)/90000 - span*Decimal('.5')*((time/span).exp()-1)
                native_end = times[-1]+Fraction(1, 25)
                if source_time <= native_end:
                    selected = bisect_left(times, source_time)-1
            identities.append(selected)
            color = colors[selected] if selected >= 0 else (0, 0, 0, 255)
            if alpha and selected >= 0:
                color = tuple((v*color[3]+127)//255 for v in color[:3])+(255,)
            expected.append(bytes(color) * (helpers.W*helpers.H))
        self.assertTrue(all(frame[3::4] == b'\xff'*(helpers.W*helpers.H) for frame in actual))
        wrong = [i for i, pair in enumerate(zip(actual, expected))
                 if max(abs(a-b) for a, b in zip(*pair)) > (1 if alpha else 0)]
        self.assertEqual(wrong, [], f'wrong output frames={wrong}; independent source indices={identities}')

    def test_reverse_preserves_each_VFR_frame_interval_duration(self):
        self.assert_reverse(vfr=[0, 33, 101, 188, 195, 441, 499, 800, 1002, 1221, 1600, 1800])

    def test_reverse_fractional_CFR_cut_in_keeps_partial_end_intervals(self):
        self.assert_reverse(source_in=10170, source_out=100170)

    def test_reverse_fractional_VFR_cut_in_and_speed_keep_original_time(self):
        self.assert_reverse(vfr=[0, 33, 101, 188, 195, 441, 499, 800, 1002, 1221, 1600, 1800],
                            source_in=10170, source_out=100170, speed=Fraction(3, 2))

    def test_reverse_nonzero_demux_origin_retains_source_interval_phase(self):
        self.assert_reverse(vfr=[0, 33, 101, 188, 195, 441, 499, 800, 1002, 1221, 1600, 1800],
                            source_in=10170, source_out=100170, offset='5.117123')

    def test_reverse_window_inside_one_VFR_hold_uses_partial_duration(self):
        self.assert_reverse(vfr=[0, 33, 101, 188, 195, 441, 499, 800, 1002, 1221, 1600, 1800],
                            source_in=10800, source_out=16200)

    def test_reverse_one_tick_window_emits_its_exact_global_sample(self):
        self.assert_reverse(source_in=45000, source_out=45001, start=3003)

    def test_reverse_preserves_gap_before_a_genuinely_short_source(self):
        self.assert_reverse(source_out=225000)

    def test_reverse_nonlinear_speed_uses_independent_decimal_inverse(self):
        self.assert_reverse(vfr=[0, 33, 101, 188, 195, 441, 499, 800, 1002, 1221, 1600, 1800],
                            source_in=10170, source_out=100170, curve=True)

    def test_reverse_partial_alpha_preserves_source_identity_and_composition(self):
        self.assert_reverse(vfr=[0, 33, 101, 188, 195, 441, 499, 800, 1002, 1221, 1600, 1800],
                            source_in=10170, source_out=100170, alpha=True)


if __name__ == '__main__':
    unittest.main()
