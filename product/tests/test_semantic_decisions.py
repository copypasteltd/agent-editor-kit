"""Contract/integrity tests only. Actual model quality has independent frozen receipts."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor import semantic, semantic_decision as decision
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import load_project
from ai_ad_editor.semantic_queries import compile_query, prepare, rank_clauses
import test_semantic as baseline


class QueryScopeTests(unittest.TestCase):
    def test_chinese_negation_splits_positive_and_excluded_concepts(self):
        plan = compile_query(dict(text='一只猫，不是一杯咖啡'))
        self.assertEqual(plan['include'], ['一只猫'])
        self.assertEqual(plan['exclude'], ['一杯咖啡'])

    def test_english_and_multiple_exclusions_keep_all_conditions(self):
        plan = compile_query(dict(text='a cat, not coffee, excluding gravel'))
        self.assertEqual(plan['include'], ['a cat'])
        self.assertEqual(plan['exclude'], ['coffee', 'gravel'])

    def test_unbounded_or_double_negation_requires_explicit_scope(self):
        for text in ('not a cat', '没有咖啡', '不是不喜欢猫', 'not only a cat', 'a cat that is not drinking'):
            with self.subTest(text=text):
                with self.assertRaises(AppError) as caught:
                    compile_query(dict(text=text))
                self.assertIn(caught.exception.code, ('ARGUMENT_INVALID', 'SEMANTIC_QUERY_SCOPE_REQUIRES_REVIEW'))

    def test_explicit_conjunction_preserves_display_text(self):
        value = dict(text='show this brief verbatim', include=['a cat', 'a chair'], exclude=['a coffee cup'])
        plan = compile_query(value)
        self.assertEqual(plan['original_text'], value['text'])
        self.assertEqual(plan['include'], value['include'])

    def test_contradictions_duplicates_and_invalid_clause_budgets_refuse(self):
        for include, exclude in [(['cat'], ['CAT']), (['cat', ' cat '], []), ([], []),
                                 (['cat'], ['']), (['cat']*9, []), ('cat', [])]:
            with self.subTest(include=include, exclude=exclude), self.assertRaises(AppError):
                compile_query(dict(text='brief', include=include, exclude=exclude))

    def test_batch_deduplicates_features_without_losing_query_mapping(self):
        plans, inputs = prepare([dict(id='a', text='a cat, not coffee'), dict(id='b', text='A CAT')])
        self.assertEqual(len(inputs), 2)
        self.assertEqual(plans[0]['include_rows'], plans[1]['include_rows'])


class DecisionMathTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(asset_id='cat', kind='image', sample_seconds=0),
                     dict(asset_id='coffee', kind='image', sample_seconds=0)]
        self.vectors = np.stack([baseline.basis(0), baseline.basis(1)])

    def test_negation_removes_the_forbidden_candidate(self):
        plans, _ = prepare([dict(text='a cat, not coffee')])
        hits = rank_clauses(self.vectors, self.vectors, self.rows, plans[0], limit=2)
        self.assertEqual([h['asset_id'] for h in hits], ['cat'])
        self.assertEqual(hits[0]['positive_scores'], [1.])
        self.assertEqual(hits[0]['exclusion_scores'], [0.])

    def test_all_positives_must_hold_on_the_same_frame(self):
        plans, _ = prepare([dict(text='both', include=['cat', 'coffee'])])
        self.assertEqual(rank_clauses(self.vectors, self.vectors, self.rows, plans[0], limit=2, cutoff=0), [])

    def test_threshold_comparison_is_strict_and_scores_are_not_probabilities(self):
        plans, _ = prepare([dict(text='cat')])
        self.assertEqual(rank_clauses(self.vectors, self.vectors[:1], self.rows, plans[0], limit=2, cutoff=1), [])
        hit = rank_clauses(self.vectors, self.vectors[:1], self.rows, plans[0], limit=2, cutoff=.5)[0]
        self.assertIn('not_probability', hit['score_kind'])
        self.assertTrue(hit['review_required'])

    @staticmethod
    def observations(positive=.8, negative=.2):
        return [dict(id=str(i), expected_asset_ids=['cat'] if i < 16 else [],
                     top_asset_id='cat', score=positive if i < 16 else negative) for i in range(32)]

    def test_calibration_separates_independent_positive_and_absent_labels(self):
        fitted = decision.fit(self.observations(), false_accept_rate=0)
        self.assertTrue(fitted['quality_gate_passed'])
        self.assertEqual(fitted['false_accepted_negatives'], 0)
        self.assertEqual(fitted['correct_positive_coverage'], 1)

    def test_indistinguishable_scores_fail_coverage_instead_of_publishing_reject_all(self):
        fitted = decision.fit(self.observations(.2, .2))
        self.assertFalse(fitted['quality_gate_passed'])
        self.assertEqual(fitted['correct_positive_coverage'], 0)

    def test_wrong_top_asset_does_not_count_as_correct_coverage(self):
        values = self.observations()
        for row in values[:16]: row['top_asset_id'] = 'wrong'
        self.assertFalse(decision.fit(values)['quality_gate_passed'])

    def test_nonfinite_and_boolean_controls_refuse(self):
        for controls in (dict(false_accept_rate=float('nan')), dict(false_accept_rate=True),
                         dict(minimum_coverage=.1), dict(minimum_coverage=float('inf'))):
            with self.subTest(controls=controls), self.assertRaises(AppError):
                decision.fit(self.observations(), **controls)


class CalibrationIntegrationTests(unittest.TestCase):
    def setUp(self):
        baseline.SemanticIndexIntegrityTests.setUp(self)
        baseline.SemanticIndexIntegrityTests.build(self)
        self.embedding.stop()
        self.source_data = self.base/'calibration.json'
        self.truth = dict(format=decision.DATASET_FORMAT, scope='Synthetic contract fixture, not model quality.',
            queries=[dict(id='q'+str(i), text=('visual ' if i < 16 else 'unrelated ')+str(i),
                          expected_asset_ids=['asset_visual'] if i < 16 else []) for i in range(32)])
        self.source_data.write_text(json.dumps(self.truth), encoding='utf-8')
        self.infer = patch.object(semantic, 'embed', side_effect=lambda root, adapter, items, task, **kwargs:
            (np.stack([baseline.basis(0 if v['text'].startswith('visual') else 1) for v in items]),
             dict(response=dict(device='cpu', device_index=0), contract_test_stub=True)))
        self.infer.start(); self.addCleanup(self.infer.stop)

    def calibrate(self, **kwargs):
        result = decision.calibrate(self.root, self.project, index_id='index', calibration_id='accept',
            input_path=str(self.source_data), device='cpu', **kwargs)
        self.project = load_project(self.root)[1]
        return result

    def test_registered_profile_returns_empty_for_absent_subject_and_preserves_project(self):
        result = self.calibrate()
        self.assertEqual(result['profile']['fit']['correct_positive_coverage'], 1)
        before = {n:(self.root/n).read_bytes() for n in ('project.json', 'rights-ledger.json')}
        good = semantic.search(self.root, self.project, index_id='index', query='visual subject',
            calibration_id='accept', device='cpu')
        empty = semantic.search(self.root, self.project, index_id='index', query='unrelated subject',
            calibration_id='accept', device='cpu')
        self.assertEqual(good['results'][0]['decision'], 'calibrated_match')
        self.assertEqual(empty['results'][0]['hits'], [])
        self.assertEqual(empty['results'][0]['decision'], 'no_calibrated_match')
        self.assertEqual(before, {n:(self.root/n).read_bytes() for n in before})

    def test_profile_tampering_is_rejected_before_inference(self):
        result = self.calibrate()
        asset = next(a for a in self.project['assets'] if a['id'] == result['calibration']['asset_id'])
        path = self.root/asset['uri']; path.write_bytes(path.read_bytes()+b' ')
        with patch.object(semantic, 'embed', side_effect=AssertionError('must not infer')), self.assertRaises(AppError):
            semantic.search(self.root, self.project, index_id='index', query='visual subject', calibration_id='accept')

    def test_dataset_copy_tampering_is_rejected(self):
        result = self.calibrate()
        asset = next(a for a in self.project['assets'] if a['id'] == result['calibration']['dataset_asset_id'])
        path = self.root/asset['uri']; path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(AppError):
            semantic.search(self.root, self.project, index_id='index', query='visual', calibration_id='accept')

    def test_mismatched_filter_raw_mode_or_image_query_refuses(self):
        self.calibrate()
        for options in (dict(kind='image'), dict(query_mode='raw')):
            with self.subTest(options=options), self.assertRaises(AppError):
                semantic.search(self.root, self.project, index_id='index', query='visual',
                    calibration_id='accept', **options)
        with self.assertRaises(AppError):
            semantic.search(self.root, self.project, index_id='index', image=str(self.source), calibration_id='accept')

    def test_cpu_profile_does_not_silently_apply_to_cuda(self):
        self.calibrate()
        with (patch.object(semantic, 'embed', return_value=(baseline.basis()[None],
                dict(response=dict(device='cuda', device_index=0)))), self.assertRaises(AppError) as caught):
            semantic.search(self.root, self.project, index_id='index', query='visual', calibration_id='accept')
        self.assertEqual(caught.exception.code, 'SEMANTIC_CALIBRATION_DEVICE_MISMATCH')

    def test_dry_run_never_creates_profile_or_runs_model(self):
        before = (self.root/'project.json').read_bytes()
        with patch.object(semantic, 'embed', side_effect=AssertionError('must not infer')):
            result = self.calibrate(dry_run=True)
        self.assertEqual(result['model_forward_calls'], 0)
        self.assertEqual(before, (self.root/'project.json').read_bytes())

    def test_insufficient_or_duplicate_calibration_queries_refuse(self):
        for changes in ('short', 'duplicate', 'unknown_asset'):
            value = json.loads(json.dumps(self.truth))
            if changes == 'short': value['queries'] = value['queries'][:31]
            if changes == 'duplicate': value['queries'][1]['text'] = value['queries'][0]['text']
            if changes == 'unknown_asset': value['queries'][0]['expected_asset_ids'] = ['missing']
            self.source_data.write_text(json.dumps(value), encoding='utf-8')
            with self.subTest(changes=changes), self.assertRaises(AppError): self.calibrate()

    def test_quality_failure_preserves_metadata_and_never_registers_profile(self):
        before = {n:(self.root/n).read_bytes() for n in ('project.json', 'rights-ledger.json')}
        with (patch.object(semantic, 'embed', return_value=(np.tile(baseline.basis(), (32,1)),
                dict(response=dict(device='cpu', device_index=0)))), self.assertRaises(AppError) as caught):
            self.calibrate()
        self.assertEqual(caught.exception.code, 'SEMANTIC_CALIBRATION_QUALITY_FAILED')
        self.assertEqual(before, {n:(self.root/n).read_bytes() for n in before})
        self.assertFalse((self.root/'assets/semantic-calibration').exists())

    def test_cli_transaction_restores_metadata_after_ledger_save_failure(self):
        before = {n:(self.root/n).read_bytes() for n in ('project.json', 'rights-ledger.json')}
        stream = io.StringIO()
        with (patch.object(decision, 'save_ledger', side_effect=OSError('injected write failure')),
              contextlib.redirect_stdout(stream)):
            code = main(['semantic','calibrate','--project',str(self.root),'--index-id','index',
                '--calibration-id','accept','--input',str(self.source_data),'--device','cpu'])
        self.assertNotEqual(code, 0)
        self.assertEqual(before, {n:(self.root/n).read_bytes() for n in before})
        self.assertFalse(any((self.root/'assets/semantic-calibration').glob('*/profile.json')))

    def test_cancel_marker_stops_before_inference_or_publication(self):
        marker = self.root/'stop'; marker.touch()
        with patch.object(semantic, 'embed', side_effect=AssertionError('must not infer')), self.assertRaises(AppError):
            self.calibrate(cancel_file=str(marker))


if __name__ == '__main__':
    unittest.main()
