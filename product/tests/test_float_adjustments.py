"""Independent sequence-clock, ordered pixel and resource adjustment checks."""
import copy
from fractions import Fraction
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_adjustments import FloatAdjustments
from ai_ad_editor.float_timeline import FloatTimeline
import test_float_timeline as fixture
import test_float_standard_render as native_fixture

NATIVE_CALLS=[]
RENDER_RECEIPTS=[]


def exposure(amount=0, black=0, **extra):
    return dict(type='exposure', parameters=dict(amount=amount, black=black), **extra)


def oracle(value, amount=0, black=0):
    # Independently round the public native exposure coefficients, then each
    # Float32 RGB stage. Alpha is never part of the colour calculation.
    white = np.float32(2**(-float(np.float32(amount))))
    b = np.float32(black)
    scale = np.float32(1 / float(abs(np.float32(white-b))))
    output = value.copy()
    output[..., :3] = (output[..., :3] - b) * scale
    return output


class FloatAdjustmentTests(unittest.TestCase):
    def host(self, p, sources, **kwargs):
        return FloatTimeline(p, 'main', sources, working_signal=fixture.LINEAR, **kwargs)

    def test_adjust_after_all_tracks_including_transparent_mix_and_preserve_alpha_bits(self):
        a, b = fixture.rgba((.25, .5, .75, .5)), fixture.rgba((.75, .25, 0, .25))
        p = fixture.project(assets=[dict(id=k, kind='image', sha256=fixture.SHA) for k in ('a', 'b')],
            tracks=[fixture.track([fixture.clip()]), dict(id='top', kind='video', order=1, clips=[fixture.clip('top','b')])])
        sources={k:fixture.source(v,still=True,durations=[0]) for k,v in [('a',a),('b',b)]}
        clean=self.host(p,sources).render_frame(0)[0]
        p['settings']['adjustments']=[exposure(1,.1),exposure(-1,-.2)]
        authored=copy.deepcopy(p);host=self.host(p,sources);actual,meta=host.render_frame(0)
        np.testing.assert_array_equal(actual,oracle(oracle(clean,1,.1),-1,-.2))
        np.testing.assert_array_equal(actual[...,3].view(np.uint32),clean[...,3].view(np.uint32))
        self.assertEqual(len(meta['adjustments']),2);self.assertEqual(p,authored)
        self.assertEqual(host.metadata['adjustments']['layer_applications'],2)

    def test_chain_and_layer_order_match_and_reversal_changes_result(self):
        p,s=fixture.image_project(fixture.rgba((.2,.4,.7,1)))
        a,b=exposure(1,.1),exposure(-1,-.2)
        p['settings']['adjustments']=[{'id':'grade','effects':[a,b]}]
        first=self.host(p,s).render_frame(0)[0]
        p['settings']['adjustments']=[a,b]
        np.testing.assert_array_equal(self.host(p,s).render_frame(0)[0],first)
        p['settings']['adjustments']=[b,a]
        self.assertFalse(np.array_equal(self.host(p,s).render_frame(0)[0],first))

    def test_interval_uses_exact_half_open_endpoints_and_original_local_clock(self):
        v=fixture.rgba((.2,.3,.4,1));p,s=fixture.image_project(v,fps=(4,1))
        effect=exposure(keyframes=[dict(property='amount',keyframes=[dict(at_tick=0,value=0),dict(at_tick=50,value=1)])])
        p['settings']['adjustments']=[dict(id='interval',start_tick=25,duration_tick=50,effects=[effect])]
        h=self.host(p,s)
        for frame in range(4):
            value,meta=h.render_frame(frame)
            active=frame in (1,2)
            np.testing.assert_array_equal(value,oracle(v,(frame*25-25)/50) if active else v)
            self.assertEqual(bool(meta['adjustments']),active)
        self.assertEqual(h.metadata['adjustments']['applied_frames'],2)

    def test_fractional_ticks_do_not_snap_hold_channels_to_frame_grid(self):
        v=fixture.rgba((.2,.3,.4,1));p,s=fixture.image_project(v,fps=(3,2),duration=200)
        p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200)
        p['settings']['adjustments']=[dict(start_tick=25,duration_tick=100,effects=[exposure(
            keyframes=[dict(property='amount',keyframes=[dict(at_tick=0,value=0,interpolation='hold'),dict(at_tick=42,value=1)])])])]
        value,meta=self.host(p,s).render_frame(1)
        np.testing.assert_array_equal(value,v)
        self.assertEqual(meta['adjustments'][0]['author_tick'],'125/3')

    def test_six_easings_retain_layer_clock_offset(self):
        functions={'linear':lambda x:x,'hold':lambda x:0,'ease_in':lambda x:x*x,
            'ease_out':lambda x:1-(1-x)**2,'ease_in_out':lambda x:2*x*x,
            'bezier':lambda x:3*(1-x)*x*x+x*x*x}
        for mode,fn in functions.items():
            with self.subTest(mode=mode):
                v=fixture.rgba((.2,.3,.4,1));p,s=fixture.image_project(v,fps=(4,1),duration=200)
                p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200)
                key=dict(at_tick=0,value=0,interpolation=mode)
                if mode=='bezier':key['control_points']=[0,1]
                p['settings']['adjustments']=[dict(start_tick=25,duration_tick=100,effects=[exposure(
                    keyframes=[dict(property='amount',keyframes=[key,dict(at_tick=100,value=1)])])])]
                np.testing.assert_array_equal(self.host(p,s).render_frame(2)[0],oracle(v,fn(.25)))

    def test_global_is_applied_once_after_reversed_nested_canvas(self):
        v=fixture.rgba((.2,.3,.4,1));p,s=fixture.image_project(v,fps=(4,1))
        child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        child['tracks'][0]['clips'][0]['effects']=[exposure(-1)]
        p['sequences'].append(child)
        p['sequences'][0]['tracks'][0]['clips']=[dict(id='group',sequence_id='child',timeline_start_tick=0,
            duration_tick=100,source_in_tick=0,source_out_tick=100,reverse=True)]
        p['settings']['adjustments']=[dict(start_tick=25,duration_tick=50,effects=[exposure(1)])]
        h=self.host(p,s)
        for i in range(4):
            value,meta=h.render_frame(i)
            np.testing.assert_array_equal(value,v if i in (1,2) else oracle(v,-1))
            self.assertEqual(len(meta['adjustments']),int(i in (1,2)))
        self.assertEqual(h.metadata['adjustments']['nested_application'],
            'once at selected root; child canvases are not graded twice')

    def test_short_target_clips_coverage_without_rescaling_declared_animation(self):
        v=fixture.rgba((.2,.3,.4,1));p,s=fixture.image_project(v,fps=(4,1))
        p['settings']['adjustments']=[dict(start_tick=50,duration_tick=100,effects=[exposure(
            keyframes=[dict(property='amount',keyframes=[dict(at_tick=0,value=0),dict(at_tick=100,value=1)])])])]
        h=self.host(p,s);value,meta=h.render_frame(3)
        np.testing.assert_array_equal(value,oracle(v,.25))
        self.assertEqual(meta['adjustments'][0]['author_tick'],'25')
        self.assertEqual(h.metadata['adjustments']['layers'][0]['effective_end_tick'],100)
        p['settings']['adjustments'][0]['start_tick']=125
        h=self.host(p,s)
        for i in range(4):np.testing.assert_array_equal(h.render_frame(i)[0],v)

    def test_disabled_unknown_effects_and_empty_layers_are_noops(self):
        v=fixture.rgba((.2,.3,.4,.25));p,s=fixture.image_project(v)
        p['settings']['adjustments']=[dict(enabled=False,type='hqdn3d'),dict(effects=[]),dict(effects=[dict(type='not-real',enabled=False)])]
        value,meta=self.host(p,s).render_frame(0)
        np.testing.assert_array_equal(value,v);self.assertFalse(meta['adjustments'])

    def test_malformed_and_unknown_declarations_reject_before_fetch(self):
        bad=[{},True,dict(effects='exposure'),dict(effects=[],opacity=.2),dict(type='hqdn3d'),
            dict(type='exposure',start_tick=True),dict(type='exposure',start_tick=.5),
            dict(type='exposure',duration_tick=0),dict(type='exposure',duration_tick=-1),
            dict(type='exposure',start_tick=2**63-1,duration_tick=1),dict(type='exposure',enabled=1),
            dict(type='exposure',parameters=dict(amount=float('nan')))]
        for layer in bad:
            with self.subTest(layer=layer):
                p,s=fixture.image_project();p['settings']['adjustments']=[layer]
                with self.assertRaises(AppError):self.host(p,s)
        for raw in (True,{},[exposure()]*129):
            p,s=fixture.image_project();p['settings']['adjustments']=raw
            with self.assertRaises(AppError):self.host(p,s)

    def test_keys_beyond_declared_window_reject_and_equal_endpoint_is_valid(self):
        for end,valid in ((50,True),(51,False)):
            p,s=fixture.image_project();p['settings']['adjustments']=[dict(start_tick=25,duration_tick=50,
                effects=[exposure(keyframes=[dict(property='amount',keyframes=[dict(at_tick=0,value=0),dict(at_tick=end,value=1)])])])]
            if valid:self.host(p,s)
            else:
                with self.assertRaises(AppError) as caught:self.host(p,s)
                self.assertEqual(caught.exception.code,'FLOAT_ADJUSTMENT_CLOCK')

    def test_late_surface_invalid_values_are_not_skipped_by_zero_strength(self):
        value=fixture.rgba();value[-1,-1,0]=np.nan
        p,s=fixture.image_project(value);p['settings']['adjustments']=[exposure(0)]
        with self.assertRaises(AppError):self.host(p,s).render_frame(0)

    def test_local_LUT_resource_is_shared_fingerprinted_and_change_detected(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='float-adjust-lut-',dir=base) as directory:
            root=Path(directory);table=root/'look.cube'
            table.write_text('LUT_3D_SIZE 2\n'+'\n'.join(f'{r/2} {g/2} {b/2}' for b in (0,1) for g in (0,1) for r in (0,1))+'\n',encoding='utf8')
            p,s=fixture.image_project(fixture.rgba((.2,.4,.8,.3)))
            effect=dict(type='lut3d',parameters=dict(path='look.cube',input_signal=vars(fixture.LINEAR),
                output_signal=vars(fixture.LINEAR),interpolation='trilinear',intensity=1))
            p['settings']['adjustments']=[dict(effects=[effect])]
            h=self.host(p,s,resource_root=root);value,_=h.render_frame(0)
            np.testing.assert_allclose(value[...,:3],fixture.rgba((.1,.2,.4,1))[...,:3],rtol=0,atol=1e-7)
            plans=[plan.effects for plan in h.adjustments.plans]
            self.assertEqual(len(h.effects.dependencies(plans)),1)
            h.verify_sources();table.write_text(table.read_text()+'# changed\n')
            with self.assertRaises(AppError) as caught:h.verify_sources()
            self.assertEqual(caught.exception.code,'FLOAT_LUT_RESOURCE_CHANGED')

    def test_real_ten_bit_render_frame_preview_and_complete_audio(self):
        f=native_fixture.FloatStandardRenderTests(methodName='runTest');f.setUp();self.addCleanup(f.doCleanups)
        f.s['duration_tick']=90000
        surface=np.broadcast_to(np.array([.2,.2,.2,1],np.float32),(10,16,32,4)).copy()
        f.visual(surface);audio=f.audio()
        sound=f.p['assets'][1];sound['rights_ref']='rights_sound'
        f.s['tracks'][1]['clips'][0]['id']='sound_clip'
        ledger=native_fixture.load_ledger(f.root)
        native_fixture.add_record(ledger,dict(asset_id='sound',record_id='rights_sound',verification_status='verified',
            source_type='generated',source_url=str(f.root/sound['uri']),license_spdx='CC0-1.0',permitted_uses=['all'],
            commercial_use_allowed=True,modification_allowed=True,attribution_required=False,sha256=sound['sha256'],
            evidence='Original numerical stereo fixture authored by this test.'))
        native_fixture.save_ledger(f.root,ledger);before=f.execute('before.mkv')
        f.p['settings']['adjustments']=[dict(id='grade',start_tick=27000,duration_tick=36000,
            effects=[exposure(keyframes=[dict(property='amount',keyframes=[dict(at_tick=0,value=0,interpolation='linear'),dict(at_tick=36000,value=1,interpolation='linear')])])])]
        authored={k:copy.deepcopy(f.p[k]) for k in ('settings','assets','sequences')};after=f.execute('after.mkv')
        actual=f.decode_y(after['path'],32,16)
        for frame in range(10):
            ev=(frame*9000-27000)/36000 if 3<=frame<7 else 0
            expected=64+.2*2**ev*876
            self.assertLessEqual(float(np.abs(actual[frame,0].astype(np.float64)-expected).max()),1.5)
        self.assertEqual(after['delivery']['pixel_pipeline']['timeline']['adjustments']['applied_frames'],4)
        raw=[]
        for result in (before,after):
            raw.append(f.native([native_fixture.ffmpeg_path(),'-nostdin','-v','error','-i',result['path'],
                '-map','0:a:0','-c:a','pcm_f32le','-f','f32le','-']))
        self.assertEqual(raw[0],raw[1]);np.testing.assert_array_equal(np.frombuffer(raw[1],'<f4').reshape(-1,2),audio)
        code,envelope=f.invoke('preview','frame','--project',f.root,'--frame','5','--height','64')
        self.assertEqual(code,0,envelope);preview=envelope['data']
        decoded=f.native([native_fixture.ffmpeg_path(),'-nostdin','-v','error','-i',preview['path'],'-pix_fmt','rgba64le','-f','rawvideo','-'])
        # Height is an upper bound: previews preserve this small native canvas.
        pixels=np.frombuffer(decoded,'<u2').reshape(16,32,4)
        self.assertLessEqual(float(np.abs(pixels[...,:3].astype(np.float64)-.2*2**.5*65535).max()),1)
        self.assertEqual({k:f.p[k] for k in authored},authored);f.assert_clean()
        RENDER_RECEIPTS.append(dict(scope='ten-bit render, full PCM and RGBA16 preview',result=after,preview=preview))

    def test_project_local_LUT_is_read_locked_before_encoder_and_released_afterward(self):
        f=native_fixture.FloatStandardRenderTests(methodName='runTest');f.setUp();self.addCleanup(f.doCleanups)
        f.visual();table=f.root/'look.cube'
        table.write_text('LUT_3D_SIZE 2\n'+'\n'.join(f'{r} {g} {b}' for b in (0,1) for g in (0,1) for r in (0,1))+'\n',encoding='utf8')
        original=table.read_bytes()
        f.p['settings']['adjustments']=[dict(effects=[dict(type='lut3d',parameters=dict(path='look.cube',
            input_signal=vars(fixture.LINEAR),output_signal=vars(fixture.LINEAR)))])]
        from ai_ad_editor.float_stream import _EncoderPipe
        checked=[]
        def factory(*args,**kwargs):
            with self.assertRaises(PermissionError):table.write_bytes(b'changed')
            checked.append(True);return _EncoderPipe(*args,**kwargs)
        with patch('ai_ad_editor.float_standard_render._EncoderPipe',side_effect=factory):result=f.execute()
        self.assertTrue(checked);self.assertEqual(table.read_bytes(),original)
        artifacts=result['delivery']['pixel_pipeline']['artifacts']
        self.assertTrue(any(r['path']==str(table) and r['role']=='float-effect-resource' for r in artifacts))
        table.write_bytes(original+b'# unlocked after render\n');f.assert_clean()


if __name__=='__main__':unittest.main()
