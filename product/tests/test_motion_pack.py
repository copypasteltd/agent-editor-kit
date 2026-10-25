"""Portable motion safety and observable author-clock/reuse contracts."""
from __future__ import annotations

import copy
from fractions import Fraction
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from ai_ad_editor import motion_pack as mp
from ai_ad_editor.animation import keyframe_value
from ai_ad_editor.clip_windows import slice_clip
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project, load_project, project_file, save_project
from ai_ad_editor.runtime import configure_local_runtime
from test_magnetic_reorder import invoke


def clip():
    return dict(id='hero', asset_id='image', timeline_start_tick=0, duration_tick=180000,
                source_in_tick=0, source_out_tick=180000,
                transform=dict(position=dict(x=.5,y=.5),scale=1.,rotation=0.,opacity=1.))


class MotionPackContracts(unittest.TestCase):
    def assert_error(self, code, callback):
        with self.assertRaises(AppError) as caught: callback()
        self.assertEqual(caught.exception.code, code)

    def test_six_recipes_compile_all_parameters_at_declared_extremes(self):
        for name in mp.BUILTIN_NAMES:
            pack=mp.builtin(name)
            for extremum in ('minimum','maximum','default'):
                with self.subTest(name=name,extremum=extremum):
                    output, receipt, _=mp.compile_pack(pack,clip(),parameters={k:s[extremum] for k,s in pack['parameters'].items()})
                    self.assertEqual(receipt['content_sha256'],mp.digest(pack))
                    self.assertTrue(all(len(t['keyframes'])==65 for t in output['keyframes']))

    def test_capture_and_retime_preserves_original_bezier_easing_at_independent_times(self):
        original=clip();original['keyframes']=[dict(property='scale',keyframes=[
            dict(at_tick=18000,value=1.,interpolation='bezier',control_points=[.2,.1,.7,.9]),
            dict(at_tick=130000,value=1.4,interpolation='ease_out'),
            dict(at_tick=170000,value=1.1,interpolation='hold')])]
        pack=mp.capture_pack(original,pack_id='captured',name='Captured',creator='tester',license='LicenseRef-UNVERIFIED')
        other=clip();other['duration_tick']=360000
        target,receipt,_=mp.compile_pack(pack,other)
        for at in (0,12999,18000,45000,99999,130000,145000,170000,179999,180000):
            a=keyframe_value(original,mp.ALIASES['transform.scale'],1.,at)
            b=keyframe_value(target,mp.ALIASES['transform.scale'],1.,at*2)
            self.assertAlmostEqual(a,b,12)
        self.assertEqual(receipt['license'],'LicenseRef-UNVERIFIED')
        self.assertIn('control_points',pack['tracks'][0]['keyframes'][1])

    def test_capture_window_retains_full_author_curve_instead_of_slicing_easing(self):
        original,_,_=mp.compile_pack(mp.builtin('arc_push'),clip())
        piece=slice_clip(original,45000,135000,clip_id='piece')
        captured=mp.capture_pack(piece,pack_id='window',name='Window',creator='test',license='MIT')
        self.assertEqual(captured['capture']['authored_duration_tick'],180000)
        self.assertEqual(captured['tracks'][0]['keyframes'][0]['at'],[0,1])
        self.assertEqual(captured['tracks'][0]['keyframes'][-1]['at'],[1,1])

    def test_visible_application_uses_author_offset_and_preserves_native_source_fields(self):
        original=clip();original.update(reverse=True,source_in_tick=1000,source_out_tick=271000,
            speed_curve=dict(keyframes=[dict(at_tick=0,speed=.5),dict(at_tick=270000,speed=2.)]))
        piece=slice_clip(original,45000,135000,clip_id='piece')
        got,receipt,_=mp.compile_pack(mp.builtin('orbit_focus'),piece,start_tick=9000,end_tick=81000)
        self.assertEqual(receipt['author_start_tick'],54000)
        self.assertEqual(receipt['author_end_tick'],126000)
        for k in ('reverse','source_in_tick','source_out_tick','speed_curve','presentation_window'):
            self.assertEqual(got[k],piece[k])

    def test_property_alias_conflicts_require_explicit_whole_track_replacement(self):
        original=clip();original['keyframes']=[dict(property='position_x',keyframes=[dict(at_tick=0,value=.5,interpolation='hold')]),
            dict(property='audio.volume',keyframes=[dict(at_tick=0,value=.3,interpolation='hold')])]
        pack=mp.builtin('arc_push')
        self.assert_error('MOTION_PACK_CONFLICT',lambda:mp.compile_pack(pack,original))
        got,receipt,warnings=mp.compile_pack(pack,original,replace=True)
        self.assertEqual(got['keyframes'][0],original['keyframes'][1])
        self.assertEqual(receipt['replaced_properties'],['position_x'])
        self.assertEqual(warnings[0]['code'],'MOTION_PACK_REPLACED_TRACKS')
        self.assertEqual(original['keyframes'][0]['property'],'position_x')

    def test_rational_rounding_collisions_are_rejected_before_mutation(self):
        original=clip();original['duration_tick']=63
        before=copy.deepcopy(original)
        self.assert_error('MOTION_PACK_TIME_COLLISION',lambda:mp.compile_pack(mp.builtin('arc_push'),original))
        self.assertEqual(original,before)

    def test_parameter_unknown_bool_nan_infinite_and_overflow_are_rejected(self):
        pack=mp.builtin('arc_push')
        for params in ({'unknown':1},{'zoom':True},{'zoom':float('nan')},{'zoom':float('inf')},{'zoom':10**1000},{'zoom':.51}):
            with self.subTest(params=str(params)[:80]):
                self.assert_error('MOTION_PACK_INVALID',lambda:mp.compile_pack(pack,clip(),parameters=params))

    def test_rejects_zero_negative_duplicate_or_out_of_range_times(self):
        for at in ([0,0],[-1,1],[2,1],[True,1],[1,10**13]):
            pack=mp.builtin('arc_push');pack['tracks'][0]['keyframes'][1]['at']=at
            with self.subTest(at=at):
                self.assert_error('MOTION_PACK_INVALID',lambda:mp.validate_pack(pack))

    def test_rejects_bad_easing_unknown_fields_and_unbound_expressions(self):
        for mutation in ('easing','field','expression','bezier','mode','format'):
            pack=mp.builtin('arc_push');point=pack['tracks'][0]['keyframes'][0]
            if mutation=='easing':point['interpolation']=[]
            elif mutation=='field':point['eval']='__import__("os")'
            elif mutation=='expression':point['value']={'expression':'t+1'}
            elif mutation=='bezier':point.update(interpolation='bezier',control_points=[-1,0,1,1])
            elif mutation=='mode':pack['tracks'][0]['mode']='exec'
            else:pack['format_version']=2
            with self.subTest(mutation=mutation):
                self.assert_error('MOTION_PACK_INVALID',lambda:mp.validate_pack(pack))

    def test_duplicate_json_keys_and_large_inputs_are_rejected(self):
        self.assert_error('MOTION_PACK_INVALID',lambda:mp.decode_pack(b'{"format":1,"format":2}'))
        self.assert_error('MOTION_PACK_TOO_LARGE',lambda:mp.decode_pack(b' '*(mp.MAX_BYTES+1)))

    def test_capture_rejects_duplicate_native_aliases_and_empty_properties(self):
        original=clip();original['keyframes']=[dict(property=p,keyframes=[dict(at_tick=0,value=1.,interpolation='hold')])
            for p in ('scale','transform.scale')]
        kwargs=dict(pack_id='x',name='X',creator='test',license='MIT')
        self.assert_error('MOTION_PACK_ALIAS_CONFLICT',lambda:mp.capture_pack(original,**kwargs))
        self.assert_error('MOTION_PACK_EMPTY',lambda:mp.capture_pack(clip(),**kwargs))

    def test_tracking_is_not_silently_overwritten(self):
        original=clip();original['tracking_binding']={'source_clip_id':'other'}
        self.assert_error('MOTION_PACK_TRACKING_CONFLICT',lambda:mp.compile_pack(mp.builtin('arc_push'),original))

    def test_catalog_calls_return_independent_values(self):
        first=mp.catalog();first[0]['parameters']['zoom']['default']=999
        self.assertEqual(mp.catalog()[0]['parameters']['zoom']['default'],.15)

    def test_additive_scale_allows_negative_deltas_but_rejects_invalid_final_scale(self):
        pack=mp.builtin('arc_push');pack['tracks']=[dict(property='transform.scale',mode='add',keyframes=[
            dict(at=[0,1],value=-.2,interpolation='linear'),dict(at=[1,1],value=.1,interpolation='hold')])]
        result,_,_=mp.compile_pack(pack,clip())
        self.assertEqual([k['value'] for k in result['keyframes'][0]['keyframes']],[.8,1.1])
        pack['tracks'][0]['keyframes'][0]['value']=-1.1
        self.assert_error('MOTION_PACK_INVALID',lambda:mp.compile_pack(pack,clip()))


class MotionPackCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name);self.root=self.work/'工程';create_project(self.root)
        source=self.work/'source.png'
        image=Image.new('RGB',(160,90),'#112233');ImageDraw.Draw(image).rectangle((60,25,100,65),fill='red');image.save(source)
        code,value=invoke('media','ingest','--project',str(self.root),'--input',str(source))
        self.assertEqual(code,0,value)
        project=load_project(self.root)[1];self.sequence_id=project['sequences'][0]['id']
        target=clip();target['asset_id']=value['data']['asset']['id']
        project['sequences'][0]['duration_tick']=180000;project['sequences'][0]['tracks'][0]['clips']=[target]
        save_project(self.root,project)

    def command(self,action,*args,code=0):
        actual,value=invoke('motion','pack',action,*map(str,args))
        self.assertEqual(actual,code,value)
        return value

    def apply(self,*args,**kwargs):
        return self.command('apply','--project',self.root,'--clip-id','hero',*args,**kwargs)

    def test_catalog_inspect_create_roundtrip_and_no_overwrite(self):
        listed=self.command('list');self.assertEqual(listed['data']['count'],6)
        pack=self.work/'路径.aek-motion.json'
        created=self.command('create','--name','arc_push','--output',pack)
        inspected=self.command('inspect','--input',pack)
        self.assertEqual(created['data']['content_sha256'],inspected['data']['content_sha256'])
        before=pack.read_bytes();failed=self.command('create','--name','orbit_focus','--output',pack,code=2)
        self.assertEqual(failed['errors'][0]['code'],'OUTPUT_EXISTS');self.assertEqual(before,pack.read_bytes())

    def test_dry_run_and_idempotency_preserve_snapshots_and_project(self):
        before=project_file(self.root).read_bytes()
        planned=self.apply('--name','arc_push','--dry-run')
        self.assertEqual(planned['status'],'planned');self.assertEqual(before,project_file(self.root).read_bytes())
        first=self.apply('--name','arc_push','--idempotency-key','motion_once')
        after=project_file(self.root).read_bytes()
        replay=self.apply('--name','arc_push','--idempotency-key','motion_once')
        self.assertEqual(first['operation_id'],replay['operation_id']);self.assertEqual(after,project_file(self.root).read_bytes())
        self.assertTrue(first['data']['before_snapshot']['snapshot_id'])
        self.apply('--name','orbit_focus','--idempotency-key','motion_once',code=2)
        self.assertEqual(after,project_file(self.root).read_bytes())

    def test_capture_does_not_mutate_project_and_copies_declared_rights(self):
        self.apply('--name','bezier_sweep')
        before=project_file(self.root).read_bytes();output=self.work/'capture.json'
        captured=self.command('capture','--project',self.root,'--clip-id','hero','--id','own_motion',
            '--title','Saved motion','--creator','Customer','--license','LicenseRef-UNVERIFIED','--output',output)
        self.assertEqual(before,project_file(self.root).read_bytes())
        self.assertEqual(captured['data']['pack']['license'],'LicenseRef-UNVERIFIED')
        self.assertEqual(captured['data']['pack']['creator'],'Customer')

    def test_capture_rejects_project_idempotency_without_writing_any_project_file(self):
        self.apply('--name','arc_push')
        before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        output=self.work/'rejected-capture.json'
        value=self.command('capture','--project',self.root,'--clip-id','hero','--id','capture',
            '--title','Capture','--creator','Customer','--license','LicenseRef-UNVERIFIED','--output',output,
            '--idempotency-key','read-only-capture',code=2)
        self.assertEqual(value['errors'][0]['code'],'ARGUMENT_INVALID')
        self.assertFalse(output.exists())
        self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()})

    def test_bad_parameters_conflicts_and_cancel_leave_original_bytes(self):
        before=project_file(self.root).read_bytes()
        for args in (('--param','zoom=true'),('--param','zoom=0.1','--param','zoom=0.2'),('--param','zoom=2')):
            self.apply('--name','arc_push',*args,code=2)
            self.assertEqual(before,project_file(self.root).read_bytes())
        marker=self.root/'stop';marker.write_text('cancel')
        response=self.apply('--name','arc_push','--cancel-file',marker,code=8)
        self.assertEqual(response['errors'][0]['code'],'CANCELLED')
        self.assertEqual(before,project_file(self.root).read_bytes())
        self.apply('--name','arc_push')
        before=project_file(self.root).read_bytes()
        self.apply('--name','orbit_focus',code=2)
        self.assertEqual(before,project_file(self.root).read_bytes())
        replaced=self.apply('--name','orbit_focus','--replace')
        self.assertEqual(replaced['warnings'][0]['code'],'MOTION_PACK_REPLACED_TRACKS')

    def test_tiny_budget_and_locked_tracks_are_explicit_failures(self):
        before=project_file(self.root).read_bytes()
        value=self.apply('--name','arc_push','--timeout-seconds','0.000000001',code=6)
        self.assertEqual(value['errors'][0]['code'],'PROCESS_TIMEOUT')
        self.assertEqual(before,project_file(self.root).read_bytes())
        project=load_project(self.root)[1];project['sequences'][0]['tracks'][0]['locked']=True;save_project(self.root,project)
        value=self.apply('--name','arc_push',code=2)
        self.assertEqual(value['errors'][0]['code'],'EDIT_TRACK_LOCKED')

    def test_post_save_failure_rolls_back_project_snapshot_and_operation(self):
        before=project_file(self.root).read_bytes()
        def fail(*args,**kwargs): raise AppError('INJECTED_FAILURE','injected after save',exit_code=6)
        with patch('ai_ad_editor.cli._operation',side_effect=fail):
            value=self.apply('--name','arc_push',code=6)
        self.assertEqual(value['errors'][0]['code'],'INJECTED_FAILURE')
        self.assertEqual(before,project_file(self.root).read_bytes())
        self.assertFalse((self.root/'operations/project-transaction.json').exists())

    def test_applied_keys_render_without_external_recipe(self):
        output=self.work/'recipe.json'
        self.command('create','--name','arc_push','--output',output)
        value=self.apply('--input',output,'--param','zoom=0.2')
        output.unlink()
        project=load_project(self.root)[1]
        self.assertEqual(project['provenance']['change_log'][-1]['motion']['recipe']['id'],'arc_push')
        self.assertEqual(project['sequences'][0]['tracks'][0]['clips'][0]['keyframes'],value['data']['clip']['keyframes'])


if __name__=='__main__':unittest.main()
