from __future__ import annotations

import contextlib
import copy
import io
import json
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_vision import YOLO_ENGINE, manifest_hash, prepare_request, settings
from ai_ad_editor.model_registry import load_visual_model_registry, verify_visual_adapter
from ai_ad_editor.project import ledger_file
from ai_ad_editor.rights import check_project_rights, load_ledger
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.tracking import _parse_roi
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.vision_tracker import MotionTracker, assignment, decode_detections

BASE_RUN = subprocess.run


def invoke(*argv: str) -> tuple[int, dict]:
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(list(argv))
    return code, json.loads(output.getvalue())


def detection(x, *, confidence=.9, class_id=0):
    return {'x':x, 'y':.5, 'width':.1, 'height':.2, 'confidence':confidence, 'class_id':class_id}


class AssociationTests(unittest.TestCase):
    def tracker(self, **kwargs):
        return MotionTracker(confidence=.35, match_iou=.1, max_gap_seconds=kwargs.get('gap', .8), max_objects=kwargs.get('objects', 8))

    def test_assignment_finds_global_minimum_instead_of_greedy_pair(self):
        self.assertEqual(assignment([[1,2],[1.1,100]]), [(0,1),(1,0)])
        self.assertEqual(assignment([[1,1,2],[1,1,2]]), [(0,0),(1,1)])

    def test_integer_letterbox_coordinates_restore_landscape_and_portrait(self):
        roi={'x':0,'y':0,'width':1,'height':1}
        for width,height,resized,pad in [(1920,1080,(640,360),(0,140)),(641,960,(427,640),(106,0))]:
            rw,rh=resized; px,py=pad
            value=decode_detections([[px+rw*.1,py+rh*.1,px+rw*.5,py+rh*.6,.9,0]],width,height,resized,pad,threshold=.1,classes=[0],roi=roi)[0]
            for key,expected in [('x',.3),('y',.35),('width',.4),('height',.5)]:
                self.assertAlmostEqual(value[key],expected)

    def test_detection_rejects_nonfinite_values_and_filters_roi_class_and_padding(self):
        options=dict(threshold=.1,classes=[0],roi={'x':.2,'y':.2,'width':.6,'height':.6})
        self.assertEqual(decode_detections([[0,0,20,20,.8,0],[100,100,300,300,.8,15],[0,0,640,100,.8,0]],640,360,(640,360),(0,140),**options),[])
        with self.assertRaises(ValueError):
            decode_detections([[0,0,200,300,math.nan,0]],640,360,(640,360),(0,140),**options)
        with self.assertRaises(AppError):
            _parse_roi('nan,0,0.1,0.1')

    def test_low_confidence_can_continue_but_cannot_start_a_track(self):
        tracker=self.tracker()
        tracker.update([detection(.3,confidence=.15)],0)
        self.assertEqual(tracker.tracks,[])
        tracker.update([detection(.3)],.1)
        tracker.update([detection(.31,confidence=.15)],.2)
        self.assertEqual(len(tracker.tracks),1)
        self.assertEqual(len(tracker.tracks[0]['frames']),2)

    def test_missing_observations_resume_within_gap_and_expire_after_gap(self):
        tracker=self.tracker()
        tracker.update([detection(.2)],0)
        tracker.update([detection(.25)],.2)
        tracker.update([],.4)
        tracker.update([detection(.35)],.6)
        self.assertEqual(len(tracker.tracks),1)
        self.assertEqual(len(tracker.tracks[0]['frames']),3)
        self.assertAlmostEqual(tracker.tracks[0]['max_observation_gap_seconds'],.4)
        tracker.update([detection(.4)],1.6)
        self.assertEqual(len(tracker.tracks),2)

    def test_velocity_association_keeps_two_toy_paths_through_crossing(self):
        tracker=self.tracker()
        for i in range(6):
            at=i*.2
            tracker.update(sorted([detection(.2+.5*at),detection(.8-.5*at)],key=lambda d:d['x']),at)
        self.assertEqual(len(tracker.tracks),2)
        self.assertAlmostEqual(tracker.tracks[0]['frames'][-1]['x'],.7)
        self.assertAlmostEqual(tracker.tracks[1]['frames'][-1]['x'],.3)

    def test_class_gating_and_object_budget_never_silently_drop_objects(self):
        tracker=self.tracker(objects=2)
        tracker.update([detection(.3),detection(.3,class_id=15)],0)
        tracker.update([detection(.31,class_id=15),detection(.31)],.1)
        self.assertEqual([t['class_id'] for t in tracker.tracks],[0,15])
        with self.assertRaisesRegex(ValueError,'OBJECT_LIMIT'):
            tracker.update([detection(.9,class_id=16)],.2)


class NativeVisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='agent-vision-')
        self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name)
        self.root=self.base/'中文项目'
        self.assertEqual(invoke('project','init',str(self.root))[0],0)
        self.model=self.base/'model.onnx';self.model.write_bytes(b'protocol fixture only, not a model quality test')
        self.proof=self.base/'proof.json';atomic_write_json(self.proof,{'purpose':'internal protocol fixture'})
        self.source=self.base/'source.mp4'
        r=BASE_RUN(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-f','lavfi','-i','color=c=blue:s=320x180:r=8:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(self.source)],capture_output=True)
        self.assertEqual(r.returncode,0,r.stderr)
        code,value=invoke('media','ingest','--project',str(self.root),'--input',str(self.source))
        self.assertEqual(code,0,value)
        self.asset=value['data']['asset']['id']
        plan=self.base/'plan.json'
        atomic_write_json(plan,{'operations':[{'op':'append_clip','track_id':'track_video_1','id':'video','asset_id':self.asset,'source_in_tick':0,'source_out_tick':90000},{'op':'add_track','track_id':'titles','kind':'subtitle','order':3},{'op':'append_clip','track_id':'titles','id':'title','generator':{'type':'text'},'source_in_tick':0,'source_out_tick':90000,'subtitle':{'text':'Track','style':{'fontsize':24}}}]})
        self.assertEqual(invoke('timeline','compose','--project',str(self.root),'--input',str(plan))[0],0)
        self.options=['--project',str(self.root),'--adapter-id','yolo','--engine',YOLO_ENGINE,'--model-path',str(self.model),'--executable',sys.executable,'--evidence',str(self.proof)]
        self.change=None
        self.calls=0

    def project(self):
        return json.loads((self.root/'project.json').read_text(encoding='utf-8'))

    def metadata(self):
        return tuple(p.read_bytes() if p.exists() else None for p in [self.root/'project.json',self.root/'project.lock.json',ledger_file(self.root),self.root/'models/visual-adapters.json'])

    def register(self):
        code,value=invoke('media','adapter','register',*self.options)
        self.assertEqual(code,0,value)
        return value

    def track(self, *extra):
        return invoke('media','track','--project',str(self.root),'--asset-id',self.asset,'--adapter-id','yolo','--roi','0,0,1,1','--step-frames','1',*extra)

    def fake_runner(self, argv, **kwargs):
        if not any(str(a).endswith('yolo_worker.py') for a in argv):
            return BASE_RUN(argv,**kwargs)
        self.calls+=1
        self.assertIn('-I',argv)
        request=json.loads(kwargs['input'])
        video=request['native']['video']
        frames=[{'at_seconds':request['range']['start_seconds']+i*video['sample_interval_seconds'],'x':.3+i*.02,'y':.4,'width':.1,'height':.2,'confidence':.9} for i in range(video['expected_samples'])]
        response={'protocol':request['protocol'],'status':'ok','engine':YOLO_ENGINE,'network':'disabled','blocked_network_events':[],'request_sha256':request['request_sha256'],'adapter_sha256':request['native']['adapter']['sha256'],'source_sha256':request['source']['sha256'],'metadata':{'sampled_frames':len(frames)},'objects':[{'object_id':'obj_0001','label':'person','frames':frames}]}
        if self.change:
            self.change(response)
        return subprocess.CompletedProcess(argv,0,json.dumps(response),'')

    def test_dry_run_and_inspection_are_read_only(self):
        before=self.metadata()
        code,value=invoke('media','adapter','register',*self.options,'--dry-run')
        self.assertEqual(code,0,value)
        self.assertEqual(self.metadata(),before)
        registered=self.register()['data']['adapter']
        self.assertEqual(registered['settings']['class_ids'],[0])
        before=self.metadata()
        for action,extra in [('list',[]),('inspect',['--adapter-id','yolo'])]:
            code,value=invoke('media','adapter',action,'--project',str(self.root),*extra)
            self.assertEqual(code,0,value)
            self.assertEqual(self.metadata(),before)

    def test_registration_requires_local_evidence_native_python_and_valid_settings(self):
        for key,value in [('--evidence','https://invalid.example/proof'),('--evidence',str(self.base/'missing')),('--executable',str(self.base/'python.cmd')),('--model-path','https://invalid.example/model')]:
            args=list(self.options);args[args.index(key)+1]=value
            self.assertNotEqual(invoke('media','adapter','register',*args)[0],0)
        for extra in [('--threads','0'),('--confidence','nan'),('--low-confidence','0.9'),('--class-id','80'),('--max-gap-seconds','0')]:
            self.assertEqual(invoke('media','adapter','register',*self.options,*extra)[0],2)

    def test_model_evidence_and_configuration_tampering_block_inference(self):
        self.register()
        registry_path=self.root/'models/visual-adapters.json'
        original=registry_path.read_bytes()
        for kind in ('model','evidence','config'):
            with self.subTest(kind=kind):
                model_before,proof_before=self.model.read_bytes(),self.proof.read_bytes()
                if kind=='model':self.model.write_bytes(b'changed')
                if kind=='evidence':self.proof.write_bytes(b'changed')
                if kind=='config':
                    value=json.loads(original);value['adapters'][0]['settings']['threads']=8;atomic_write_json(registry_path,value)
                with patch('ai_ad_editor.tracking.subprocess.run',side_effect=self.fake_runner):
                    code,value=self.track('--all-objects')
                self.assertEqual(code,10,value)
                self.assertEqual(self.calls,0)
                self.model.write_bytes(model_before);self.proof.write_bytes(proof_before);registry_path.write_bytes(original)

    def test_native_object_report_is_read_only_for_project_and_has_no_implicit_fallback(self):
        self.register();before=self.metadata()
        with patch('ai_ad_editor.tracking.subprocess.run',side_effect=self.fake_runner):
            code,value=self.track('--all-objects')
        self.assertEqual(code,0,value)
        self.assertEqual(value['data']['result']['engine'],YOLO_ENGINE)
        self.assertEqual(len(value['data']['result']['objects'][0]['frames']),8)
        self.assertEqual(self.metadata(),before)

    def test_worker_integrity_clock_and_bounds_fail_without_mutating_project(self):
        self.register();before=self.metadata()
        changes=[lambda r:r.update(network='enabled'),lambda r:r.update(blocked_network_events=['socket.connect']),lambda r:r.update(adapter_sha256='wrong'),lambda r:r.update(source_sha256='wrong'),lambda r:r.update(request_sha256='wrong'),lambda r:r['metadata'].update(sampled_frames=1),lambda r:r['objects'][0]['frames'][1].update(at_seconds=.13),lambda r:r['objects'][0]['frames'][0].update(width=.9),lambda r:r['objects'].append(copy.deepcopy(r['objects'][0])),lambda r:r.update(objects=[])]
        for change in changes:
            with self.subTest(change=change):
                self.change=change
                with patch('ai_ad_editor.tracking.subprocess.run',side_effect=self.fake_runner):
                    code,value=self.track('--object-id','obj_0001','--clip-id','video','--track-id','track_video_1')
                self.assertEqual(code,6,value)
                self.assertEqual(self.metadata(),before)

    def test_sample_budget_and_selection_are_explicit(self):
        self.register()
        with patch('ai_ad_editor.tracking.subprocess.run',side_effect=self.fake_runner):
            self.assertEqual(self.track()[0],2)
            self.assertEqual(self.track('--all-objects','--max-samples','2')[0],2)
            self.assertEqual(self.track('--all-objects','--step-frames','16')[0],2)
        self.assertEqual(self.calls,0)

    def test_apply_paths_preserve_model_rights_and_binding_source_clock(self):
        self.register()
        with patch('ai_ad_editor.tracking.subprocess.run',side_effect=self.fake_runner):
            code,value=self.track('--object-id','obj_0001','--clip-id','video','--track-id','track_video_1')
            self.assertEqual(code,0,value)
            code,value=invoke('media','track-bind','--project',str(self.root),'--asset-id',self.asset,'--adapter-id','yolo','--object-id','obj_0001','--roi','0,0,1,1','--step-frames','1','--target-clip-id','title','--target-track-id','titles','--apply')
            self.assertEqual(code,0,value)
            self.assertEqual(value['data']['plan']['keyframes'][0]['keyframes'][-1]['at_tick'],78750)
            code,value=invoke('media','reframe','--project',str(self.root),'--asset-id',self.asset,'--adapter-id','yolo','--object-id','obj_0001','--roi','0,0,1,1','--step-frames','1','--clip-id','video','--track-id','track_video_1','--apply')
            self.assertEqual(code,0,value)
        clips=[c for s in self.project()['sequences'] for t in s['tracks'] for c in t['clips']]
        self.assertTrue(all(c.get('rights_dependencies',[{}])[0].get('rights_ref')=='visual_adapter_yolo' for c in clips))
        rights=check_project_rights(self.project(),load_ledger(self.root))
        self.assertFalse(rights['ok'])
        self.assertIn('visual_adapter_yolo',json.dumps(rights))
        self.assertEqual(invoke('validate','--project',str(self.root))[0],0)

    def test_existing_report_and_failed_inference_preserve_project_and_outputs(self):
        self.register()
        target=self.root/'validation/existing.json';target.write_bytes(b'original')
        before=self.metadata()
        with patch('ai_ad_editor.tracking.subprocess.run',side_effect=self.fake_runner):
            code,value=self.track('--object-id','obj_0001','--clip-id','video','--output',str(target))
        self.assertEqual(code,2,value)
        self.assertEqual(target.read_bytes(),b'original')
        self.assertEqual(self.metadata(),before)
        with patch('ai_ad_editor.tracking.subprocess.run',side_effect=subprocess.TimeoutExpired(['worker'],1)):
            code,value=self.track('--all-objects')
        self.assertEqual(code,6,value)
        self.assertEqual(self.metadata(),before)

    def test_registry_follows_snapshot_restore_and_transaction_rollback(self):
        before=self.metadata()
        with patch('ai_ad_editor.cli.save_project',side_effect=OSError('injected registration write failure')):
            code,_=invoke('media','adapter','register',*self.options)
        self.assertNotEqual(code,0)
        self.assertEqual(self.metadata(),before)
        self.register()
        code,value=invoke('project','snapshot','--project',str(self.root),'--label','with-model')
        self.assertEqual(code,0,value)
        snapshot=value['data']['snapshot_id']
        expected=(self.root/'models/visual-adapters.json').read_bytes()
        atomic_write_json(self.root/'models/visual-adapters.json',{'adapters':[]})
        code,value=invoke('project','restore','--project',str(self.root),'--snapshot',snapshot)
        self.assertEqual(code,0,value)
        self.assertEqual(json.loads((self.root/'models/visual-adapters.json').read_bytes()),json.loads(expected))

    def test_native_worker_network_guard_rejects_socket_connect(self):
        worker=Path(__file__).parents[1]/'src/ai_ad_editor/yolo_worker.py'
        program='import runpy,socket\ne=[]\nm=runpy.run_path('+repr(str(worker))+')\nm["install_network_guard"](e)\ntry: socket.create_connection(("127.0.0.1",9),timeout=.1)\nexcept RuntimeError: pass\nelse: raise AssertionError("network not blocked")\nassert e\n'
        value=BASE_RUN([sys.executable,'-I','-B','-X','utf8','-c',program],capture_output=True,text=True)
        self.assertEqual(value.returncode,0,value.stderr)

    def test_restoring_pre_registration_snapshot_removes_new_registry(self):
        registration=self.register()
        snapshot=registration['data']['snapshot']['snapshot_id']
        self.assertTrue((self.root/'models/visual-adapters.json').exists())
        code,value=invoke('project','restore','--project',str(self.root),'--snapshot',snapshot)
        self.assertEqual(code,0,value)
        self.assertFalse((self.root/'models/visual-adapters.json').exists())

    def test_missing_or_mismatched_clip_model_rights_block_publish(self):
        self.register()
        project=self.project()
        clip=project['sequences'][0]['tracks'][0]['clips'][0]
        clip['rights_dependencies']=[{'rights_ref':'visual_adapter_yolo','sha256':'sha256:'+'0'*64}]
        result=check_project_rights(project,load_ledger(self.root))
        self.assertFalse(result['ok'])
        self.assertIn('RIGHTS_HASH_MISMATCH',json.dumps(result))
        clip['rights_dependencies'][0]['rights_ref']='missing_model'
        result=check_project_rights(project,load_ledger(self.root))
        self.assertIn('missing_model',json.dumps(result))

    def test_rotated_non_square_pixel_and_unknown_source_clock_are_rejected(self):
        from ai_ad_editor.media import probe_media
        self.register()
        original=probe_media(self.source)
        for change in [lambda v:v['streams'][0].update(sample_aspect_ratio='4:3'),lambda v:v['streams'][0].update(avg_frame_rate='0/0'),lambda v:v['streams'][0].update(side_data_list=[{'rotation':90}]),lambda v:v['streams'][0].update(start_time='2.0')]:
            altered=copy.deepcopy(original);change(altered)
            with patch('ai_ad_editor.local_vision.probe_media',return_value=altered),patch('ai_ad_editor.tracking.subprocess.run',side_effect=self.fake_runner):
                code,value=self.track('--all-objects')
            self.assertEqual(code,4,value)
        self.assertEqual(self.calls,0)

    def test_model_tracking_apply_requires_ingested_source(self):
        self.register()
        code,value=invoke('media','track','--project',str(self.root),'--input',str(self.source),'--adapter-id','yolo','--object-id','obj_0001','--roi','0,0,1,1','--clip-id','video','--dry-run')
        self.assertEqual(code,2,value)
        self.assertEqual(value['errors'][0]['code'],'VISION_SOURCE_RIGHTS_REQUIRED')

    def test_project_package_preserves_registered_model_metadata_without_weights(self):
        import zipfile
        self.register()
        archive=self.root/'exports/portable.aevpkg.zip'
        code,value=invoke('convert','export','--project',str(self.root),'--output',str(archive),'--target-format','package')
        self.assertEqual(code,0,value)
        with zipfile.ZipFile(archive) as bundle:
            self.assertIn('models/visual-adapters.json',bundle.namelist())
            self.assertFalse(any(name.endswith('.onnx') for name in bundle.namelist()))
        destination=self.base/'restored-package'
        code,value=invoke('convert','import','--input',str(archive),'--output',str(destination))
        self.assertEqual(code,0,value)
        self.assertEqual(load_visual_model_registry(destination)['adapters'][0]['adapter_id'],'yolo')

    def test_native_probe_rejects_network_playlist_protocol(self):
        from ai_ad_editor.media import probe_media
        playlist=self.base/'network.m3u8'
        playlist.write_text('#EXTM3U\n#EXT-X-TARGETDURATION:1\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:1,\nhttps://invalid.example/segment.ts\n#EXT-X-ENDLIST\n',encoding='utf-8')
        with self.assertRaises(AppError) as rejected:
            probe_media(playlist)
        self.assertIn('whitelist',rejected.exception.cause.lower())

    def test_long_dynamic_crop_graph_renders_from_local_file_and_rejects_tampering(self):
        from ai_ad_editor.utils import sha256_file
        project=self.project()
        clip=project['sequences'][0]['tracks'][0]['clips'][0]
        clip['crop']={'unit':'normalized','x':.1,'y':0,'width':.316406,'height':1,'fit':'fill'}
        clip['keyframes']=[{'property':'crop.'+key,'keyframes':[{'at_tick':i*2800,'value':(.1+i*.003 if key=='x' else .316406 if key=='width' else 1 if key=='height' else 0),'interpolation':'linear'} for i in range(32)]} for key in ('x','y','width','height')]
        atomic_write_json(self.root/'project.json',project)
        output=self.root/'renders/long-graph.mp4'
        options=['render','--project',str(self.root),'--output',str(output),'--profile','custom','--width','160','--height','90']
        code,value=invoke(*options,'--dry-run')
        self.assertEqual(code,0,value)
        transport=value['data']['plan']['filter_graph_transport']
        self.assertEqual(transport['mode'],'local-file')
        self.assertGreater(transport['logical_command_utf16_units'],28000)
        self.assertFalse(Path(transport['path']).exists())
        code,value=invoke(*options)
        self.assertEqual(code,0,value)
        manifest=json.loads(Path(value['data']['manifest']).read_text(encoding='utf-8'))
        graph=Path(manifest['filter_graph_transport']['path'])
        self.assertEqual('sha256:'+sha256_file(graph),manifest['filter_graph_transport']['sha256'])
        self.assertIn('-/filter_complex',manifest['command'])
        self.assertEqual(graph.read_text(encoding='utf-8'),manifest['filter_complex'])
        graph.write_text('changed',encoding='utf-8')
        code,value=invoke(*options)
        self.assertEqual(code,6,value)
        self.assertTrue(output.exists())


if __name__=='__main__':
    unittest.main()
