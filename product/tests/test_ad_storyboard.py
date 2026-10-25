from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from ai_ad_editor import ad_storyboard as ad
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import initial_project, load_project


def fixture():
    project = initial_project('Storyboard', 'storyboard_test')
    project['assets'] = [dict(id=key, kind=kind, sha256='sha256:' + '1' * 64,
        uri='assets/' + key, rights_ref=key, probe={'duration_tick': duration,
        'audio': {'codec': 'pcm_s16le'} if kind in ('video', 'audio') else {}})
        for key, kind, duration in [('picture', 'image', 0), ('other', 'image', 0),
            ('video', 'video', 900000), ('voice', 'audio', 90000), ('music', 'audio', 1800000), ('font', 'font', 0)]]
    brief = dict(id='sample', product='Actual product', audience='Video editors', cta='Try the local workflow',
        caption_style={'font_asset_id': 'font'},
        shots=[{'id': 'hook', 'asset_id': 'picture', 'text': 'Keep the original.', 'weight': 1},
               {'id': 'proof', 'asset_id': 'other', 'text': 'Make an editable version.', 'weight': 2},
               {'id': 'cta', 'asset_id': 'picture', 'text': 'Try the local workflow.', 'weight': 1}],
        variants=[{'id': 'vertical', 'canvas': {'width': 360, 'height': 640}, 'duration_seconds': 6},
                  {'id': 'wide', 'canvas': {'width': 640, 'height': 360}, 'duration_seconds': 9},
                  {'id': 'square', 'canvas': {'width': 360, 'height': 360}, 'duration_seconds': 6,
                   'shot_ids': ['proof', 'hook', 'cta'], 'overrides': {'hook': {'text': 'Another opening.'}}}])
    return project, brief


def find_clip(sequence, role, shot):
    return next(c for t in sequence['tracks'] for c in t['clips'] if c.get('ad_storyboard') == {'role': role, 'shot_id': shot})


class StoryboardPlanTests(unittest.TestCase):
    def setUp(self):
        self.project, self.brief = fixture()

    def assert_error(self, code, function, *args):
        with self.assertRaises(AppError) as caught:
            function(*args)
        self.assertEqual(caught.exception.code, code)

    def built(self):
        return ad.apply_plan(self.project, ad.plan_storyboard(self.project, self.brief))

    def test_variants_are_gapless_frame_aligned_and_preserve_source(self):
        before = copy.deepcopy(self.project)
        plan = ad.plan_storyboard(self.project, self.brief)
        self.assertEqual(self.project, before)
        self.assertEqual(len(plan['sequences']), 3)
        for sequence, seconds in zip(plan['sequences'], (6, 9, 6)):
            clips = sequence['tracks'][0]['clips']
            self.assertEqual(clips[0]['timeline_start_tick'], 0)
            self.assertEqual(clips[-1]['timeline_start_tick'] + clips[-1]['duration_tick'], seconds * 90000)
            self.assertTrue(all(a['timeline_start_tick'] + a['duration_tick'] == b['timeline_start_tick'] for a, b in zip(clips, clips[1:])))
            self.assertTrue(all(c['duration_tick'] % 3000 == 0 for c in clips))
        self.assertEqual(find_clip(plan['sequences'][2], 'caption', 'hook')['subtitle']['text'], 'Another opening.')

    def test_rational_fps_boundaries_do_not_accumulate_rounding(self):
        from fractions import Fraction
        self.project['settings']['timebase']['display_fps'] = {'num': 30000, 'den': 1001}
        self.brief['variants'][0]['duration_seconds'] = 7.34
        plan = ad.plan_storyboard(self.project, self.brief)
        for sequence in plan['sequences']:
            frames = sequence['ad_storyboard']['frames']
            self.assertEqual(sequence['duration_tick'], round(Fraction(frames * 90000 * 1001, 30000)))
            for clip in sequence['tracks'][0]['clips']:
                self.assertLessEqual(clip['timeline_start_tick'] + clip['duration_tick'], sequence['duration_tick'])
        self.assertTrue(plan['warnings'])

    def test_source_audio_is_explicit_and_its_gain_is_editable(self):
        self.brief['shots'][0].update(asset_id='video', include_source_audio=True, source_gain_db=-12)
        sequence = ad.plan_storyboard(self.project, self.brief)['sequences'][0]
        clip = find_clip(sequence, 'source_audio', 'hook')
        self.assertEqual(clip['audio']['gain_db'], -12)
        self.assertEqual(clip['source_out_tick'], find_clip(sequence, 'picture', 'hook')['source_out_tick'])

    def test_no_implicit_video_audio(self):
        self.brief['shots'][0]['asset_id'] = 'video'
        sequence = ad.plan_storyboard(self.project, self.brief)['sequences'][0]
        self.assertFalse([c for t in sequence['tracks'] for c in t['clips'] if c.get('ad_storyboard', {}).get('role') == 'source_audio'])

    def test_voice_is_complete_and_never_truncated(self):
        self.brief['shots'][0]['voice'] = {'asset_id': 'voice'}
        clip = find_clip(ad.plan_storyboard(self.project, self.brief)['sequences'][0], 'voice', 'hook')
        self.assertEqual(clip['source_out_tick'], 90000)
        self.project['assets'][3]['probe']['duration_tick'] = 900000
        self.assert_error('AD_VOICE_OUT_OF_WINDOW', ad.plan_storyboard, self.project, self.brief)

    def test_short_source_and_music_are_rejected(self):
        self.brief['music'] = {'asset_id': 'voice'}
        self.assert_error('AD_SOURCE_TOO_SHORT', ad.plan_storyboard, self.project, self.brief)
        self.brief.pop('music')
        self.brief['shots'][0].update(asset_id='video', source_in_tick=899999)
        self.assert_error('AD_SOURCE_TOO_SHORT', ad.plan_storyboard, self.project, self.brief)

    def test_nonfinite_boolean_and_nonpositive_weights_are_rejected(self):
        for value in (float('nan'), float('inf'), True, -1, 0, 'NaN'):
            with self.subTest(value=value):
                self.brief['shots'][0]['weight'] = value
                self.assert_error('AD_STORYBOARD_INVALID', ad.plan_storyboard, self.project, self.brief)

    def test_unknown_fields_and_duplicate_shots_are_rejected(self):
        brief = copy.deepcopy(self.brief); brief['shost'] = []
        self.assert_error('AD_STORYBOARD_INVALID', ad.plan_storyboard, self.project, brief)
        self.brief['shots'].append(copy.deepcopy(self.brief['shots'][0]))
        self.assert_error('AD_STORYBOARD_INVALID', ad.plan_storyboard, self.project, self.brief)

    def test_invalid_canvas_and_repeated_variants_are_rejected(self):
        self.brief['variants'][1]['id'] = 'vertical'
        self.assert_error('AD_STORYBOARD_INVALID', ad.plan_storyboard, self.project, self.brief)
        self.brief['variants'][1]['id'] = 'wide'
        self.brief['variants'][0]['canvas']['width'] = 361
        self.assert_error('OUTPUT_CANVAS_ALIGNMENT_INVALID', ad.plan_storyboard, self.project, self.brief)

    def test_missing_font_and_wrong_media_kind_are_rejected(self):
        self.brief['caption_style']['font_asset_id'] = 'picture'
        self.assert_error('AD_STORYBOARD_INVALID', ad.plan_storyboard, self.project, self.brief)

    def test_stale_plan_cannot_overwrite_current_edit(self):
        plan = ad.plan_storyboard(self.project, self.brief)
        self.project['sequences'][0]['name'] = 'Human changed this'
        self.assert_error('AD_PROJECT_CHANGED', ad.apply_plan, self.project, plan)

    def test_changed_and_rehashed_plan_cannot_inject_arbitrary_tracks(self):
        plan = ad.plan_storyboard(self.project, self.brief)
        plan['sequences'][0]['name'] = 'Tampered'
        self.assert_error('AD_PLAN_CHANGED', ad.apply_plan, self.project, plan)
        plan['plan_sha256'] = ad.digest({k: v for k, v in plan.items() if k != 'plan_sha256'})
        self.assert_error('AD_PLAN_CHANGED', ad.apply_plan, self.project, plan)

    def test_existing_variant_is_preserved_and_rejected(self):
        project = self.built()
        self.assert_error('AD_VARIANT_EXISTS', ad.plan_storyboard, project, self.brief)

    def test_revision_changes_only_requested_variant_shot_and_fields(self):
        project = self.built(); before = copy.deepcopy(project)
        request = {'campaign_id': 'sample', 'variant_ids': ['vertical'], 'shots': [{'id': 'hook', 'text': 'New confirmed copy.'}]}
        plan = ad.plan_revision(project, request)
        candidate = ad.apply_plan(project, plan)
        self.assertEqual(candidate['sequences'][0], before['sequences'][0])
        self.assertEqual(candidate['sequences'][2:], before['sequences'][2:])
        seq = candidate['sequences'][1]
        self.assertEqual(find_clip(seq, 'caption', 'hook')['subtitle']['text'], 'New confirmed copy.')
        for role, shot in [('picture', 'hook'), ('picture', 'proof'), ('caption', 'proof')]:
            self.assertEqual(find_clip(seq, role, shot), find_clip(before['sequences'][1], role, shot))
        self.assertEqual(project, before)

    def test_revision_preserves_manual_style_keyframes_and_crop(self):
        project = self.built(); seq = project['sequences'][1]
        caption = find_clip(seq, 'caption', 'hook'); caption['subtitle']['style']['fontcolor'] = 'yellow'
        picture = find_clip(seq, 'picture', 'hook'); picture['keyframes'] = [{'property': 'transform.scale', 'keyframes': []}]
        picture['crop']['x'] = 4
        request = {'campaign_id': 'sample', 'variant_ids': ['vertical'], 'shots': [{'id': 'hook', 'text': 'New copy.', 'asset_id': 'other'}]}
        changed = ad.apply_plan(project, ad.plan_revision(project, request))['sequences'][1]
        self.assertEqual(find_clip(changed, 'caption', 'hook')['subtitle']['style']['fontcolor'], 'yellow')
        self.assertEqual(find_clip(changed, 'picture', 'hook')['keyframes'], picture['keyframes'])
        self.assertEqual(find_clip(changed, 'picture', 'hook')['crop']['x'], 4)

    def test_locked_revision_track_is_not_overwritten(self):
        project = self.built(); project['sequences'][1]['tracks'][1]['locked'] = True
        request = {'campaign_id': 'sample', 'variant_ids': ['vertical'], 'shots': [{'id': 'hook', 'text': 'Changed'}]}
        self.assert_error('AD_TARGET_LOCKED', ad.plan_revision, project, request)

    def test_split_picture_revision_is_rejected(self):
        project = self.built(); clips = project['sequences'][1]['tracks'][0]['clips']; clips.append(copy.deepcopy(clips[0]))
        request = {'campaign_id': 'sample', 'variant_ids': ['vertical'], 'shots': [{'id': 'hook', 'text': 'Changed'}]}
        self.assert_error('AD_TARGET_CHANGED', ad.plan_revision, project, request)

    def test_add_and_remove_caption_and_voice_preserve_other_clips(self):
        self.brief['shots'][0]['text'] = ''
        project = self.built()
        request = {'campaign_id': 'sample', 'variant_ids': ['vertical'], 'shots': [{'id': 'hook', 'text': 'Added', 'voice': {'asset_id': 'voice'}}]}
        changed = ad.apply_plan(project, ad.plan_revision(project, request))
        self.assertEqual(find_clip(changed['sequences'][1], 'voice', 'hook')['duration_tick'], 90000)
        request['shots'][0].update(text='', voice=None)
        changed = ad.apply_plan(changed, ad.plan_revision(changed, request))
        self.assertFalse([c for t in changed['sequences'][1]['tracks'] for c in t['clips'] if c.get('ad_storyboard', {}).get('shot_id') == 'hook' and c.get('ad_storyboard', {}).get('role') in ('caption', 'voice')])

    def test_text_revision_preserves_independently_edited_voice(self):
        self.brief['shots'][0]['voice'] = {'asset_id': 'voice'}
        project = self.built(); sequence = project['sequences'][1]
        picture = find_clip(sequence, 'picture', 'hook')
        picture['duration_tick'] = 3000
        voice = find_clip(sequence, 'voice', 'hook'); voice['audio']['gain_db'] = -7
        request = {'campaign_id': 'sample', 'variant_ids': ['vertical'], 'shots': [{'id': 'hook', 'text': 'Edit text only'}]}
        candidate = ad.apply_plan(project, ad.plan_revision(project, request))
        self.assertEqual(find_clip(candidate['sequences'][1], 'voice', 'hook'), voice)


def invoke(*args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(list(map(str, args)))
    return code, json.loads(stream.getvalue())


class StoryboardCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory(prefix='aek-storyboard-base-')
        cls.directory = Path(cls.base.name)
        project = cls.directory / 'original'
        code, value = invoke('project', 'init', project, '--project-id', 'storyboard_cli')
        if code:
            raise AssertionError(value)
        for aid, color in [('picture', 'navy'), ('other', 'teal')]:
            image = cls.directory / (aid + '.png'); Image.new('RGB', (320, 180), color).save(image)
            code, value = invoke('media', 'ingest', '--project', project, '--input', image, '--asset-id', aid)
            if code:
                raise AssertionError(value)
        import ai_ad_editor
        font = Path(ai_ad_editor.__file__).parent / 'material_data/fonts/noto-sans-sc-variable.ttf'
        code, value = invoke('media', 'ingest', '--project', project, '--input', font, '--asset-id', 'font')
        if code:
            raise AssertionError(value)

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='aek-storyboard-cli-')
        self.root = Path(self.temp.name) / 'project'; shutil.copytree(self.directory / 'original', self.root)
        self.brief = fixture()[1]
        self.input = self.root / 'brief.json'; self.write(self.input, self.brief)
        self.output = self.root / 'validation/plan.json'
        self.original = (self.root / 'project.json').read_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def plan(self, *extra):
        return invoke('ad', 'storyboard', '--project', self.root, '--input', self.input, '--output', self.output, *extra)

    def test_dry_run_has_no_project_side_effects(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        code, value = self.plan('--dry-run')
        self.assertEqual(code, 0, value)
        self.assertEqual(before, {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_plan_then_atomic_build_and_idempotent_replay(self):
        code, value = self.plan(); self.assertEqual(code, 0, value)
        self.assertEqual((self.root / 'project.json').read_bytes(), self.original)
        args = ('ad', 'build', '--project', self.root, '--input', self.output, '--idempotency-key', 'story-build')
        code, value = invoke(*args); self.assertEqual(code, 0, value)
        built = (self.root / 'project.json').read_bytes()
        self.assertEqual(len(load_project(self.root)[1]['sequences']), 4)
        self.assertTrue(value['data']['before_snapshot'])
        code, value = invoke(*args); self.assertEqual(code, 0, value)
        self.assertEqual((self.root / 'project.json').read_bytes(), built)
        self.assertIn('IDEMPOTENT_REPLAY', {v['code'] for v in value['warnings']})

    def test_changed_actual_media_fails_without_project_edits(self):
        code, value = self.plan(); self.assertEqual(code, 0, value)
        project = load_project(self.root)[1]
        asset = next(a for a in project['assets'] if a['id'] == 'picture')
        path = self.root / asset['uri']; Image.new('RGB', (320, 180), 'red').save(path)
        code, value = invoke('ad', 'build', '--project', self.root, '--input', self.output)
        self.assertNotEqual(code, 0)
        self.assertEqual(value['errors'][0]['code'], 'AD_ASSET_CHANGED')
        self.assertEqual((self.root / 'project.json').read_bytes(), self.original)

    def test_existing_output_is_preserved(self):
        code, value = self.plan(); self.assertEqual(code, 0, value)
        before = self.output.read_bytes()
        code, value = self.plan(); self.assertNotEqual(code, 0)
        self.assertEqual(value['errors'][0]['code'], 'OUTPUT_EXISTS')
        self.assertEqual(self.output.read_bytes(), before)

    def test_caption_overflow_is_rejected_before_publishing_plan(self):
        self.brief['shots'][0]['text'] = ('word ' * 350).strip(); self.write(self.input, self.brief)
        code, value = self.plan(); self.assertNotEqual(code, 0, value)
        self.assertEqual(value['errors'][0]['code'], 'AD_CAPTION_OVERFLOW')
        self.assertFalse(self.output.exists())

    def test_cancellation_preserves_original_and_no_plan(self):
        marker = self.root / 'cancel'; marker.touch()
        code, value = self.plan('--cancel-file', marker)
        self.assertNotEqual(code, 0); self.assertEqual(value['errors'][0]['code'], 'CANCELLED')
        self.assertFalse(self.output.exists())
        self.assertEqual((self.root / 'project.json').read_bytes(), self.original)

    def test_commit_failure_rolls_back_project_snapshot_and_operations(self):
        code, value = self.plan(); self.assertEqual(code, 0, value)
        from ai_ad_editor.ad_storyboard_cli import save_project
        def fail_after_save(*args):
            save_project(*args)
            raise AppError('TEST_COMMIT_FAILURE', 'Test failure after real save', exit_code=6)
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for folder in ('history', 'operations') for p in (self.root / folder).rglob('*.json')}
        with patch('ai_ad_editor.ad_storyboard_cli.save_project', fail_after_save):
            code, value = invoke('ad', 'build', '--project', self.root, '--input', self.output)
        self.assertNotEqual(code, 0)
        self.assertEqual(value['errors'][0]['code'], 'TEST_COMMIT_FAILURE')
        self.assertEqual((self.root / 'project.json').read_bytes(), self.original)
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for folder in ('history', 'operations') for p in (self.root / folder).rglob('*.json')}
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main()
