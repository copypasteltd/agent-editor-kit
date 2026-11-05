"""Face contract/geometry boundaries; real model/media checks live in smoke receipts."""
from __future__ import annotations
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from ai_ad_editor.face_geometry import FaceAssociation,controls,validate_face
from ai_ad_editor.face_landmarks import FaceModels
from ai_ad_editor import local_face as face
from ai_ad_editor.errors import AppError


def found(x=10):
    return {'bbox':[x,10.,30.,40.],'crop':[8,8,46,55],
            'landmarks':[[float(x+10),25.,1.02] for _ in range(66)],'confidence':1.02,'detection_score':.9}


def report():
    row = {'frame_index':0,'pts_seconds':0.,'decoded_rgba_sha256':'sha256:'+'a'*64,
           'faces':[{'face_id':'face_0001',**found()}]}
    return {'source':{'sha256':'sha256:'+'b'*64,'width':64,'height':64,'fps':'1','frame_count':1,'color_transfer':'srgb'},
            'request':{'adapter':{'sha256':'sha256:'+'c'*64}},'response':{'frames':[row]}}


class LocalFaceContractTests(unittest.TestCase):
    def test_controls_are_explicit_neutral_by_default(self):
        self.assertEqual(controls(),dict(skin_smooth=0.,exposure_ev=0.,face_slim=0.,eye_enlarge=0.))
        self.assertEqual(controls(exposure_ev=-1)['exposure_ev'],-1.)

    def test_invalid_controls_are_rejected_without_silent_clamping(self):
        for key in controls():
            for value in (True,None,float('nan'),float('inf'),1.001,-1.001):
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    controls(**{key:value})
        with self.assertRaises(ValueError):
            controls(whiten=.2)

    def test_adjacent_geometry_keeps_id_but_does_not_claim_identity(self):
        tracker = FaceAssociation()
        first = tracker.update([found()])[0]
        second = tracker.update([found(11)])[0]
        self.assertEqual(first['face_id'],second['face_id'])
        self.assertEqual(second['landmarks'],found(11)['landmarks'])

    def test_absent_face_never_copies_previous_landmarks_or_recycles_id(self):
        tracker = FaceAssociation()
        self.assertEqual(tracker.update([found()])[0]['face_id'],'face_0001')
        self.assertEqual(tracker.update([]),[])
        self.assertEqual(tracker.update([found()])[0]['face_id'],'face_0002')

    def test_explicit_cut_clears_association_even_for_identical_geometry(self):
        tracker = FaceAssociation();tracker.update([found()])
        self.assertEqual(tracker.update([found()],cut=True)[0]['face_id'],'face_0002')

    def test_multiple_faces_follow_geometry_when_detector_order_changes(self):
        tracker = FaceAssociation();tracker.update([found(10),found(100)])
        current = tracker.update([found(101),found(11)])
        self.assertEqual([(r['face_id'],r['bbox'][0]) for r in current],[('face_0001',11),('face_0002',101)])

    def test_raw_heatmap_regression_values_are_preserved(self):
        row = {'face_id':'face_0001',**found()}
        validate_face(row,64,64)
        self.assertEqual(row['landmarks'][0][2],1.02)
        for key in ('detection_score','confidence'):
            wrong = copy.deepcopy(row);wrong[key] = float('nan')
            with self.assertRaises(ValueError):
                validate_face(wrong,64,64)

    def test_malformed_points_and_outside_crops_fail(self):
        row = {'face_id':'face_0001',**found()}
        invalid = []
        v=copy.deepcopy(row);v['landmarks'].pop();invalid.append(v)
        v=copy.deepcopy(row);v['landmarks'][0][0]=10000;invalid.append(v)
        v=copy.deepcopy(row);v['crop']=[0,0,65,64];invalid.append(v)
        v=copy.deepcopy(row);v['face_id']='some_person';invalid.append(v)
        v=copy.deepcopy(row);v['landmarks'][0][0]=True;invalid.append(v)
        for v in invalid:
            with self.subTest(value=v),self.assertRaises(ValueError):
                validate_face(v,64,64)

    def test_recipe_contains_bound_complete_landmarks_and_can_be_resealed(self):
        recipe = face.recipe_from_report(report(),settings={'skin_smooth':.2},selected_ids=['face_0001'])
        face.validate_recipe(recipe)
        self.assertEqual(recipe['source_sha256'],report()['source']['sha256'])
        self.assertEqual(recipe['frames'],report()['response']['frames'])
        changed = copy.deepcopy(recipe);changed['controls']['skin_smooth']=.8
        with self.assertRaises(ValueError):
            face.validate_recipe(changed)
        face.validate_recipe(face.seal(changed))

    def test_resealed_bad_coverage_clock_selection_and_geometry_still_fail(self):
        recipe = face.recipe_from_report(report(),settings={})
        invalid=[]
        v=copy.deepcopy(recipe);v['frames']=[];invalid.append(v)
        v=copy.deepcopy(recipe);v['frames'][0]['pts_seconds']=.1;invalid.append(v)
        v=copy.deepcopy(recipe);v['selected_ids']=['face_0002'];invalid.append(v)
        v=copy.deepcopy(recipe);v['frames'][0]['faces'][0]['crop'][2]=100;invalid.append(v)
        v=copy.deepcopy(recipe);v['source_sha256']='bad';invalid.append(v)
        v=copy.deepcopy(recipe);v['controls']['eye_enlarge']=float('inf');invalid.append(v)
        for v in invalid:
            with self.subTest(value=v),self.assertRaises((ValueError,TypeError,OverflowError)):
                face.validate_recipe(face.seal(v))

    def test_report_budget_is_rejected_before_tools_or_worker_start(self):
        source={'frame_count':1800,'width':1920,'height':1080}
        with mock.patch.object(face,'verify_adapter',return_value={'ok':True}),mock.patch.object(face,'source_plan',return_value=source),mock.patch.object(face,'ffmpeg_path',side_effect=AssertionError('tool called')):
            with self.assertRaises(AppError) as raised:
                face.scan_plan(Path('.'),{}, {},max_faces=4)
        self.assertEqual(raised.exception.code,'FACE_REPORT_BUDGET')

    def test_bad_native_thread_options_fail_before_importing_dependencies(self):
        for threads in (True,0,17,float('nan')):
            with self.subTest(threads=threads),self.assertRaisesRegex(ValueError,'FACE_THREADS_INVALID'):
                FaceModels(Path('does-not-exist'),threads=threads)

    def test_short_pipe_reads_are_accumulated(self):
        from ai_ad_editor.face_worker import read_exact
        class Pipe:
            def __init__(self):self.parts=iter([b'a',b'bc',b'd',b''])
            def read(self,n):return next(self.parts)
        self.assertEqual(read_exact(Pipe(),4),b'abcd')

    def test_hdr_and_high_bit_depth_fail_before_worker_admission(self):
        asset={'id':'source','kind':'video','uri':'source.mkv','sha256':'sha256:'+'b'*64}
        for pixel,transfer in (('yuv420p10le','bt709'),('yuv420p','smpte2084'),('gbrpf32le','linear'),('yuv420p','arib-std-b67')):
            info={'duration_seconds':1,'streams':[{'codec_type':'video','width':64,'height':64,'pix_fmt':pixel,'color_transfer':transfer,'avg_frame_rate':'1','nb_frames':'1'}]}
            with self.subTest(pixel=pixel,transfer=transfer),mock.patch.object(face,'resolve_local_path',return_value=Path('source.mkv')),mock.patch.object(face,'sha256_file',return_value='b'*64),mock.patch.object(face,'probe_media',return_value=info):
                with self.assertRaises(AppError) as caught:
                    face.source_plan(Path('.'),asset)
                self.assertEqual(caught.exception.code,'FACE_SOURCE_COLOR_UNSUPPORTED')

    def test_unspecified_transfer_is_recorded_as_an_assumption(self):
        asset={'id':'source','kind':'video','uri':'source.mkv','sha256':'sha256:'+'b'*64}
        for transfer,expected,assumed in ((None,'srgb',True),('bt709','bt709',False),('iec61966-2-1','srgb',False)):
            info={'duration_seconds':1,'streams':[{'codec_type':'video','width':64,'height':64,'pix_fmt':'yuv420p','color_transfer':transfer,'avg_frame_rate':'1','nb_frames':'1'}]}
            with self.subTest(transfer=transfer),mock.patch.object(face,'resolve_local_path',return_value=Path('source.mkv')),mock.patch.object(face,'sha256_file',return_value='b'*64),mock.patch.object(face,'probe_media',return_value=info):
                source=face.source_plan(Path('.'),asset)
                self.assertEqual((source['color_transfer'],source['transfer_assumed']),(expected,assumed))

    def test_worker_pixel_and_clock_proofs_reject_boolean_or_missing_checks(self):
        plan={'mode':'retouch','source':report()['source']}
        valid={'protocol':face.PROTOCOL,'status':'succeeded','network':'disabled','blocked_network_events':[],
               'request_sha256':face.digest(plan),'source_sha256':plan['source']['sha256'],'device':'cpu','engine':face.RETOUCH,
               'model_forwards':0,'output_frames':1,'protected_pixel_mismatches':0,'alpha_mismatches':0,
               'changed_rgb_pixels':[0],'affected_pixels':[0],'output_rgba_sha256':['sha256:'+'d'*64],'source_clock_frames_checked':1}
        face.validate_response(valid,plan)
        for key,value in (('alpha_mismatches',False),('output_frames',True),('source_clock_frames_checked',False),('affected_pixels',[]),('changed_rgb_pixels',[1]),('output_rgba_sha256',['bad'])):
            with self.subTest(key=key),self.assertRaises(AppError):
                face.validate_response({**valid,key:value},plan)


if __name__ == '__main__':
    unittest.main()
