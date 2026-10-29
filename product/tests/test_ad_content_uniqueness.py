"""Content-aware ad selection; these tests do not claim neural quality."""
import copy
import hashlib
import itertools
import random
import unittest

from ai_ad_editor import ad_selection as select
from ai_ad_editor.errors import AppError
from test_ad_selection import setup_request, hit, response


class ContentUniquenessTests(unittest.TestCase):
    def setUp(self):
        self.project, self.payload = setup_request()
        for asset in self.project['assets']:
            asset['sha256'] = 'sha256:'+hashlib.sha256(asset['id'].encode()).hexdigest()
        original = next(a for a in self.project['assets'] if a['id'] == 'picture')
        alias = copy.deepcopy(original)
        alias.update(id='picture_alias', uri='assets/copied-name.png', rights_ref='picture_alias')
        self.project['assets'].append(alias)

    def resolve(self, rows):
        prepared = select.prepare(self.project, self.payload)
        return select.resolve(self.project, prepared, response(prepared, rows))

    def test_default_uniqueness_rejects_distinct_ids_of_identical_content(self):
        with self.assertRaises(AppError):
            self.resolve([[hit(self.project, 'picture', .9)], [hit(self.project, 'picture_alias', .8)]])

    def test_global_content_assignment_avoids_alias_greedy_dead_end(self):
        plan, receipt = self.resolve([[hit(self.project, 'picture_alias', .99), hit(self.project, 'other', .8)],
                                      [hit(self.project, 'picture', .9)]])
        self.assertEqual([s['asset_id'] for s in receipt['selected']], ['other', 'picture'])
        self.assertTrue(receipt['unique_content'])
        self.assertEqual([s['asset_id'] for s in plan['request']['shots']], ['other', 'picture'])
        self.assertEqual(len({s['source_sha256'] for s in receipt['selected']}), 2)

    def test_explicit_shot_reserves_all_aliases_of_its_source_content(self):
        self.payload['brief']['shots'].append(dict(id='fixed', asset_id='picture'))
        plan, receipt = self.resolve([[hit(self.project, 'picture_alias', .99), hit(self.project, 'other', .8)],
                                      [hit(self.project, 'video', .7)]])
        self.assertEqual(plan['request']['shots'][0]['asset_id'], 'other')
        self.assertIn('reserved_content_by_explicit_shot', [r['reason'] for r in receipt['rejected']])

    def test_explicit_id_only_mode_preserves_original_distinct_id_behavior(self):
        self.payload['unique_content'] = False
        _, receipt = self.resolve([[hit(self.project, 'picture', .9)], [hit(self.project, 'picture_alias', .8)]])
        self.assertFalse(receipt['unique_content'])
        self.assertTrue(receipt['unique_assets'])

    def test_explicit_reuse_inherits_content_reuse_unless_overridden(self):
        self.payload['unique_assets'] = False
        _, receipt = self.resolve([[hit(self.project, 'picture', .9)], [hit(self.project, 'picture', .8)]])
        self.assertFalse(receipt['unique_content'])
        self.assertEqual([s['asset_id'] for s in receipt['selected']], ['picture', 'picture'])

    def test_explicit_content_policy_is_enforced_even_with_asset_reuse_enabled(self):
        self.payload.update(unique_assets=False, unique_content=True)
        with self.assertRaises(AppError):
            self.resolve([[hit(self.project, 'picture', .9)], [hit(self.project, 'picture_alias', .8)]])

    def test_content_flag_rejects_non_boolean_values_during_preflight(self):
        for value in [0, 1, None, 'true', [], {}]:
            with self.subTest(value=value):
                self.payload['unique_content'] = value
                with self.assertRaises(AppError):
                    select.prepare(self.project, self.payload)

    def test_same_content_keeps_best_usable_alias_and_exact_window(self):
        _, receipt = self.resolve([[hit(self.project, 'picture', .7, 100),
                                    hit(self.project, 'picture_alias', .9, 200)],
                                   [hit(self.project, 'other', .8)]])
        self.assertEqual(receipt['selected'][0]['asset_id'], 'picture_alias')
        self.assertEqual(receipt['selected'][0]['source_in_tick'], 200)

    def test_unverified_alias_cannot_replace_verified_representative(self):
        forbidden = hit(self.project, 'picture_alias', .99)
        forbidden['rights_verification_status'] = 'unverified'
        _, receipt = self.resolve([[forbidden, hit(self.project, 'picture', .8)],
                                   [hit(self.project, 'other', .7)]])
        self.assertEqual(receipt['selected'][0]['asset_id'], 'picture')
        self.assertIn('rights_not_verified', [r['reason'] for r in receipt['rejected']])

    def test_same_score_alias_ties_are_stable_across_response_order(self):
        first = [hit(self.project, 'picture_alias', .9, 0), hit(self.project, 'picture', .9, 100)]
        chosen = []
        for candidates in [first, list(reversed(first))]:
            _, receipt = self.resolve([candidates, [hit(self.project, 'other', .8)]])
            chosen.append((receipt['selected'][0]['asset_id'], receipt['selected'][0]['source_in_tick']))
        self.assertEqual(chosen, [('picture', 100), ('picture', 100)])

    def test_malformed_content_identity_is_not_an_asset_id_fallback(self):
        for asset in self.project['assets']:
            if asset['id'] == 'picture':
                asset['sha256'] = None
        with self.assertRaises(AppError):
            self.resolve([[hit(self.project, 'picture', .9)], [hit(self.project, 'other', .8)]])

    def test_random_alias_graphs_match_independent_exhaustive_content_oracle(self):
        rng = random.Random(58026)
        names = ['picture', 'picture_alias', 'other', 'video']
        groups = {a['id']: a['sha256'] for a in self.project['assets']}
        for _ in range(100):
            scores = [{aid: rng.randint(-100,100)/100 for aid in names if rng.random() > .3} for _ in range(2)]
            valid = [sum(round(scores[i][aid]*10**8) for i,aid in enumerate(assignment))
                for assignment in itertools.product(names, repeat=2)
                if groups[assignment[0]] != groups[assignment[1]]
                and all(aid in scores[i] for i,aid in enumerate(assignment))]
            candidates = [[hit(self.project, aid, score) for aid,score in row.items()] for row in scores]
            if not valid:
                with self.assertRaises(AppError):
                    self.resolve(candidates)
            else:
                _, receipt = self.resolve(candidates)
                chosen = [s['asset_id'] for s in receipt['selected']]
                self.assertNotEqual(groups[chosen[0]], groups[chosen[1]])
                self.assertEqual(sum(round(scores[i][aid]*10**8) for i,aid in enumerate(chosen)), max(valid))


if __name__ == '__main__':
    unittest.main()
