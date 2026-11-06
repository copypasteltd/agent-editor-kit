"""Real native/font behavior, source geometry, lifecycle and publication contracts."""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from aek_shaping import Engine, FontSpec, ShapingError, layout, selection, shape_line, Renderer, prefix_plan
from aek_shaping.cli import execute, publish_file, strict_json
from font_fixture import font_bytes, checksum, post_names


class NativeTypography(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = Path(os.environ['SHAPING69_RUNTIME'])
        cls.work = Path(os.environ['SHAPING69_TESTROOT'])
        cls.work.mkdir(exist_ok=False)
        cls.engine = Engine(cls.runtime / 'native.json')
        cls.stack = ExitStack()
        cls.fonts = []
        for role in ('latin', 'arabic', 'hebrew', 'devanagari', 'cjk'):
            row = cls.engine.manifest['fonts'][role]
            cls.fonts.append(cls.stack.enter_context(cls.engine.font(FontSpec(cls.runtime / row['path'], row['sha256'], 48))))
        arabic = cls.engine.manifest['fonts']['arabic']
        cls.arabic_names = post_names((cls.runtime / arabic['path']).read_bytes())
        cls.geometry = []
        for carets in (True, False):
            raw = font_bytes(carets=carets)
            path = cls.work / ('geometry-' + str(carets) + '.ttf')
            path.write_bytes(raw)
            cls.geometry.append(cls.stack.enter_context(cls.engine.font(FontSpec(path, hashlib.sha256(raw).hexdigest(), 100))))

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def error(self, code, function, *args, **kwargs):
        with self.assertRaises(ShapingError) as raised:
            function(*args, **kwargs)
        self.assertEqual(raised.exception.code, code)

    def test_mixed_direction_independent_visual_order(self):
        result = self.engine.bidi('Aאב12Z', base='ltr')
        self.assertEqual(result['levels'], [0, 1, 1, 2, 2, 0])
        self.assertEqual(result['order'], [0, 3, 4, 2, 1, 5])

    def test_line_l1_whitespace_reset(self):
        result = self.engine.bidi('Aאב  X', base='ltr', start=0, end=5)
        self.assertEqual(result['levels'][3:5], [0, 0])
        self.assertEqual(result['order'], [0, 2, 1, 3, 4])

    def test_arabic_joining_uses_real_context(self):
        joined = shape_line(self.engine, 'بب', self.fonts, base='rtl')
        isolated = shape_line(self.engine, 'ب', self.fonts, base='rtl')
        # This pinned Noto font decomposes beh into a dot and a dotless base.
        # Assert its author-named initial/final forms and every source cluster;
        # counting all glyphs as letters would incorrectly reject valid marks.
        self.assertEqual([self.arabic_names[glyph['id']] for glyph in joined['glyphs']],
                         ['dotbelowar', 'uni066E.fina', 'dotbelowar', 'uni066E.init'])
        self.assertEqual([self.arabic_names[glyph['id']] for glyph in isolated['glyphs']],
                         ['dotbelowar', 'uni066E'])
        self.assertEqual([(glyph['source_start'], glyph['source_end']) for glyph in joined['glyphs']],
                         [(1, 2), (1, 2), (0, 1), (0, 1)])
        self.assertEqual(sum(glyph['x_advance'] > 0 for glyph in joined['glyphs']), 2)
        self.assertTrue(all(glyph['font'] == 1 for glyph in joined['glyphs']))
        self.assertNotIn(isolated['glyphs'][-1]['id'], [glyph['id'] for glyph in joined['glyphs']])
        self.assertTrue(all(glyph['x_advance'] == 0 and glyph['width'] > 0 and glyph['height'] != 0
                            for glyph in joined['glyphs'] if self.arabic_names[glyph['id']] == 'dotbelowar'))

    def test_arabic_lam_alef_uses_font_required_contextual_forms(self):
        result = shape_line(self.engine, 'لا', self.fonts, base='rtl')
        # NotoSansArabic encodes lam-alef as two rlig contextual components,
        # rather than one ligature glyph. The separate real ffi GSUB/GDEF test
        # continues to require an actual one-glyph, three-character ligature.
        self.assertEqual([self.arabic_names[glyph['id']] for glyph in result['glyphs']],
                         ['uni0627.fina.rlig', 'uni0644.init.rlig'])
        self.assertEqual([(glyph['source_start'], glyph['source_end']) for glyph in result['glyphs']],
                         [(1, 2), (0, 1)])
        self.assertTrue(all(glyph['font'] == 1 and glyph['x_advance'] > 0 for glyph in result['glyphs']))
        unrequired = shape_line(self.engine, 'لا', self.fonts, base='rtl', features={'rlig': 0})
        self.assertNotEqual([glyph['id'] for glyph in result['glyphs']],
                            [glyph['id'] for glyph in unrequired['glyphs']])
        self.assertTrue(all('.rlig' not in self.arabic_names[glyph['id']] for glyph in unrequired['glyphs']))

    def test_rtl_mirroring_is_shaped_not_logical_swapping(self):
        result = shape_line(self.engine, '(אב)', self.fonts, base='rtl')
        glyph = next(row for row in result['glyphs'] if row['source_start'] == 0)
        self.assertEqual(glyph['id'], self.fonts[glyph['font']].nominal(')'))

    def test_devanagari_cjk_and_marks_use_explicit_fonts(self):
        result = layout(self.engine, 'नमस्ते 中文 A\u0301', self.fonts)
        self.assertTrue(any(glyph['font'] == 3 for line in result.lines for glyph in line.glyphs))
        self.assertTrue(any(glyph['font'] == 4 for line in result.lines for glyph in line.glyphs))
        self.assertTrue(all(glyph['id'] != 0 for line in result.lines for glyph in line.glyphs))
        self.error('TEXT_SELECTION_BOUNDARY', selection, result, [[len(result.source)-1, len(result.source)]])

    def test_missing_glyph_never_uses_system_fallback(self):
        self.error('TEXT_MISSING_GLYPH', layout, self.engine, '\U0010ffff', self.fonts)

    def test_source_wrap_preserves_crlf_and_blank_lines(self):
        source = 'A אב 12 words words\r\n\r\n中文中文中文'
        result = layout(self.engine, source, self.fonts, max_width=220)
        self.assertEqual(''.join(source[line.start:line.end] for line in result.lines), source)
        self.assertTrue(all(a.end == b.start for a, b in zip(result.lines, result.lines[1:])))
        self.assertTrue(all(line.width <= 220 * 64 for line in result.lines))

    def test_mandatory_line_separator_keeps_paragraph_base(self):
        result = layout(self.engine, 'ا\u2028A', self.fonts)
        self.assertEqual(len(result.lines), 2)
        self.assertEqual([line.base for line in result.lines], [1, 1])
        self.assertEqual(result.lines[0].end, 2)

    def test_fixture_real_gsub_and_unequal_gdef_positions(self):
        font = self.geometry[0]
        result = shape_line(self.engine, 'ffi', [font], base='ltr')
        self.assertEqual(checksum(font_bytes()), 0xB1B0AFBA)
        self.assertEqual(len(result['glyphs']), 1)
        self.assertEqual(result['glyphs'][0]['id'], 4)
        self.assertEqual(result['width'], 6400)
        self.assertEqual(font.carets(4, 0), [1280, 5120])

    def test_partial_ligature_uses_actual_gdef_not_equal_subdivision(self):
        plan = layout(self.engine, 'ffi', self.geometry[:1])
        selected = selection(plan, [[1, 2]])
        self.assertEqual(selected['clusters'][0]['intervals'], [(1280, 5120)])
        self.assertEqual(selected['clusters'][0]['caret_source'], 'font-GDEF-through-HarfBuzz')
        renderer = Renderer(plan)
        normal, a = renderer.render()
        active, b = renderer.render(selected)
        self.assertEqual(a['alpha'], b['alpha'])
        changed = [index for index, value in enumerate(b['selected_alpha']) if value]
        self.assertEqual(sorted({index % renderer.width - renderer.padding for index in changed}), list(range(20, 80)))
        self.assertGreater(len(changed), 0)
        self.assertTrue(all(normal[4*i:4*i+4] == active[4*i:4*i+4] for i, value in enumerate(b['selected_alpha']) if not value))

    def test_missing_carets_reject_or_report_explicit_cluster_expansion(self):
        plan = layout(self.engine, 'ffi', self.geometry[1:])
        self.error('TEXT_PARTIAL_LIGATURE_CARETS', selection, plan, [[1, 2]])
        selected = selection(plan, [[1, 2]], partial='cluster')
        self.assertTrue(selected['clusters'][0]['expanded'])
        self.assertEqual(selected['clusters'][0]['source_end'], 3)
        joined = selection(plan, [[0, 1], [1, 2], [2, 3]])
        self.assertFalse(joined['clusters'][0]['expanded'])

    def test_mixed_selection_preserves_all_alpha_and_unselected_rgb(self):
        plan = layout(self.engine, 'AEK אבג 123 مرحبا', self.fonts)
        renderer = Renderer(plan)
        normal, a = renderer.render()
        active, b = renderer.render(selection(plan, [[5, 10], [13, len(plan.source)]]))
        self.assertEqual(a['alpha'], b['alpha'])
        self.assertGreater(b['selected_pixels'], 0)
        self.assertTrue(all(normal[4*i:4*i+4] == active[4*i:4*i+4] for i, value in enumerate(b['selected_alpha']) if not value))
        again, c = renderer.render()
        self.assertEqual(again, normal)
        self.assertLessEqual(c['cache_bytes'], 32 * 1024**2)

    def test_reveal_reshapes_without_hidden_suffix_and_keeps_rtl_anchor(self):
        plan = layout(self.engine, 'بب', self.fonts, base='rtl')
        prefix = prefix_plan(plan, 1)
        standalone = shape_line(self.engine, 'ب', self.fonts, base='rtl')
        self.assertEqual(prefix.lines[0].glyphs[0]['id'], standalone['glyphs'][0]['id'])
        renderer = Renderer(plan)
        _, full = renderer.render()
        _, part = renderer.render(display_plan=prefix)
        self.assertEqual(full['origins_26_6'][0][0] + plan.lines[0].width,
                         part['origins_26_6'][0][0] + prefix.lines[0].width)
        self.assertEqual(full['origins_26_6'][0][1], part['origins_26_6'][0][1])
        self.assertEqual(renderer.render()[0], renderer.render(display_plan=prefix_plan(plan, len(plan.source)))[0])
        self.assertFalse(any(renderer.render(display_plan=prefix_plan(plan, 0))[1]['alpha']))

    def test_reveal_rejects_combining_or_crlf_split(self):
        plan = layout(self.engine, 'A\u0301\r\nA', self.fonts)
        self.error('TEXT_REVEAL_BOUNDARY', prefix_plan, plan, 1)
        self.error('TEXT_REVEAL_BOUNDARY', prefix_plan, plan, 3)

    def test_variation_digest_and_closed_font_lifecycle(self):
        row = self.engine.manifest['fonts']['cjk']
        with self.engine.font(FontSpec(self.runtime / row['path'], row['sha256'], 48, variations={'wght': 700})) as bold:
            default = self.fonts[4].bitmap(self.fonts[4].nominal('中'), 0, 0)
            stronger = bold.bitmap(bold.nominal('中'), 0, 0)
            self.assertNotEqual(default, stronger)
        self.error('TEXT_FONT_CLOSED', bold.nominal, '中')
        self.error('TEXT_FONT_DIGEST', self.engine.font, FontSpec(self.runtime / row['path'], '0' * 64, 48))
        self.error('TEXT_FONT_NATIVE', self.engine.font, FontSpec(self.runtime / row['path'], row['sha256'], 48, variations={'XXXX': 1}))

    def test_limits_fail_explicitly(self):
        self.error('TEXT_CONTROL_POLICY', layout, self.engine, 'A\tA', self.fonts)
        self.error('TEXT_LAYOUT_OPTION', layout, self.engine, 'A', self.fonts, max_width=True)
        self.error('TEXT_LINE_OVERFLOW', layout, self.engine, 'AAAAA', self.fonts, max_width=1)
        row = self.engine.manifest['fonts']['latin']
        with self.engine.font(FontSpec(self.runtime / row['path'], row['sha256'], 512)) as large:
            self.error('TEXT_CANVAS_BUDGET', Renderer, layout(self.engine, 'A' * 32, [large], max_width=65536))
        self.error('TEXT_RENDER_OPTION', Renderer, layout(self.engine, 'A', self.fonts), padding=-1)
        self.error('TEXT_FEATURE', layout, self.engine, 'A', self.fonts, features=[])

    def test_json_unknown_duplicate_nonfinite_and_existing_output(self):
        self.error('TEXT_JSON_DUPLICATE', strict_json, b'{"text":"A","text":"B"}')
        self.error('TEXT_JSON_NUMBER', strict_json, b'{"value":NaN}')
        path = self.work / 'preserve.bin'
        path.write_bytes(b'original')
        self.error('TEXT_OUTPUT_EXISTS', publish_file, path, b'new')
        self.assertEqual(path.read_bytes(), b'original')

    def test_atomic_file_race_preserves_external_writer(self):
        path = self.work / 'race.bin'
        real = os.link
        def racing(source, target):
            Path(target).write_bytes(b'external')
            real(source, target)
        with patch('aek_shaping.cli.os.link', racing):
            self.error('TEXT_OUTPUT_EXISTS', publish_file, path, b'new')
        self.assertEqual(path.read_bytes(), b'external')
        self.assertFalse(list(self.work.glob('race.bin.pending-*')))

    def test_actual_cli_inspect_render_and_unknown_field(self):
        request = dict(format='aek-shaping69-request-v1', runtime=str(self.runtime / 'native.json'), text='AEK אב 123 中文',
            fonts=[dict(path=str(font.spec.path), sha256=font.spec.sha256, pixels=48) for font in self.fonts])
        path = self.work / 'request.json'
        path.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
        result = execute('inspect', path, self.work / 'plan.json')
        self.assertGreater(result['glyphs'], 0)
        for launcher, folder in [(Path(__file__).parents[1] / 'aek_shaping69.py', 'source-render'),
                                 (self.runtime / 'run.py', 'portable-render')]:
            actual = subprocess.run([sys.executable, '-I', '-B', '-X', 'utf8', str(launcher), 'render', '--request', str(path),
                                     '--output', str(self.work / folder)], capture_output=True, timeout=60,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            self.assertEqual(actual.returncode, 0, actual.stdout.decode('utf-8', errors='replace') + actual.stderr.decode('utf-8', errors='replace'))
            self.assertTrue(json.loads(actual.stdout)['ok'])
        self.assertEqual((self.work / 'source-render/actual.png').read_bytes(), (self.work / 'portable-render/actual.png').read_bytes())
        request['unknown'] = True
        path.write_text(json.dumps(request), encoding='utf-8')
        self.error('TEXT_REQUEST_FIELDS', execute, 'inspect', path, self.work / 'unknown.json')

    def test_render_directory_race_preserves_foreign_files(self):
        row = self.engine.manifest['fonts']['latin']
        request = dict(format='aek-shaping69-request-v1', runtime=str(self.runtime / 'native.json'), text='AEK',
            fonts=[dict(path=str(self.runtime / row['path']), sha256=row['sha256'], pixels=48)])
        path = self.work / 'directory-race-request.json'
        path.write_text(json.dumps(request), encoding='utf-8')
        target = self.work / 'directory-race'
        real = os.rename
        def racing(source, destination):
            Path(destination).mkdir()
            (Path(destination) / 'foreign.txt').write_bytes(b'foreign')
            real(source, destination)
        with patch('aek_shaping.cli.os.rename', racing):
            self.error('TEXT_OUTPUT_EXISTS', execute, 'render', path, target)
        self.assertEqual((target / 'foreign.txt').read_bytes(), b'foreign')
        self.assertFalse(list(self.work.glob('directory-race.pending-*')))

    def test_native_digest_and_scalar_bounds(self):
        altered = dict(self.engine.manifest, binary_sha256='0' * 64)
        isolated = self.work / 'digest-rejection'
        isolated.mkdir()
        os.link(self.engine.binary, isolated / self.engine.binary.name)
        path = isolated / 'rejected-test-manifest.json'
        path.write_text(json.dumps(altered), encoding='utf-8')
        self.error('TEXT_NATIVE_DIGEST', Engine, path)
        self.error('TEXT_SOURCE', self.engine.bidi, '\ud800')
        self.error('TEXT_SOURCE', self.engine.bidi, 'A' * 16385)
