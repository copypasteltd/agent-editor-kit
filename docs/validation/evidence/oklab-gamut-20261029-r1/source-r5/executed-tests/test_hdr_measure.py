"""Independent light oracles plus real native timeline/CLI/early-frame regressions."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor import hdr_measure, float_bundle
from ai_ad_editor.colour_audit import ColourAudit
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_hdr import LuminanceSignal
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.project import save_project
import test_float_standard_render as fixture

RECEIPTS = []
LINEAR = LuminanceSignal('bt2020', 'linear', 100)


def rgba(rows):
    return np.array([[list(v) + [1.] for v in rows]], np.float32)


class LightUnitTests(unittest.TestCase):
    def test_maxRGB_and_CIE_Y_differ_for_saturated_colors(self):
        meter = hdr_measure.LightMeter(LINEAR, 2, 1)
        source = rgba([[1, 0, 0], [0, 0, 1]])
        meter.add(0, source, Fraction(1, 24)); result = meter.result()
        # Independent published BT2020/D65 luma row, not product matrix helpers.
        self.assertAlmostEqual(result['peak_pixel']['maxrgb']['nits'], 100)
        self.assertAlmostEqual(result['peak_pixel']['cie_y']['nits'], 26.2700212, places=5)
        self.assertAlmostEqual(result['maximum_frame_average']['maxrgb']['nits'], 100)
        self.assertAlmostEqual(result['maximum_frame_average']['cie_y']['nits'], 16.1000964, places=5)
        self.assertEqual(result['peak_pixel']['maxrgb']['x'], 0)
        self.assertFalse(result['codec_output_measured']); self.assertFalse(result['automatically_written_SEI'])

    def test_early_peak_and_bright_average_are_not_last_frame_values(self):
        meter = hdr_measure.LightMeter(LINEAR, 2, 1)
        meter.add(4, rgba([[1, 0, 0], [0, 0, 0]]), Fraction(1, 10))
        meter.add(5, rgba([[.75]*3, [.75]*3]), Fraction(1, 10))
        meter.add(6, rgba([[0]*3, [0]*3]), Fraction(1, 20))
        r = meter.result(); self.assertEqual(r['peak_pixel']['maxrgb']['frame'], 4)
        self.assertEqual(r['maximum_frame_average']['maxrgb']['frame'], 5)
        self.assertEqual(r['analyzed_duration_seconds'], '1/4')
        q = round(.75 * 65535) / 65535 * 100
        self.assertAlmostEqual(r['duration_weighted_frame_average_nits']['maxrgb'], (50*.1+q*.1)/.25, places=10)
        self.assertEqual(r['frames'], 3)

    def test_PQ_float64_decode_matches_independent_decimal_oracle(self):
        from test_float_hdr import pq_decimal
        signal = LuminanceSignal('bt2020', 'pq-st2084', 203)
        source = rgba([[v]*3 for v in (.01, .1, .5, .75, 1.)])
        meter = hdr_measure.LightMeter(signal, 5, 1); meter.add(0, source, Fraction(1, 25)); r = meter.result()
        values = [pq_decimal(float(round(float(v)*65535)/65535)) for v in source[0,:,0]]
        self.assertAlmostEqual(r['peak_pixel']['maxrgb']['nits'], max(values), delta=1e-7)
        self.assertAlmostEqual(r['maximum_frame_average']['maxrgb']['nits'], sum(values)/5, delta=1e-7)
        RECEIPTS.append(dict(test=self.id(), measured=r, independent_decimal_nits=values))

    def test_HLG_coupled_decode_black_and_peak_follow_explicit_display(self):
        from ai_ad_editor.float_hlg_black import HLGBlackSignal
        signal = HLGBlackSignal('bt2020','hlg-bt2100',203,1000,1.2,1)
        meter = hdr_measure.LightMeter(signal, 2, 1)
        meter.add(0, rgba([[0]*3,[1]*3]), Fraction(1, 10)); r=meter.result()
        self.assertAlmostEqual(r['minimum_RGB_component_nits'],1,places=5)
        self.assertAlmostEqual(r['peak_pixel']['maxrgb']['nits'],1000,places=4)
        self.assertAlmostEqual(r['maximum_frame_average']['maxrgb']['nits'],500.5,places=4)

    def test_explicit_active_region_preserves_canvas_coordinates(self):
        source = np.zeros((3,4,4),np.float32); source[...,3]=1
        source[0,0,:3]=1; source[2,3,:3]=.5
        meter=hdr_measure.LightMeter(LINEAR,4,3,region=[2,1,2,2]); meter.add(2,source,Fraction(1,10));r=meter.result()
        self.assertEqual((r['peak_pixel']['maxrgb']['x'],r['peak_pixel']['maxrgb']['y']),(3,2))
        self.assertLess(r['peak_pixel']['maxrgb']['nits'],51)
        self.assertEqual(r['active_pixels_per_frame'],4)

    def test_quantization_and_explicit_clip_match_integer_delivery(self):
        source=rgba([[1.2,-.1,.5]])
        with self.assertRaises(AppError):hdr_measure.LightMeter(LINEAR,1,1).add(0,source,Fraction(1,10))
        meter=hdr_measure.LightMeter(LINEAR,1,1);meter.add(0,source,Fraction(1,10),range_policy='clip')
        self.assertEqual(meter.result()['peak_pixel']['maxrgb']['nits'],100)
        self.assertEqual(meter.result()['minimum_RGB_component_nits'],0)

    def test_rejects_relative_units_invalid_regions_dimensions_and_empty_results(self):
        for signal,w,h,region in [(ColorSignal('bt2020','linear'),1,1,None),(LINEAR,0,1,None),
                (LINEAR,4,2,[0,0,5,2]),(LINEAR,4,2,[True,0,1,1]),(LINEAR,4,2,[-1,0,1,1])]:
            with self.subTest(region=region),self.assertRaises(AppError):hdr_measure.LightMeter(signal,w,h,region=region)
        with self.assertRaises(AppError):hdr_measure.LightMeter(LINEAR,1,1).result()

    def test_invalid_clock_nonfinite_alpha_and_layout_fail_closed(self):
        for bad in [rgba([[0]*3]).astype(np.float64),rgba([[float('nan')]*3]),rgba([[float('inf')]*3])]:
            with self.subTest(dtype=bad.dtype),self.assertRaises(AppError):hdr_measure.LightMeter(LINEAR,1,1).add(0,bad,Fraction(1,10))
        for alpha in (0,.5,1.01):
            bad=rgba([[0]*3]);bad[...,3]=alpha
            with self.assertRaises(AppError):hdr_measure.LightMeter(LINEAR,1,1).add(0,bad,Fraction(1,10))
        meter=hdr_measure.LightMeter(LINEAR,1,1);meter.add(0,rgba([[0]*3]),Fraction(1,10))
        with self.assertRaises(AppError):meter.add(2,rgba([[0]*3]),Fraction(1,10))
        with self.assertRaises(AppError):hdr_measure.LightMeter(LINEAR,1,1).add(0,rgba([[0]*3]),Fraction(0))

    def test_cancel_and_source_immutability(self):
        source=rgba([[.5]*3]);before=source.tobytes()
        def cancel():raise AppError('CANCELLED','test',exit_code=8)
        with self.assertRaises(AppError):hdr_measure.LightMeter(LINEAR,1,1,cancel=cancel).add(0,source,Fraction(1,10))
        self.assertEqual(source.tobytes(),before)

    def test_all_frame_colour_totals_peak_and_ordered_hash(self):
        audit=ColourAudit()
        audit.add(2,dict(hdr_output_components_clipped=23));audit.add(3,dict(hdr_input_components_clipped=4));audit.add(4,{})
        r=audit.result();self.assertEqual(r['frames'],3);self.assertEqual(r['totals']['hdr_output_components_clipped'],23)
        self.assertEqual(r['first_affected_frame'],2);self.assertEqual(r['last_affected_frame'],3)
        self.assertEqual(r['frames_with_counted_events'],2)
        other=ColourAudit();other.add(2,{});other.add(3,dict(hdr_input_components_clipped=4));other.add(4,dict(hdr_output_components_clipped=23))
        self.assertEqual(other.result()['totals'],r['totals']);self.assertNotEqual(other.result()['framed_receipts_sha256'],r['framed_receipts_sha256'])

    def test_colour_ledger_rejects_invalid_counter_and_noncontiguous_frames(self):
        for value in (-1,True,1.5):
            with self.assertRaises(ValueError):ColourAudit().add(0,dict(hdr_input_components_clipped=value))
        audit=ColourAudit();audit.add(0,{})
        with self.assertRaises(ValueError):audit.add(2,{})


class LightIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.FloatStandardRenderTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;f.s['duration_tick']=22500 # 2.5 CFR frames; last frame's authored duration is 1/20 s.
        values=np.zeros((3,16,32,4),np.float32);values[...,3]=1;values[0,...,:3]=[.9,.1,.2];values[1,...,:3]=.5
        f.visual(values);f.p['settings']['color'].update(primaries='bt2020',transfer='smpte2084',matrix='bt2020nc')
        pipeline=f.p['settings']['pixel_pipeline'];pipeline.update(working_signal=vars(LINEAR),output_signal=vars(LuminanceSignal('bt2020','pq-st2084',203)))
        pipeline['sources']['picture']['source_signal']=vars(LINEAR)
        save_project(f.root,f.p)

    def plan(self,**kw):return hdr_measure.prepare(self.f.p,self.f.s['id'],**kw)

    def test_real_CLI_readonly_all_frames_and_dryrun_without_decode(self):
        f=self.f;before=(f.root/'project.json').read_bytes();args=['surface','measure','--project',f.root,'--sequence-id',f.s['id']]
        with patch('ai_ad_editor.float_standard_render.FloatRenderContext.__enter__',side_effect=AssertionError('dry-run decoded')):
            code,r=f.invoke(*args,'--dry-run');self.assertEqual(code,0,r);self.assertEqual(r['status'],'planned')
        code,r=f.invoke(*args);self.assertEqual(code,0,r);data=r['data']
        self.assertTrue(data['all_timeline_frames_measured']);self.assertTrue(data['full_canvas_measured'])
        self.assertEqual(data['frames'],3);self.assertEqual(data['analyzed_duration_seconds'],'1/4')
        self.assertEqual(data['peak_pixel']['maxrgb']['frame'],0);self.assertEqual(data['maximum_frame_average']['cie_y']['frame'],1)
        self.assertTrue(data['timeline']['providers_closed_before_publish']);self.assertEqual(before,(f.root/'project.json').read_bytes())
        RECEIPTS.append(dict(test=self.id(),response=r))

    def test_same_common_encoder_RGB16_digest_as_actual_render(self):
        f=self.f;measurement=hdr_measure.measure(f.root,f.p,self.plan());result=f.execute('meter-match.mkv')
        transport=result['delivery']['pixel_pipeline']['transport']
        self.assertEqual(measurement['encoder_RGB16_input_sha256'],transport['video_input_sha256'])
        self.assertEqual(measurement['encoder_RGBA16_input_bytes'],transport['video_input_bytes'])
        self.assertEqual(result['delivery']['pixel_pipeline']['colour_boundary_all_frames']['frames'],3)
        RECEIPTS.append(dict(test=self.id(),measurement=measurement,render=result))

    def test_real_display_map_and_native_proof_match_common_render_input(self):
        from test_icc_output import create_clut
        from test_float_hdr import MAPPING
        f=self.f;profile=create_clut(f.root/'proof.icc')
        pipe=f.p['settings']['pixel_pipeline'];pipe['display_mapping']=dict(MAPPING)
        pipe['output_signal']=dict(primaries='bt709',transfer='srgb',reference_white_nits=100)
        pipe['proofing']=dict(profile={k:v for k,v in vars(profile).items() if v is not None},simulation_intent='relative-colorimetric')
        f.p['settings']['color']=dict(primaries='bt709',transfer='iec61966-2-1',matrix='bt709',range='limited')
        save_project(f.root,f.p);before=(f.root/'project.json').read_bytes()
        measurement=hdr_measure.measure(f.root,f.p,self.plan())
        self.assertEqual(before,(f.root/'project.json').read_bytes())
        self.assertEqual(measurement['timeline']['ICC_proofing']['converted_frames'],3)
        self.assertTrue(measurement['timeline']['ICC_proofing']['native_handles_closed'])
        rendered=f.execute('meter-proof.mkv')
        self.assertEqual(measurement['encoder_RGB16_input_sha256'],rendered['delivery']['pixel_pipeline']['transport']['video_input_sha256'])
        RECEIPTS.append(dict(test=self.id(),measurement=measurement,render=rendered))

    def test_missing_nit_units_bad_selection_and_regions_reject_before_decode(self):
        f=self.f
        for kwargs in (dict(start_frame=-1),dict(stop_frame=0),dict(stop_frame=4),dict(region=[0,0,33,16])):
            with self.subTest(kwargs=kwargs),self.assertRaises(AppError):self.plan(**kwargs)
        f.p['settings']['pixel_pipeline']['working_signal']=dict(primaries='bt2020',transfer='linear')
        with self.assertRaises(AppError):self.plan()

    def test_partial_and_active_regions_cannot_claim_whole_content(self):
        f=self.f;r=hdr_measure.measure(f.root,f.p,self.plan(start_frame=1,stop_frame=3,region=[2,3,8,7]))
        self.assertFalse(r['all_timeline_frames_measured']);self.assertFalse(r['full_canvas_measured'])
        self.assertEqual(r['analyzed_duration_seconds'],'3/20');self.assertEqual(r['first_frame'],1)

    def test_plan_mutation_and_actual_project_change_fail_before_decode(self):
        f=self.f;plan=self.plan();changed=copy.deepcopy(plan);changed['recipe']['stop_frame_exclusive']=1
        with self.assertRaises(AppError):hdr_measure.measure(f.root,f.p,changed)
        f.p['settings']['canvas']['background']='#111111'
        with self.assertRaises(AppError) as c:hdr_measure.measure(f.root,f.p,plan)
        self.assertEqual(c.exception.code,'HDR_MEASURE_INPUT_CHANGED')

    def test_cancellation_after_real_first_frame_returns_no_partial_metrics(self):
        f=self.f;marker=f.root/'cancel-measure';before=(f.root/'project.json').read_bytes()
        def progress(done,total):
            if done==1:marker.write_text('cancel')
        with self.assertRaises(AppError) as c:hdr_measure.measure(f.root,f.p,self.plan(),cancel_file=marker,progress=progress)
        self.assertEqual(c.exception.code,'CANCELLED');self.assertEqual(before,(f.root/'project.json').read_bytes())

    def test_actual_native_bundle_retains_early_HLG_black_clip_when_last_frame_clear(self):
        from ai_ad_editor.float_hlg_black import HLGBlackSignal
        f=fixture.FloatStandardRenderTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        target=HLGBlackSignal('bt2020','hlg-bt2100',100,1000,1.2,1)
        # Frame0 dark and frame1 positive; original encoded source is real 16bit FFV1.
        values=np.zeros((2,16,32,4),np.float32)
        values[...,3]=1;values[1,...,:3]=1
        f.visual(values)
        asset=f.p['assets'][0];plan=float_bundle.prepare(f.root,f.p,asset['id'],'renders/audit',source_signal=LINEAR,target_signal=target,hdr_range_policy='clip')
        output=float_bundle.export_bundle(f.root,plan);m=json.loads(Path(output['manifest']).read_bytes())
        self.assertEqual(m['colour_boundary']['hdr_output_components_clipped'],0)
        audit=m['colour_boundary_all_frames'];self.assertEqual(audit['totals']['hdr_output_components_clipped'],16*32*3)
        self.assertEqual(audit['frames_with_counted_events'],1);self.assertEqual(audit['first_affected_frame'],0)
        self.assertEqual(m['colour_boundary_scope'],'last-selected-frame')
        self.assertEqual(float_bundle.inspect_bundle(f.root,'renders/audit')['status'],'verified')
        RECEIPTS.append(dict(test=self.id(),manifest=m))
