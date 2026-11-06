"""Complete text68 candidate contracts, written before the first test run.

Normative corpus comparison lives in the separate validation driver. These
contracts cover public offsets, invariants, authored timing and failure paths.
No current CLI67 source or installed Skill is imported or modified.
"""
from fractions import Fraction
import math
import unittest
from unittest.mock import patch

import aek_unicode17 as t
from aek_unicode17._vendor.db import get_value


class Text68Contracts(unittest.TestCase):
    def error(self, code, action):
        with self.assertRaises(t.TextError) as caught:
            action()
        self.assertEqual(code, caught.exception.code)

    def test_flags_combining_emoji_hangul_indic_prepend_exact_ranges(self):
        samples = [
            ('🇹🇼🇷🇺🇯', ['🇹🇼', '🇷🇺', '🇯']),
            ('a\u0308b', ['a\u0308', 'b']),
            ('👩🏽\u200d💻!', ['👩🏽\u200d💻', '!']),
            ('각각', ['각', '각']),
            ('क्\u200dष', ['क्\u200dष']),
            ('\u0600A', ['\u0600A']),
            ('\r\nA', ['\r\n', 'A']),
        ]
        for source, expected in samples:
            with self.subTest(source=source):
                spans = t.graphemes(source)
                self.assertEqual(expected, [span.text for span in spans])
                self.assertEqual(source, ''.join(span.text for span in spans))
                cursor = 0
                for span in spans:
                    self.assertEqual(cursor, span.start)
                    self.assertEqual(source[span.start:span.end], span.text)
                    cursor = span.end
                self.assertEqual(len(source), cursor)

    def test_unicode17_new_characters_do_not_depend_on_host_ucd(self):
        # U+11B60 SHARADA VOWEL SIGN OE was added in Unicode 17; its
        # GCB=Extend must work even when Python's unicodedata predates it.
        self.assertEqual('Extend', get_value('Grapheme_Cluster_Break', 0x11B60))
        self.assertEqual(['A\U00011b60'], [span.text for span in t.graphemes('A\U00011b60')])
        self.assertEqual('HH', get_value('Line_Break', 0x2010))
        self.assertEqual('AL', get_value('Bidi_Class', 0x070E))

    def test_scalar_utf16_roundtrip_and_half_surrogate_rejection(self):
        text = 'A😀🇹🇼e\u0301'
        expected = [0, 1, 3, 5, 7, 8, 9]
        self.assertEqual(expected, [t.scalar_to_utf16(text, i) for i in range(len(text) + 1)])
        for scalar, units in enumerate(expected):
            self.assertEqual(scalar, t.utf16_to_scalar(text, units))
        for units in (2, 4, 6, 10):
            self.error('TEXT_UTF16_BOUNDARY', lambda units=units: t.utf16_to_scalar(text, units))

    def test_invalid_text_and_offsets_fail_before_measurement(self):
        self.error('TEXT_TYPE', lambda: t.graphemes(None))
        self.error('TEXT_SURROGATE', lambda: t.graphemes('x\ud800'))
        self.error('TEXT_BUDGET', lambda: t.graphemes('x' * 16385))
        self.error('TEXT_GRAPHEME_BUDGET', lambda: t.graphemes('x' * 4097))
        for value in (True, -1, 1.5, 99):
            self.error('TEXT_INTEGER', lambda value=value: t.scalar_to_utf16('A', value))
        self.assertEqual((), t.graphemes(''))
        self.assertEqual(0, t.utf16_to_scalar('', 0))

    def test_cjk_punctuation_and_glue_word_joiner(self):
        source = '你好，世界。'
        self.assertEqual([1, 3, 4, 6], [item.offset for item in t.line_breaks(source)])
        for source in ('A\u00a0B', 'A\u202fB', 'A\u2060B'):
            with self.subTest(source=source):
                self.assertEqual([len(source)], [item.offset for item in t.line_breaks(source)])
                result = t.wrap_text(source, 1, len)
                self.assertEqual(1, len(result.lines))
                self.assertTrue(result.lines[0].overflow)
                self.assertEqual(source, result.lines[0].text)

    def test_hard_separators_crlf_and_trailing_empty_line(self):
        source = 'A\r\nB\rC\u0085D\u2028E\u2029'
        result = t.wrap_text(source, 20, len)
        self.assertEqual(['A', 'B', 'C', 'D', 'E', ''], [line.text for line in result.lines])
        self.assertEqual(['mandatory'] * 5 + ['end'], [line.break_kind for line in result.lines])
        self.assertEqual(source, ''.join(source[line.start:line.end] for line in result.lines))
        self.assertEqual([(0, 3), (3, 5), (5, 7), (7, 9), (9, 11), (11, 11)],
                         [(line.start, line.end) for line in result.lines])
        self.assertEqual([(3, 'mandatory'), (4, 'end')],
                         [(item.offset, item.kind) for item in t.line_breaks('A\r\nB')])

    def test_wrap_lossless_offsets_no_normalization_and_no_nbsp_trimming(self):
        source = 'a\u0308 b\u00a0 c  d'
        result = t.wrap_text(source, 4, len)
        self.assertEqual(source, result.source)
        self.assertEqual(source, ''.join(source[line.start:line.end] for line in result.lines))
        cursor = 0
        edges = {0} | {span.end for span in t.graphemes(source)}
        for line in result.lines:
            self.assertEqual(cursor, line.start)
            self.assertIn(line.start, edges)
            self.assertIn(line.end, edges)
            self.assertEqual(source[line.content_start:line.content_end], line.text)
            cursor = line.end
        nbsp = t.wrap_text('A\u00a0', 20, len).lines[0]
        self.assertEqual('A\u00a0', nbsp.text)
        self.assertEqual(2, nbsp.content_end)

    def test_explicit_whitespace_policy_only_trims_ascii_line_ends(self):
        source = '  A \t\r\n B '
        trimmed = t.wrap_text(source, 99, len)
        retained = t.wrap_text(source, 99, len, trim_line_end=False)
        self.assertEqual(['  A', ' B'], [line.text for line in trimmed.lines])
        self.assertEqual(['  A \t', ' B '], [line.text for line in retained.lines])
        self.assertEqual(source, ''.join(source[line.start:line.end] for line in trimmed.lines))

    def test_nonmonotonic_whole_run_measure_is_not_prefix_estimation(self):
        seen = []
        def shape(text):
            seen.append(text)
            return {'甲': 10, '甲乙': 4, '甲乙丙': 6, '丙': 1}[text]
        result = t.wrap_text('甲乙丙', 5, shape)
        self.assertEqual(['甲乙', '丙'], [line.text for line in result.lines])
        self.assertEqual([4, 1], [line.width for line in result.lines])
        self.assertEqual(4, result.measurement_count)
        self.assertEqual(['甲', '甲乙', '甲乙丙', '丙'], seen)

    def test_overflow_rejection_and_measurement_failures_are_explicit(self):
        self.error('TEXT_OVERFLOW', lambda: t.wrap_text('unbroken', 2, len, overflow='reject'))
        for width in (0, -1, True, math.nan, math.inf, 10**1000, '12'):
            self.error('TEXT_WIDTH', lambda width=width: t.wrap_text('A', width, len))
        for value in (math.nan, math.inf, -1, True, 10**1000, '5'):
            self.error('TEXT_MEASURE', lambda value=value: t.wrap_text('A', 5, lambda _: value))
        self.error('TEXT_MEASURE', lambda: t.wrap_text('A', 5, None))
        self.error('TEXT_MEASURE', lambda: t.wrap_text('A', 5, lambda _: 1 / 0))
        self.error('TEXT_OPTION', lambda: t.wrap_text('A', 5, len, overflow='guess'))
        self.error('TEXT_OPTION', lambda: t.line_breaks('A', preserve_graphemes='yes'))

    def test_resource_budgets_stop_instead_of_silent_partial_layout(self):
        self.error('TEXT_LINE_BUDGET', lambda: t.wrap_text('\n' * 512, 1, len))
        with patch('aek_unicode17.core.MAX_MEASUREMENTS', 2):
            self.error('TEXT_MEASURE_BUDGET', lambda: t.wrap_text('甲乙丙丁', 1, len))
        result = t.wrap_text('', 1, lambda _: self.fail('Empty text must not invoke font metrics'))
        self.assertEqual(1, len(result.lines))
        self.assertEqual(('', 0, 0), (result.lines[0].text, result.lines[0].start, result.lines[0].end))

    def test_paragraph_base_direction_ignores_isolates_and_later_paragraphs(self):
        for text, expected in [('مرحبا', 'rtl'), ('שלום', 'rtl'), ('12 abc', 'ltr'),
                               ('123', 'ltr'), ('\u2067مرحبا\u2069abc', 'ltr'),
                               ('\u2066abc\u2069שלום', 'rtl'),
                               ('\u2066\u2067א\u2069A\u2069ب', 'rtl'),
                               ('123\nשלום', 'ltr'), ('\u202eABC', 'ltr')]:
            with self.subTest(text=text):
                self.assertEqual(expected, t.paragraph_direction(text))
        self.assertEqual('rtl', t.paragraph_direction('123', default='rtl'))
        self.assertEqual('rtl', t.paragraph_direction('\u2067abc', default='rtl'))
        self.error('TEXT_DIRECTION', lambda: t.paragraph_direction('A', default='auto'))

    def test_rational_reveal_plan_matches_independent_fraction_oracle(self):
        text = 'A🇹🇼e\u0301👩🏽\u200d💻Z'
        ends = [span.end for span in t.graphemes(text)]
        for fps_num, fps_den, start, duration, hz in [(30000, 1001, 17, 901, 1000),
                                                     (24, 1, 10**14 + 3, 1001, 90000),
                                                     (1, 1, 0, 1, 90000)]:
            expected = {}
            for index, end in enumerate(ends, 1):
                instant = Fraction(start, hz) + Fraction(duration * index, hz * len(ends))
                frame = math.ceil(instant * Fraction(fps_num, fps_den))
                expected[frame] = (end, index)
            actual = t.reveal_plan(text, start_tick=start, duration_ticks=duration,
                                   clock_hz=hz, fps_num=fps_num, fps_den=fps_den)
            self.assertEqual([(frame, end, count) for frame, (end, count) in expected.items()],
                             [(event.frame, event.end, event.grapheme_count) for event in actual])
            self.assertEqual(len(text), actual[-1].end)
            for event in actual:
                self.assertIn(event.end, ends)

    def test_reveal_integer_validation_and_empty_source(self):
        base = dict(start_tick=0, duration_ticks=1, clock_hz=1000, fps_num=25, fps_den=1)
        self.assertEqual((), t.reveal_plan('', **base))
        for key in base:
            for invalid in (True, 1.5, -1, 2**53):
                config = dict(base, **{key: invalid})
                self.error('TEXT_INTEGER', lambda config=config: t.reveal_plan('A', **config))
        for key in ('duration_ticks', 'clock_hz', 'fps_num', 'fps_den'):
            self.error('TEXT_INTEGER', lambda key=key: t.reveal_plan('A', **dict(base, **{key: 0})))

    def test_default_linebreaks_and_egc_tailoring_have_distinct_profiles(self):
        source = '🇹🇼👩🏽\u200d💻a\u0308甲'
        raw = {item.offset for item in t.line_breaks(source, preserve_graphemes=False)}
        safe = {item.offset for item in t.line_breaks(source)}
        edges = {span.end for span in t.graphemes(source)}
        self.assertEqual(raw & edges, safe)
        self.assertIn(len(source), safe)
        self.assertEqual((t.Break(0, 'end'),), t.line_breaks(''))


if __name__ == '__main__':
    unittest.main()
