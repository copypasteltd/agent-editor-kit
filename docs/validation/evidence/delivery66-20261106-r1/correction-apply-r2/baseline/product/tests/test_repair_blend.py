"""Independent analytic and preservation checks for the numerical kernel."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from ai_ad_editor.repair_blend import harmonize_region


class HarmonizeTests(unittest.TestCase):
    def plane(self):
        y, x = np.indices((24, 32))
        rgb = np.stack([20+x+y, 50+2*x+y, 100+x-y], axis=2).astype(np.uint8)
        rgba = np.concatenate([rgb, (x*7 % 256).astype(np.uint8)[:, :, None]], axis=2)
        mask = np.zeros((24, 32), bool); mask[5:19, 7:25] = True
        return rgba, rgb.astype(np.float32), mask

    def test_constant_bias_on_a_plane_recovers_independent_truth(self):
        source, truth, mask = self.plane(); prediction = truth + [25., -20., 10.]
        prediction = prediction.astype(np.float32); source[mask, :3] = [255, 0, 0]
        corrected, metrics = harmonize_region(source, prediction, mask)
        np.testing.assert_allclose(corrected[mask], truth[mask], atol=.002)
        np.testing.assert_array_equal(corrected[~mask], prediction[~mask])
        self.assertTrue(all(x > 0 for x in metrics['iterations']))

    def test_compact_model_texture_survives_low_frequency_correction(self):
        source, truth, mask = self.plane(); wanted = truth.copy(); wanted[9:14, 12:17, 0] += 5
        prediction = (wanted + [25., -20., 10.]).astype(np.float32)
        corrected, _ = harmonize_region(source, prediction, mask)
        np.testing.assert_allclose(corrected[mask], wanted[mask], atol=.002)

    def test_selected_source_colors_and_alpha_cannot_influence_repair(self):
        source, truth, mask = self.plane(); prediction = (truth + 20).astype(np.float32)
        first, _ = harmonize_region(source, prediction, mask)
        source[mask, :3] = [255, 0, 255]; source[:, :, 3] = 0
        second, _ = harmonize_region(source, prediction, mask)
        np.testing.assert_array_equal(first, second)

    def test_disconnected_and_canvas_edge_regions_recover_a_plane(self):
        source, truth, _ = self.plane(); mask = np.zeros((24, 32), bool)
        mask[:5, :7] = True; mask[12:19, 17:25] = True
        corrected, _ = harmonize_region(source, (truth + 20).astype(np.float32), mask)
        np.testing.assert_allclose(corrected[mask], truth[mask], atol=.003)

    def test_matching_plane_is_stable_and_does_not_mutate_inputs(self):
        source, truth, mask = self.plane(); before_source = source.copy(); before_truth = truth.copy()
        corrected, metrics = harmonize_region(source, truth, mask)
        np.testing.assert_array_equal(corrected, truth)
        np.testing.assert_array_equal(source, before_source); np.testing.assert_array_equal(truth, before_truth)
        self.assertEqual(metrics['max_abs_correction'], 0.)

    def test_empty_selection_bypasses_and_full_selection_has_no_boundary(self):
        source, truth, mask = self.plane(); mask[:] = False
        corrected, metrics = harmonize_region(source, truth, mask, array_budget=1)
        np.testing.assert_array_equal(corrected, truth); self.assertEqual(metrics['owned_array_budget_bytes'], 0)
        mask[:] = True
        with self.assertRaisesRegex(ValueError, 'NO_BOUNDARY'): harmonize_region(source, truth, mask)

    def test_budget_and_nonconvergence_fail_without_changing_inputs(self):
        source, truth, mask = self.plane(); before_source = source.copy(); before_truth = truth.copy()
        with self.assertRaisesRegex(ValueError, 'BUDGET_EXCEEDED'): harmonize_region(source, truth, mask, array_budget=1)
        rng = np.random.default_rng(42); source[~mask, :3] = rng.integers(0, 256, (int((~mask).sum()), 3), dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, 'NOT_CONVERGED'): harmonize_region(source, truth, mask, max_iterations=1)
        np.testing.assert_array_equal(truth, before_truth)
        source[~mask] = before_source[~mask]; np.testing.assert_array_equal(source, before_source)

    def test_fractional_model_detail_is_kept_until_final_quantization(self):
        source = np.full((9, 9, 4), 100, np.uint8); prediction = np.full((9, 9, 3), 110, np.float32)
        mask = np.zeros((9, 9), bool); mask[2:7, 2:7] = True; prediction[4, 4] += .25
        corrected, _ = harmonize_region(source, prediction, mask)
        self.assertEqual(corrected.dtype, np.float32); np.testing.assert_allclose(corrected[4, 4], 100.25, atol=.001)

    def test_cancellation_checkpoint_during_solver_preserves_all_inputs(self):
        source,truth,mask=self.plane();prediction=(truth+20).astype(np.float32)
        before_source=source.copy();before_prediction=prediction.copy();calls=[]
        def cancel():
            calls.append(True)
            if len(calls)==2:raise InterruptedError('controlled cancellation during solver')
        with self.assertRaisesRegex(InterruptedError,'during solver'):
            harmonize_region(source,prediction,mask,checkpoint=cancel)
        self.assertEqual(len(calls),2)
        np.testing.assert_array_equal(source,before_source);np.testing.assert_array_equal(prediction,before_prediction)

    def test_cli_planning_and_report_validation_do_not_require_host_numpy(self):
        import subprocess
        code="""
import sys,importlib.abc
sys.path.insert(0,PRODUCT_SOURCE)
class Block(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname=='numpy' or fullname.startswith('numpy.'):raise ModuleNotFoundError('NumPy deliberately unavailable in host')
sys.meta_path.insert(0,Block())
from ai_ad_editor.cli import build_parser
from ai_ad_editor.local_inpainting import normalize_options
from ai_ad_editor.repair_blend import blend_budget_plan,new_blend_report,validate_blend_report
build_parser()
for mode in ['direct','harmonic']:
 options=normalize_options(blend_mode=mode)
 plan=blend_budget_plan(64,48,options,512*1024**2)
 assert plan['mode']==mode
 validate_blend_report({'empty_mask_frames':8,'mask_pixels':0,'blend':new_blend_report(options)},options,width=64,height=48,frames=8)
assert 'numpy' not in sys.modules
print('host planning without numpy succeeded')
""".replace('PRODUCT_SOURCE',repr(str(Path(__file__).resolve().parents[1]/'src')))
        result=subprocess.run([sys.executable,'-I','-B','-X','utf8','-c',code],capture_output=True,text=True,encoding='utf-8',timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('without numpy succeeded',result.stdout)

    def test_invalid_shapes_types_and_nonfinite_values_are_rejected(self):
        source, truth, mask = self.plane()
        for options in [{'max_iterations': True}, {'relative_tolerance': float('nan')}, {'array_budget': 0}]:
            with self.subTest(options=options), self.assertRaises(ValueError): harmonize_region(source, truth, mask, **options)
        for value in [truth.astype(np.float64), truth[:, :-1], np.full_like(truth, np.nan)]:
            with self.assertRaises(ValueError): harmonize_region(source, value, mask)
        with self.assertRaises(ValueError): harmonize_region(source, truth, mask.astype(np.uint8))


if __name__ == '__main__': unittest.main()
