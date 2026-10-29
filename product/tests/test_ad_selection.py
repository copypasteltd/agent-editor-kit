import copy
import itertools
import json
import random
import unittest
import contextlib
import io
from pathlib import Path
import tempfile
from unittest.mock import patch

from ai_ad_editor import ad_selection as select, ad_storyboard as storyboard
from ai_ad_editor.errors import AppError
from test_ad_storyboard import fixture


def setup_request():
    project, brief = fixture()
    brief['shots'] = brief['shots'][:2]
    brief['variants'] = brief['variants'][:2]
    for shot in brief['shots']:
        del shot['asset_id']
    payload = dict(brief=brief, queries=[dict(id=s['id'], text='Visual ' + s['id']) for s in brief['shots']])
    return project, payload


def hit(project, aid, score, start=0, **changes):
    asset = next(a for a in project['assets'] if a['id'] == aid)
    return dict(asset_id=aid, source_sha256=asset['sha256'], decision_score=score,
                editable_reference=dict(asset_id=aid, source_in_tick=start, point_sample_only=True),
                rights_verification_status='verified', preview_asset_id='preview-' + aid, **changes)


def response(prepared, candidates):
    return dict(task='text', query_mode='clauses', calibration_id='cal-cuda', index_id='visuals',
                network='disabled', results=[dict(query=q, calibration_id='cal-cuda',
                decision='calibrated_match', hits=hits) for q, hits in zip(prepared['queries'], candidates)])


class AssignmentTests(unittest.TestCase):
    def test_global_assignment_avoids_greedy_dead_end(self):
        self.assertEqual(select.maximum_assignment([{'a': .9, 'b': .8}, {'a': .85}]), ['b', 'a'])

    def test_hall_conflict_is_rejected_even_with_enough_total_assets(self):
        with self.assertRaises(AppError):
            select.maximum_assignment([{'a': .9}, {'a': .8}, {'b': .7, 'c': .6}])

    def test_reuse_requires_explicit_policy(self):
        self.assertEqual(select.maximum_assignment([{'a': .9}, {'a': .8}], unique=False), ['a', 'a'])
        with self.assertRaises(AppError):
            select.maximum_assignment([{'a': .9}, {'a': .8}])

    def test_random_graphs_match_exhaustive_independent_oracle(self):
        rng = random.Random(3054)
        for _ in range(100):
            rows = [{a: rng.randint(-100, 100)/100 for a in 'abcd' if rng.random() > .3} for _ in range(3)]
            possibilities = [sum(round(rows[i][a]*10**8) for i, a in enumerate(p))
                             for p in itertools.permutations('abcd', 3)
                             if all(a in rows[i] for i, a in enumerate(p))]
            if not possibilities:
                with self.assertRaises(AppError):
                    select.maximum_assignment(rows)
            else:
                chosen = select.maximum_assignment(rows)
                self.assertEqual(sum(round(rows[i][a]*10**8) for i, a in enumerate(chosen)), max(possibilities))


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.project, self.payload = setup_request()
        self.prepared = select.prepare(self.project, self.payload)

    def resolve(self, candidates):
        return select.resolve(self.project, self.prepared, response(self.prepared, candidates))

    def test_real_storyboard_contract_replay_and_source_immutability(self):
        before = copy.deepcopy(self.project)
        plan, receipt = self.resolve([[hit(self.project, 'picture', .9), hit(self.project, 'other', .8)],
                                      [hit(self.project, 'picture', .85)]])
        candidate = storyboard.apply_plan(self.project, plan)
        self.assertEqual(self.project, before)
        self.assertEqual(len(candidate['sequences']), len(self.project['sequences']) + 2)
        self.assertEqual([r['asset_id'] for r in receipt['selected']], ['other', 'picture'])
        rationale = json.loads(plan['request']['shots'][0]['rationale'])
        self.assertEqual(rationale['selection']['query'], self.payload['queries'][0])
        self.assertFalse(rationale['selection']['semantic_truth_verified'])

    def test_all_variants_bound_video_duration_and_keep_exact_sample_tick(self):
        self.project['assets'].append(dict(id='long', kind='video', sha256='sha256:'+'2'*64,
                                          probe={'duration_tick': 1800000}))
        plan, receipt = self.resolve([[hit(self.project, 'video', .99, 850000), hit(self.project, 'long', .8, 90000)],
                                     [hit(self.project, 'picture', .9)]])
        self.assertEqual(plan['request']['shots'][0]['asset_id'], 'long')
        self.assertEqual(plan['request']['shots'][0]['source_in_tick'], 90000)
        self.assertEqual(receipt['rejected'][0]['reason'], 'source_too_short')

    def test_unverified_rights_never_auto_selected(self):
        candidate = hit(self.project, 'picture', .99); candidate['rights_verification_status'] = 'unverified'
        plan, receipt = self.resolve([[candidate, hit(self.project, 'other', .8)], [hit(self.project, 'video', .7)]])
        self.assertEqual(plan['request']['shots'][0]['asset_id'], 'other')
        self.assertEqual(receipt['rejected'][0]['reason'], 'rights_not_verified')

    def test_source_hash_change_is_hard_failure(self):
        candidate = hit(self.project, 'picture', .9); candidate['source_sha256'] = 'sha256:'+'f'*64
        with self.assertRaises(AppError):
            self.resolve([[candidate], [hit(self.project, 'other', .8)]])

    def test_no_calibrated_match_is_not_silently_promoted(self):
        data = response(self.prepared, [[hit(self.project, 'picture', .9)], [hit(self.project, 'other', .8)]])
        data['results'][0]['decision'] = 'candidates_require_review'
        with self.assertRaises(AppError):
            select.resolve(self.project, self.prepared, data)

    def test_query_and_profile_binding_must_match(self):
        for field, value in [('query', {'id': 'hook', 'text': 'changed'}), ('calibration_id', 'other')]:
            data = response(self.prepared, [[hit(self.project, 'picture', .9)], [hit(self.project, 'other', .8)]])
            data['results'][0][field] = value
            with self.assertRaises(AppError):
                select.resolve(self.project, self.prepared, data)

    def test_nonfinite_scores_and_invalid_ticks_rejected(self):
        for field, value in [('decision_score', float('nan')), ('decision_score', True)]:
            candidate = hit(self.project, 'picture', .9); candidate[field] = value
            with self.assertRaises(AppError):
                self.resolve([[candidate], [hit(self.project, 'other', .8)]])
        candidate = hit(self.project, 'picture', .9, start=True)
        with self.assertRaises(AppError):
            self.resolve([[candidate], [hit(self.project, 'other', .8)]])

    def test_variant_asset_override_cannot_bypass_query(self):
        self.payload['brief']['variants'][0]['overrides'] = {'hook': {'asset_id': 'picture'}}
        with self.assertRaises(AppError):
            select.prepare(self.project, self.payload)

    def test_query_shot_cannot_also_pin_an_asset(self):
        self.payload['brief']['shots'][0]['asset_id'] = 'picture'
        with self.assertRaises(AppError):
            select.prepare(self.project, self.payload)

    def test_source_audio_must_exist_on_selected_asset(self):
        self.payload['brief']['shots'][0]['include_source_audio'] = True
        self.prepared = select.prepare(self.project, self.payload)
        plan, receipt = self.resolve([[hit(self.project, 'picture', .99), hit(self.project, 'video', .8)],
                                     [hit(self.project, 'other', .9)]])
        self.assertEqual(plan['request']['shots'][0]['asset_id'], 'video')
        self.assertEqual(receipt['rejected'][0]['reason'], 'source_audio_missing')

    def test_explicit_shot_reserves_its_asset(self):
        self.payload['brief']['shots'].append({'id': 'fixed', 'asset_id': 'picture'})
        self.prepared = select.prepare(self.project, self.payload)
        plan, receipt = self.resolve([[hit(self.project, 'picture', .99), hit(self.project, 'other', .8)],
                                     [hit(self.project, 'video', .7)]])
        self.assertEqual(plan['request']['shots'][0]['asset_id'], 'other')
        self.assertEqual(receipt['rejected'][0]['reason'], 'reserved_by_explicit_shot')


class SelectionCliTests(unittest.TestCase):
    def setUp(self):
        from ai_ad_editor.cli import main
        from PIL import Image
        import ai_ad_editor
        self.main = main
        scratch = Path(__file__).resolve().parents[2] / 'local/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch, prefix='ad-select-')
        self.root = Path(self.temp.name) / 'project'
        self.invoke('project', 'init', self.root, '--project-id', 'selection_cli')
        for aid, color in [('picture', 'navy'), ('other', 'teal')]:
            image = Path(self.temp.name) / (aid + '.png')
            Image.new('RGB', (320, 180), color).save(image)
            self.invoke('media', 'ingest', '--project', self.root, '--input', image, '--asset-id', aid)
        font = Path(ai_ad_editor.__file__).parent / 'material_data/fonts/noto-sans-sc-variable.ttf'
        self.invoke('media', 'ingest', '--project', self.root, '--input', font, '--asset-id', 'font')
        self.payload = setup_request()[1]
        self.input, self.output = self.root / 'request.json', self.root / 'validation/selected.json'
        self.input.write_text(json.dumps(self.payload), encoding='utf-8')
        self.before = (self.root / 'project.json').read_bytes()

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, *args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = self.main(list(map(str, args)))
        return code, json.loads(stream.getvalue())

    def select(self, *extra):
        return self.invoke('ad', 'select', '--project', self.root, '--input', self.input,
            '--output', self.output, '--index-id', 'index', '--calibration-id', 'cal-cuda', *extra)

    def test_cli_service_result_becomes_actual_buildable_plan(self):
        from ai_ad_editor.project import load_project
        project = load_project(self.root)[1]
        prepared = select.prepare(project, self.payload)
        data = response(prepared, [[hit(project, 'picture', .8)], [hit(project, 'other', .9)]])
        with patch('ai_ad_editor.semantic.search', return_value=data) as service:
            code, result = self.select()
        self.assertEqual(code, 0, result)
        self.assertFalse(service.call_args.kwargs['distinct_assets'])
        self.assertEqual((self.root / 'project.json').read_bytes(), self.before)
        self.assertTrue(self.output.is_file())
        code, result = self.invoke('ad', 'build', '--project', self.root, '--input', self.output)
        self.assertEqual(code, 0, result)

    def test_existing_output_refuses_before_service(self):
        self.output.write_text('preserve', encoding='utf-8')
        with patch('ai_ad_editor.semantic.search') as service:
            code, result = self.select()
        self.assertNotEqual(code, 0)
        service.assert_not_called()
        self.assertEqual(self.output.read_text('utf-8'), 'preserve')

    def test_preflight_dry_run_never_claims_a_selected_plan(self):
        with patch('ai_ad_editor.semantic.search', return_value={'model_forward_calls': 0}) as service:
            code, result = self.select('--dry-run')
        self.assertEqual(code, 0, result)
        self.assertTrue(service.call_args.kwargs['dry_run'])
        self.assertIsNone(result['data']['plan'])
        self.assertFalse(self.output.exists())
        self.assertEqual((self.root / 'project.json').read_bytes(), self.before)

    def test_invalid_brief_never_invokes_service_or_publishes(self):
        self.payload['brief']['shots'][0]['asset_id'] = 'picture'
        self.input.write_text(json.dumps(self.payload), encoding='utf-8')
        with patch('ai_ad_editor.semantic.search') as service:
            code, result = self.select()
        self.assertNotEqual(code, 0)
        service.assert_not_called()
        self.assertFalse(self.output.exists())
        self.assertEqual((self.root / 'project.json').read_bytes(), self.before)


if __name__ == '__main__':
    unittest.main()
