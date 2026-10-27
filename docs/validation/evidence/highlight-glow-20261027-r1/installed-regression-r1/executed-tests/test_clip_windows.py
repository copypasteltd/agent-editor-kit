from __future__ import annotations

import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from ai_ad_editor.cli import main
from ai_ad_editor.clip_windows import apply_operation, slice_clip, validate_window
from ai_ad_editor.edit_planner import interchange_features
from ai_ad_editor.errors import AppError
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.validator import validate_project

ROOT = Path(__file__).resolve().parents[2]
TPS, FPS = 90000, 10


class ClipWindowTests(unittest.TestCase):
    def same_media(self, actual, expected):
        digest=lambda raw:hashlib.sha256(raw).hexdigest()
        self.assertEqual([digest(f) for f in actual[0]],[digest(f) for f in expected[0]])
        self.assertEqual(digest(actual[1]),digest(expected[1]))
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def call(self, *args, expected=0):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(list(map(str, args)))
        result = json.loads(output.getvalue())
        self.assertEqual(code, expected, result)
        return result

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='presentation-window-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'project'
        self.call('project', 'init', self.root)
        source = ROOT/'docs/assets/source-transitions-20261017/source-a.mp4'
        sound = ROOT/'docs/assets/source-transitions-20261017/sound-a.wav'
        self.video = self.call('media','ingest','--project',self.root,'--input',source)['data']['asset']['id']
        self.audio = self.call('media','ingest','--project',self.root,'--input',sound)['data']['asset']['id']
        self.project = json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.project['settings']['canvas'] = {'width':240,'height':136}
        self.project['settings']['timebase']['display_fps'] = {'num':10,'den':1}
        self.seq = self.project['sequences'][0]
        self.sid = self.seq['id']
        self.seq['duration_tick'] = 4*TPS
        self.seq['tracks'][0]['clips'] = [self.clip('v',self.video)]
        self.seq['tracks'][1]['clips'] = [self.clip('a',self.audio)]

    def clip(self, name, aid):
        return {'id':name,'asset_id':aid,'timeline_start_tick':0,'duration_tick':4*TPS,
            'source_in_tick':TPS,'source_out_tick':5*TPS}

    def saved(self, project=None):
        (self.root/'project.json').write_text(json.dumps(project or self.project),encoding='utf-8')

    def pixels_and_samples(self, project):
        sequence = next(s for s in project['sequences'] if s['id']==self.sid)
        inputs, graph, _, _ = build_filter_graph(self.root, project, sequence)
        stem = str(len(list(self.root.glob('raw*'))))
        script, result = self.root/f'raw{stem}.txt', self.root/f'raw{stem}.nut'
        script.write_text(graph,encoding='utf-8')
        command = ['ffmpeg','-v','error','-nostdin','-filter_complex_threads','1',*inputs,
            '-filter_complex_script',str(script),'-map','[vout]','-map','[aout]',
            '-c:v','ffv1','-pix_fmt','bgr0','-c:a','pcm_f32le','-t',str(sequence['duration_tick']/TPS),str(result)]
        run = subprocess.run(command,capture_output=True,timeout=120,cwd=self.root)
        self.assertEqual(run.returncode,0,run.stderr.decode('utf-8','replace'))
        video = subprocess.check_output(['ffmpeg','-v','error','-i',str(result),'-map','0:v','-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
        audio = subprocess.check_output(['ffmpeg','-v','error','-i',str(result),'-map','0:a','-f','f32le','-ar','48000','-ac','2','pipe:1'])
        size=240*136*3
        return [video[i:i+size] for i in range(0,len(video),size)], audio

    def test_repeated_slice_preserves_authored_payload_and_composes_offset(self):
        clip = self.seq['tracks'][0]['clips'][0]
        clip['reverse']=True
        clip['keyframes']=[{'property':'transform.position.x','keyframes':[{'at_tick':0,'value':0},{'at_tick':4*TPS,'value':.2}]}]
        first=slice_clip(clip,TPS,4*TPS,start=0)
        second=slice_clip(first,TPS,2*TPS,start=0)
        self.assertEqual(second['presentation_window']['offset_tick'],2*TPS)
        self.assertEqual(second['presentation_window']['authored_duration_tick'],4*TPS)
        for field in ('source_in_tick','source_out_tick','keyframes','reverse'):
            self.assertEqual(second[field],clip[field])
        self.assertEqual(clip['duration_tick'],4*TPS)

    def test_strict_window_ranges(self):
        clip=self.seq['tracks'][0]['clips'][0]
        for first,end in [(True,90000),(0,1.5),(-1,90000),(0,5*TPS),(TPS,TPS)]:
            with self.subTest(first=first,end=end),self.assertRaises(AppError):
                slice_clip(clip,first,end)
        c=slice_clip(clip,0,TPS)
        for field,value in [('version',True),('offset_tick',4*TPS),('authored_duration_tick',False)]:
            bad=copy.deepcopy(c);bad['presentation_window'][field]=value
            with self.assertRaises(AppError):validate_window(bad)

    def test_split_is_global_id_safe_and_lock_atomic(self):
        original=copy.deepcopy(self.project)
        for patch in [{'left_id':'a'},{'at_tick':True}]:
            with self.assertRaises(AppError):
                apply_operation(self.project,self.sid,{'op':'split_clip','clip_id':'v','at_tick':TPS,**patch})
        self.seq['tracks'][0]['locked']=True
        with self.assertRaises(AppError):
            apply_operation(self.project,self.sid,{'op':'split_clip','clip_id':'v','at_tick':TPS})
        original['sequences'][0]['tracks'][0]['locked']=True
        self.assertEqual(self.project,original)

    def test_internal_ripple_deletes_middle_not_tail(self):
        candidate,_=apply_operation(self.project,self.sid,{'op':'ripple_delete','at_tick':TPS,'duration_tick':TPS})
        for track in candidate['sequences'][0]['tracks']:
            self.assertEqual(len(track['clips']),2)
            left,right=track['clips']
            self.assertEqual(left['duration_tick'],TPS)
            self.assertEqual(right['timeline_start_tick'],TPS)
            self.assertEqual(right['presentation_window']['offset_tick'],2*TPS)
            self.assertEqual(right['duration_tick'],2*TPS)
        self.assertEqual(candidate['sequences'][0]['duration_tick'],3*TPS)
        self.assertNotEqual(candidate,self.project)

    def test_track_scoped_ripple_does_not_truncate_unselected_tracks(self):
        candidate,_=apply_operation(self.project,self.sid,{'op':'ripple_delete','track_id':self.seq['tracks'][0]['id'],'at_tick':TPS,'duration_tick':TPS})
        self.assertEqual(candidate['sequences'][0]['duration_tick'],4*TPS)
        self.seq['tracks'][0]['clips'][0]['link_id']='link'
        self.seq['tracks'][1]['clips'][0]['link_id']='link'
        with self.assertRaises(AppError):
            apply_operation(self.project,self.sid,{'op':'ripple_delete','track_id':self.seq['tracks'][0]['id'],'at_tick':TPS,'duration_tick':TPS})

    def test_ripple_boundary_crossing_removes_correct_head(self):
        for track in self.seq['tracks']:
            track['clips'][0]['timeline_start_tick']=TPS
        self.seq['duration_tick']=5*TPS
        candidate,_=apply_operation(self.project,self.sid,{'op':'ripple_delete','at_tick':0,'duration_tick':2*TPS})
        right=candidate['sequences'][0]['tracks'][0]['clips'][0]
        self.assertEqual(right['presentation_window']['offset_tick'],TPS)
        self.assertEqual(right['duration_tick'],3*TPS)

    def test_window_validation_keeps_author_keyframes_outside_visible_range(self):
        c=self.seq['tracks'][0]['clips'][0]
        c['keyframes']=[{'property':'transform.position.x','keyframes':[{'at_tick':0,'value':0,'interpolation':'linear'},{'at_tick':4*TPS,'value':.2,'interpolation':'linear'}]}]
        candidate,_=apply_operation(self.project,self.sid,{'op':'trim_clip','clip_id':'v','start_tick':TPS,'end_tick':2*TPS,'timeline_start_tick':0})
        result=validate_project(self.root,candidate,strict_rights=False)
        self.assertTrue(result['ok'],result)
        self.assertIn('clip.presentation_window',interchange_features(candidate))

    def test_cli_batch_dry_run_and_rejected_cut_do_not_write(self):
        self.saved()
        original=(self.root/'project.json').read_bytes()
        request=self.root/'cuts.json'
        request.write_text(json.dumps({'operations':[{'op':'split_clip','clip_id':'v','at_tick':2*TPS}]}),encoding='utf-8')
        self.call('timeline','compose','--project',self.root,'--input',request,'--dry-run')
        self.assertEqual((self.root/'project.json').read_bytes(),original)
        request.write_text(json.dumps({'operations':[{'op':'split_clip','clip_id':'v','at_tick':TPS},{'op':'trim_clip','clip_id':'missing'}]}),encoding='utf-8')
        self.call('timeline','compose','--project',self.root,'--input',request,expected=2)
        self.assertEqual((self.root/'project.json').read_bytes(),original)

    def test_split_render_is_identical_to_original_frames_and_processed_audio(self):
        # Full interval processing before cutting avoids restarting audio effects
        # or easing at the right-hand edit. This is a counterfactual render oracle.
        for track in self.seq['tracks']:
            clip=track['clips'][0]
            clip['reverse']=True
        self.seq['tracks'][0]['clips'][0]['keyframes']=[{'property':'transform.position.x','keyframes':[
            {'at_tick':0,'value':.5,'interpolation':'ease_in_out'},{'at_tick':4*TPS,'value':.65,'interpolation':'linear'}]}]
        self.seq['tracks'][1]['clips'][0]['audio']={'fade_in':.7,'fade_out':.8,'volume':.8}
        before=self.pixels_and_samples(self.project)
        neutral=copy.deepcopy(self.project)
        neutral['sequences'][0]['tracks'][0]['clips'][0].pop('keyframes')
        neutral_frames,_=self.pixels_and_samples(neutral)
        self.assertNotEqual(hashlib.sha256(before[0][20]).hexdigest(),hashlib.sha256(neutral_frames[20]).hexdigest())
        candidate=self.project
        for cid in ('v','a'):
            candidate,_=apply_operation(candidate,self.sid,{'op':'split_clip','clip_id':cid,'at_tick':2*TPS})
        after=self.pixels_and_samples(candidate)
        self.same_media(after,before)

    def test_curved_reverse_ripple_matches_removed_original_range(self):
        for track in self.seq['tracks']:
            clip=track['clips'][0];clip['reverse']=True
            clip['speed_curve']={'keyframes':[{'at_tick':0,'speed':.7,'interpolation':'ease_in_out'},
                {'at_tick':4*TPS,'speed':1.3}]}
        frames,samples=self.pixels_and_samples(self.project)
        candidate,_=apply_operation(self.project,self.sid,{'op':'ripple_delete','at_tick':TPS,'duration_tick':TPS})
        newframes,newsamples=self.pixels_and_samples(candidate)
        self.assertEqual(newframes,frames[:10]+frames[20:])
        self.assertEqual(newsamples,samples[:48000*8]+samples[96000*8:])

    def test_freeze_window_cut_inside_held_picture_and_silence(self):
        for track in self.seq['tracks']:
            clip=track['clips'][0]
            clip['freeze']={'at_tick':TPS,'duration_tick':TPS,'audio_mode':'silence'}
            clip['duration_tick']=5*TPS
        self.seq['duration_tick']=5*TPS
        frames,samples=self.pixels_and_samples(self.project)
        candidate=self.project
        for cid in ('v','a'):
            candidate,_=apply_operation(candidate,self.sid,{'op':'trim_clip','clip_id':cid,'start_tick':int(1.5*TPS),'end_tick':int(3.5*TPS),'timeline_start_tick':0})
        candidate['sequences'][0]['duration_tick']=2*TPS
        newframes,newsamples=self.pixels_and_samples(candidate)
        self.assertEqual(newframes,frames[15:35])
        self.assertEqual(newsamples,samples[72000*8:168000*8])

    def test_insert_inside_clip_renders_black_and_silence_gap(self):
        frames,samples=self.pixels_and_samples(self.project)
        candidate,_=apply_operation(self.project,self.sid,{'op':'ripple_insert','at_tick':TPS,'duration_tick':TPS})
        newframes,newsamples=self.pixels_and_samples(candidate)
        self.assertEqual(newframes[:10],frames[:10])
        self.assertEqual(newframes[20:],frames[10:])
        self.assertTrue(all(max(f)==0 for f in newframes[10:20]))
        self.assertEqual(newsamples,samples[:48000*8]+b'\0'*(48000*8)+samples[48000*8:])

    def test_nested_window_sequence_preserves_source_clock(self):
        child=copy.deepcopy(self.seq);child['id']='child'
        for i,t in enumerate(child['tracks']):
            t['id']=f'child_track{i}'
            for c in t['clips']:c['id']='child_'+c['id']
        for c in [child['tracks'][0]['clips'][0],child['tracks'][1]['clips'][0]]:
            c['reverse']=True
        self.project['sequences'].append(child)
        self.seq['tracks'][0]['clips']=[{'id':'container','sequence_id':'child','timeline_start_tick':0,
            'duration_tick':4*TPS,'source_in_tick':0,'source_out_tick':4*TPS}]
        self.seq['tracks'][1]['clips']=[]
        frames,samples=self.pixels_and_samples(self.project)
        candidate,_=apply_operation(self.project,'child',{'op':'ripple_delete','at_tick':TPS,'duration_tick':TPS})
        root=next(s for s in candidate['sequences'] if s['id']==self.sid)
        root['duration_tick']=3*TPS
        root['tracks'][0]['clips'][0]['duration_tick']=3*TPS
        root['tracks'][0]['clips'][0]['source_out_tick']=3*TPS
        newframes,newsamples=self.pixels_and_samples(candidate)
        self.assertEqual(newframes,frames[:10]+frames[20:])
        self.assertEqual(newsamples,samples[:48000*8]+samples[96000*8:])

    def test_trim_container_keeps_processed_child_bus(self):
        child=copy.deepcopy(self.seq);child['id']='child'
        for i,t in enumerate(child['tracks']):
            t['id']=f'child_track{i}'
            for c in t['clips']:c['id']='child_'+c['id']
        child['tracks'][1]['audio']={'volume':.7,'pan':-.1}
        self.project['sequences'].append(child)
        self.seq['tracks'][0]['clips']=[{'id':'container','sequence_id':'child','timeline_start_tick':0,
            'duration_tick':4*TPS,'source_in_tick':0,'source_out_tick':4*TPS,'audio':{'fade_in':.8,'fade_out':.7}}]
        self.seq['tracks'][1]['clips']=[]
        frames,samples=self.pixels_and_samples(self.project)
        candidate,_=apply_operation(self.project,self.sid,{'op':'trim_clip','clip_id':'container',
            'start_tick':TPS,'end_tick':3*TPS,'timeline_start_tick':0})
        candidate['sequences'][0]['duration_tick']=2*TPS
        got=self.pixels_and_samples(candidate)
        self.same_media(got,(frames[10:30],samples[48000*8:144000*8]))

    def test_subtitle_file_split_keeps_original_cues_and_animation(self):
        font=ROOT/'docs/assets/fragments-20261018/agent-grid-cc0.ttf'
        captions=self.root/'captions.srt'
        captions.write_text('1\n00:00:01,000 --> 00:00:03,000\nCTA\n',encoding='utf-8')
        self.saved()
        fid=self.call('media','ingest','--project',self.root,'--input',font)['data']['asset']['id']
        aid=self.call('media','ingest','--project',self.root,'--input',captions)['data']['asset']['id']
        self.project=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.seq=self.project['sequences'][0]
        asset=next(a for a in self.project['assets'] if a['id']==fid)
        self.seq['tracks'].append({'id':'subtitles','kind':'subtitle','order':2,'clips':[
            {'id':'sub','asset_id':aid,'timeline_start_tick':0,'duration_tick':4*TPS,
             'source_in_tick':0,'source_out_tick':4*TPS,'subtitle':{'style':{'fontfile':asset['uri'],
                'font_asset_id':fid,'font_size':24,'x':.1,'y':.6},'animation':{'type':'slide_up','duration':.8}}}]})
        before=self.pixels_and_samples(self.project)
        candidate,_=apply_operation(self.project,self.sid,{'op':'split_clip','clip_id':'sub','at_tick':2*TPS})
        self.same_media(self.pixels_and_samples(candidate),before)

    def test_effect_keyframes_do_not_restart_after_trim(self):
        self.seq['tracks'][0]['clips'][0]['effects']=[{'type':'brightness','parameters':{'brightness':0},'keyframes':[
            {'property':'brightness','keyframes':[{'at_tick':0,'value':0,'interpolation':'ease_in_out'},
                {'at_tick':4*TPS,'value':.3,'interpolation':'linear'}]}]}]
        frames,samples=self.pixels_and_samples(self.project)
        neutral=copy.deepcopy(self.project)
        neutral['sequences'][0]['tracks'][0]['clips'][0].pop('effects')
        neutral_frames,_=self.pixels_and_samples(neutral)
        self.assertNotEqual(hashlib.sha256(frames[20]).hexdigest(),hashlib.sha256(neutral_frames[20]).hexdigest())
        candidate,_=apply_operation(self.project,self.sid,{'op':'ripple_delete','at_tick':TPS,'duration_tick':TPS})
        self.same_media(self.pixels_and_samples(candidate),(frames[:10]+frames[20:],samples[:48000*8]+samples[96000*8:]))

    def test_transition_reference_gate_and_whole_project_unchanged(self):
        self.seq['source_transitions']=[{'id':'x','from_clip_id':'v','to_clip_id':'other','audio_pairs':[]}]
        original=copy.deepcopy(self.project)
        with self.assertRaises(AppError) as caught:
            apply_operation(self.project,self.sid,{'op':'split_clip','clip_id':'v','at_tick':TPS})
        self.assertEqual(caught.exception.code,'CLIP_WINDOW_TRANSITION_CONFLICT')
        self.assertEqual(original,self.project)

    def test_null_window_is_rejected_without_optional_schema(self):
        c=self.seq['tracks'][0]['clips'][0];c['presentation_window']=None
        with self.assertRaises(AppError):validate_window(c)

    def test_direct_window_budget_rejects_before_building_child_graph(self):
        c=self.seq['tracks'][0]['clips'][0]
        self.seq['tracks'][0]['clips']=[slice_clip(c,0,TPS,clip_id=f'v{i}') for i in range(65)]
        with self.assertRaises(AppError) as caught:
            build_filter_graph(self.root,self.project,self.seq)
        self.assertEqual(caught.exception.code,'CLIP_WINDOW_BUDGET_EXCEEDED')

    def test_update_window_payload_keeps_original_animation_endpoint(self):
        c=self.seq['tracks'][0]['clips'][0]
        c['keyframes']=[{'property':'transform.position.x','keyframes':[{'at_tick':0,'value':0,'interpolation':'linear'},
            {'at_tick':4*TPS,'value':.2,'interpolation':'linear'}]}]
        candidate,_=apply_operation(self.project,self.sid,{'op':'trim_clip','clip_id':'v','end_tick':TPS})
        self.saved(candidate)
        req=self.root/'patch.json'
        req.write_text(json.dumps({'operations':[{'op':'update_clip','clip_id':'v','patch':{'transform':{'x':.1}}}]}),encoding='utf-8')
        self.call('timeline','compose','--project',self.root,'--input',req)
        result=json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(result['sequences'][0]['tracks'][0]['clips'][0]['keyframes'][0]['keyframes'][-1]['at_tick'],4*TPS)

    def test_delete_entire_sequence_keeps_valid_empty_one_tick_project(self):
        candidate,_=apply_operation(self.project,self.sid,{'op':'ripple_delete','at_tick':0,'duration_tick':4*TPS})
        self.assertEqual(candidate['sequences'][0]['duration_tick'],1)
        self.assertTrue(all(not t['clips'] for t in candidate['sequences'][0]['tracks']))
        self.assertTrue(validate_project(self.root,candidate,strict_rights=False)['ok'])

    def test_unknown_request_field_rejects_without_changing_project(self):
        with self.assertRaises(AppError):
            apply_operation(self.project,self.sid,{'op':'trim_clip','clip_id':'v','stop_tick':TPS})
        self.assertNotIn('presentation_window',self.seq['tracks'][0]['clips'][0])

    def test_insert_past_end_preserves_complete_requested_gap(self):
        candidate,_=apply_operation(self.project,self.sid,{'op':'ripple_insert','at_tick':5*TPS,'duration_tick':TPS})
        self.assertEqual(candidate['sequences'][0]['duration_tick'],6*TPS)

    def test_neighbor_legacy_transition_rejects_instead_of_disappearing(self):
        self.seq['tracks'][0]['clips'][0]['transition_out']={'type':'wipe','duration':.5}
        with self.assertRaises(AppError) as caught:
            apply_operation(self.project,self.sid,{'op':'split_clip','clip_id':'v','at_tick':TPS})
        self.assertEqual(caught.exception.code,'CLIP_WINDOW_TRANSITION_CONFLICT')

    def test_smart_cut_source_analysis_cannot_reinterpret_window(self):
        from ai_ad_editor.smart_cut import slice_clip as smart_slice
        c=slice_clip(self.seq['tracks'][0]['clips'][0],TPS,2*TPS)
        with self.assertRaises(AppError) as caught:
            smart_slice(c,[{'start_seconds':0,'end_seconds':1}],ticks_per_second=TPS)
        self.assertEqual(caught.exception.code,'SMART_CUT_PRESENTATION_WINDOW_UNSUPPORTED')

    def test_motion_preset_uses_visible_range_on_original_author_clock(self):
        from ai_ad_editor.cli import _apply_motion_preset
        c=slice_clip(self.seq['tracks'][0]['clips'][0],TPS,2*TPS,start=0)
        _apply_motion_preset(c,{'preset':'zoom_in'})
        times=[k['at_tick'] for t in c['keyframes'] for k in t['keyframes']]
        self.assertEqual(min(times),TPS)
        self.assertEqual(max(times),2*TPS)

    def test_partial_window_curve_duration_edit_rejects_atomically(self):
        candidate,_=apply_operation(self.project,self.sid,{'op':'trim_clip','clip_id':'v','start_tick':TPS,'end_tick':2*TPS})
        self.saved(candidate);original=(self.root/'project.json').read_bytes()
        req=self.root/'curve.json';req.write_text(json.dumps({'operations':[{'op':'set_clip_speed_curve','clip_id':'v',
            'speed_curve':{'keyframes':[{'at_tick':0,'speed':2}]}}]}),encoding='utf-8')
        result=self.call('timeline','compose','--project',self.root,'--input',req,expected=2)
        self.assertEqual(result['errors'][0]['code'],'CLIP_WINDOW_AUTHOR_EDIT_REQUIRES_FULL_TAKE')
        self.assertEqual(original,(self.root/'project.json').read_bytes())

    def test_tracking_source_cannot_reinterpret_window(self):
        from ai_ad_editor.bindings import find_source
        c=self.seq['tracks'][0]['clips'][0]
        self.seq['tracks'][0]['clips'][0]=slice_clip(c,TPS,2*TPS)
        with self.assertRaises(AppError):
            find_source(self.seq,{'source_track_id':self.seq['tracks'][0]['id'],'source_clip_id':'v','asset_id':self.video})

    def test_partial_window_reverse_rejects_instead_of_selecting_other_source(self):
        candidate,_=apply_operation(self.project,self.sid,{'op':'trim_clip','clip_id':'v','end_tick':TPS})
        self.saved(candidate);original=(self.root/'project.json').read_bytes()
        req=self.root/'reverse.json';req.write_text(json.dumps({'operations':[{'op':'reverse_clip','clip_id':'v','enabled':True}]}),encoding='utf-8')
        self.call('timeline','compose','--project',self.root,'--input',req,expected=2)
        self.assertEqual(original,(self.root/'project.json').read_bytes())

    def test_isolated_window_preserves_original_opaque_contain_bars(self):
        v=self.seq['tracks'][0]['clips'][0]
        background=copy.deepcopy(v);background['id']='background'
        background['source_in_tick']=0;background['source_out_tick']=4*TPS
        self.seq['tracks'].append({'id':'back','kind':'video','order':-1,'clips':[background]})
        v['crop']={'x':0,'y':0,'width':120,'height':136,'fit':'fit'}
        self.assertTrue(validate_project(self.root,self.project,strict_rights=False)['ok'])
        before=self.pixels_and_samples(self.project)
        project,_=apply_operation(self.project,self.sid,{'op':'split_clip','clip_id':'v','at_tick':2*TPS})
        self.same_media(self.pixels_and_samples(project),before)


if __name__ == '__main__':
    unittest.main()
