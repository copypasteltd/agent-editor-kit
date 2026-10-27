"""Timeline output windows against complete graph pixels and full decoded PCM."""
from __future__ import annotations

import contextlib
import copy
from fractions import Fraction
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from ai_ad_editor import cli, preview
from ai_ad_editor.artifact_locks import verification_scope
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project, save_project, project_file
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor.utils import atomic_write_json


def invoke(*args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = cli.main([str(v) for v in args])
    return code, json.loads(output.getvalue())


class PreviewCase(unittest.TestCase):
    def setUp(self):
        directory = Path(__file__).resolve().parents[1]/'.runtime'
        directory.mkdir(exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='preview-test-',dir=directory)
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name)
        self.root,self.project = create_project(self.workspace/'project')
        self.project['settings']['canvas'].update(width=64,height=64)
        self.project['settings']['timebase']['display_fps']={'num':8,'den':1}
        self.sequence=self.project['sequences'][0]
        self.sequence['duration_tick']=90000
        self.runtime = self.workspace/'runtime.fixture'
        self.runtime.write_bytes(b'runtime-a')
        runtime_patch=patch.object(preview,'_runtime_paths',return_value={self.runtime})
        runtime_patch.start();self.addCleanup(runtime_patch.stop)
        self.persist()

    def persist(self):
        save_project(self.root,self.project)

    def request(self,start=0,end=8,mode='range',**kwargs):
        return preview.plan(self.project,self.sequence,start_frame=start,end_frame=end,mode=mode,**kwargs)

    def execute(self,start=0,end=8,mode='range',**kwargs):
        return preview.preview_project(self.root,self.project,self.sequence,request=self.request(start,end,mode),**kwargs)


class PreviewContractTests(PreviewCase):
    def test_half_open_ntsc_partial_last_frame_has_exact_sample_endpoint(self):
        self.project['settings']['timebase']['display_fps']={'num':30000,'den':1001}
        self.sequence['duration_tick']=90001
        value=self.request(29,30)
        self.assertEqual(value['audio_start_sample_48000'],46447)
        self.assertEqual(value['audio_end_sample_48000'],48001)
        self.assertEqual(value['author_end_seconds'],'90001/90000')

    def test_bounds_types_even_height_and_working_budget_reject_before_writes(self):
        for start,end,kwargs in [(-1,1,{}),(0,9,{}),(1,1,{}),(True,2,{}),(0,1,{'height':65}),(0,1,{'budget_mib':0})]:
            with self.assertRaises(AppError):self.request(start,end,**kwargs)
        self.sequence['duration_tick']=90000*200
        self.project['settings']['canvas'].update(width=3840,height=2160)
        with self.assertRaises(AppError):self.request(0,1000,height=2160,budget_mib=8)
        self.assertFalse(preview.cache_root(self.root).exists())

    def test_scale_after_composite_preserves_aspect_without_upscaling(self):
        self.project['settings']['canvas'].update(width=1920,height=1080)
        value=self.request(0,1,height=360)
        self.assertEqual((value['width'],value['height']),(640,360))
        self.project['settings']['canvas'].update(width=67,height=65)
        value=self.request(0,1,height=1080)
        self.assertEqual((value['width'],value['height']),(66,64))

    def test_same_size_and_restored_mtime_source_and_runtime_change_identity(self):
        source=self.root/'assets/source.raw';source.write_bytes(b'source-a')
        self.project['assets']=[{'id':'a','kind':'image','uri':'assets/source.raw'}]
        def capture():
            with verification_scope():return preview.digest(preview.identity(self.root,self.project,self.sequence,self.request(),None))
        before=capture();stamp=source.stat()
        source.write_bytes(b'source-b');os.utime(source,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        after=capture();self.assertNotEqual(before,after)
        stamp=self.runtime.stat();self.runtime.write_bytes(b'runtime-b');os.utime(self.runtime,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
        self.assertNotEqual(after,capture())

    def test_dry_run_does_not_compile_or_make_cache(self):
        with patch.object(preview,'build_filter_graph',side_effect=AssertionError('compile')):
            result=self.execute(dry_run=True)
        self.assertEqual(result['status'],'planned');self.assertFalse(result['cache_hit'])
        self.assertFalse(preview.cache_root(self.root).exists())

    def test_preexisting_cancel_prevents_compilation_and_publication(self):
        marker=self.root/'cancel';marker.touch()
        with patch.object(preview,'build_filter_graph',side_effect=AssertionError('compile')):
            with self.assertRaises(AppError) as caught:self.execute(cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED')
        self.assertFalse(preview.cache_root(self.root).exists())

    def test_stochastic_strings_and_external_subtitle_disable_cache(self):
        self.assertTrue(preview._cacheable({'effects':['film-grain']},['nut']))
        self.assertTrue(preview._cacheable({'subtitle':{'asset_uri':'a.srt'}},['nut']))
        self.assertTrue(preview._cacheable({},['hls']))

    def test_junction_cache_never_prunes_external_files(self):
        outside=self.workspace/'outside';outside.mkdir();sentinel=outside/'keep';sentinel.write_text('keep')
        base=self.root/'cache';base.mkdir(exist_ok=True)
        link=base/'timeline-previews'
        result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(outside)],capture_output=True,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.assertEqual(result.returncode,0,result.stderr)
        try:
            with self.assertRaises(AppError):preview.cache_prune(self.root)
            self.assertEqual(sentinel.read_text(),'keep')
        finally:os.rmdir(link)


class PreviewPixelTests(PreviewCase):
    def setUp(self):
        super().setUp()
        image=self.workspace/'source.png'
        raw=bytes(c for y in range(64) for x in range(64) for c in ((x*17)%256,(y*19)%256,95,(x+y)%256))
        Image.frombytes('RGBA',(64,64),raw).save(image)
        code,result=invoke('media','ingest','--project',self.root,'--input',image,'--asset-id','picture')
        self.assertEqual(code,0,result)
        self.project=load_project(self.root)[1];self.sequence=self.project['sequences'][0]
        self.sequence['duration_tick']=90000
        self.sequence['tracks'][0]['clips']=[{'id':'picture_clip','asset_id':'picture','timeline_start_tick':0,
            'duration_tick':90000,'source_in_tick':0,'source_out_tick':90000,
            'effects':[{'type':'exposure','keyframes':[{'property':'exposure','keyframes':[
                {'at_tick':0,'value':0,'interpolation':'linear'},{'at_tick':90000,'value':1,'interpolation':'linear'}]}]}]}]
        audio=self.workspace/'tone.wav'
        self.command(['-f','lavfi','-i','sine=frequency=733:sample_rate=48000:duration=1.1','-ac','2','-c:a','pcm_f32le',str(audio)])
        code,result=invoke('media','ingest','--project',self.root,'--input',audio,'--asset-id','sound')
        self.assertEqual(code,0,result)
        assets=load_project(self.root)[1]['assets'];self.project['assets']=assets
        self.sequence['tracks'][1]['clips']=[{'id':'sound_clip','asset_id':'sound','timeline_start_tick':0,
            'duration_tick':90000,'source_in_tick':0,'source_out_tick':90000,
            'audio':{'gain_db':-3,'fade_in_tick':22500}}]
        self.persist()

    def command(self,args):
        result=subprocess.run([ffmpeg_path(),'-v','error','-y','-filter_complex_threads','1',*map(str,args)],capture_output=True,cwd=self.root,timeout=90)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'));return result.stdout

    def reference(self):
        inputs,graph,_,_=build_filter_graph(self.root,copy.deepcopy(self.project),self.sequence)
        path=self.root/'full.nut'
        script=self.root/'reference.ffgraph';script.write_text(graph,encoding='utf8')
        fps=self.project['settings']['timebase']['display_fps'];rate=Fraction(fps['num'],fps['den'])
        duration=Fraction(self.sequence['duration_tick'],90000)
        self.command([*inputs,'-/filter_complex',script,'-map','[vout]','-map','[aout]',
            '-t',f'{float(Fraction(math.ceil(duration*rate),1)/rate):.9f}',
            '-c:v','ffv1','-pix_fmt','bgra','-c:a','pcm_f32le',path])
        return self.decode(path),self.decode(path,audio=True)

    def decode(self,path,audio=False):
        return self.command(['-i',path,*(['-vn','-f','f32le','-acodec','pcm_f32le'] if audio else ['-an','-f','rawvideo','-pix_fmt','rgba']), 'pipe:1'])

    def test_range_pixels_and_every_pcm_sample_match_full_graph(self):
        video,audio=self.reference();result=self.execute(2,6)
        self.assertEqual(self.decode(result['master']),video[2*64*64*4:6*64*64*4])
        self.assertEqual(self.decode(result['master'],audio=True),audio[12000*8:36000*8])
        self.assertEqual(result['verified_clock']['decoded_video_frames'],4)
        self.assertEqual(result['verified_clock']['decoded_pcm_samples_48000'],24000)

    def test_frame_png_is_actual_animated_author_frame_not_source_thumbnail(self):
        video,_=self.reference();result=self.execute(5,6,'frame')
        self.assertEqual(Image.open(result['path']).convert('RGBA').tobytes(),video[5*64*64*4:6*64*64*4])
        self.assertNotEqual(video[:64*64*4],video[5*64*64*4:6*64*64*4])

    def test_author_transparent_output_retains_nontrivial_alpha(self):
        self.project['settings']['output']={'container':'webm','video':{'codec':'libvpx-vp9','crf':0,'pixel_format':'yuva420p'},'audio':{'codec':'libopus'}}
        self.persist();video,audio=self.reference();result=self.execute(2,6)
        actual=self.decode(result['master']);self.assertEqual(actual,video[2*64*64*4:6*64*64*4])
        self.assertGreater(len(set(actual[3::4])),2)
        self.assertEqual(self.decode(result['master'],audio=True),audio[12000*8:36000*8])

    def test_cache_hit_runs_no_graph_probe_encoder_and_keeps_author_bytes(self):
        before=project_file(self.root).read_bytes();first=self.execute(3,4,'frame')
        with patch.object(preview,'build_filter_graph',side_effect=AssertionError('graph')),patch.object(preview,'run_process',side_effect=AssertionError('process')),patch.object(preview,'probe_media',side_effect=AssertionError('probe')):
            second=self.execute(3,4,'frame')
        self.assertFalse(first['cache_hit']);self.assertTrue(second['cache_hit'])
        self.assertEqual(first['cache_key'],second['cache_key']);self.assertEqual(before,project_file(self.root).read_bytes())

    def test_all_direct_lut_aliases_invalidate_after_equal_size_mtime_change(self):
        lut=self.root/'assets/preview-look.cube'
        original='LUT_3D_SIZE 2\n'+''.join(f'{r} {g} {b}\n' for b in (0,1) for g in (0,1) for r in (0,1))
        changed='LUT_3D_SIZE 2\n'+''.join(f'{1-r} {g} {b}\n' for b in (0,1) for g in (0,1) for r in (0,1))
        for alias in ('path','file','lut'):
            with self.subTest(alias=alias):
                lut.write_text(original,encoding='ascii',newline='\n');stamp=lut.stat()
                self.sequence['tracks'][0]['clips'][0]['effects']=[{'type':'lut3d','parameters':{alias:'assets/preview-look.cube','intensity':1}}]
                self.persist();first=self.execute(3,4,'frame',output=self.root/'previews'/(alias+'-original'))
                before=Image.open(first['path']).convert('RGBA').tobytes()
                self.assertTrue(self.execute(3,4,'frame')['cache_hit'])
                lut.write_text(changed,encoding='ascii',newline='\n');os.utime(lut,ns=(stamp.st_atime_ns,stamp.st_mtime_ns))
                self.assertEqual(lut.stat().st_size,len(original));self.assertEqual(lut.stat().st_mtime_ns,stamp.st_mtime_ns)
                current=self.execute(3,4,'frame')
                self.assertFalse(current['cache_hit']);self.assertNotEqual(current['cache_key'],first['cache_key'])
                pixels=Image.open(current['path']).convert('RGBA').tobytes();self.assertNotEqual(pixels,before)
                reference,_=self.reference();self.assertEqual(pixels,reference[3*64*64*4:4*64*64*4])

    def test_new_output_export_survives_cache_pruning(self):
        target=self.root/'previews/export'
        result=self.execute(2,4,output=target)
        expected=self.decode(result['master']);preview.cache_prune(self.root)
        self.assertEqual(preview.cache_list(self.root)['entries'],[])
        self.assertEqual(self.decode(result['master']),expected)
        with self.assertRaises(AppError):self.execute(2,4,output=target)

    def test_receipt_and_artifact_corruption_reject_without_overwrite(self):
        for artifact in (False,True):
            result=self.execute(0,1,'frame');path=Path(result['path']);manifest=Path(result['manifest'])
            if artifact:path.write_bytes(b'broken-png')
            else:
                value=json.loads(manifest.read_bytes());value['quality_accepted']=True;atomic_write_json(manifest,value)
            with self.assertRaises(AppError) as caught:self.execute(0,1,'frame')
            self.assertEqual(caught.exception.code,'PREVIEW_CACHE_CORRUPT')
            preview.cache_prune(self.root)

    def test_cancel_after_compile_removes_staging_and_output(self):
        marker=self.root/'cancel';original=preview.build_filter_graph
        def compile_then_cancel(*args,**kwargs):
            result=original(*args,**kwargs);marker.touch();return result
        target=self.root/'previews/cancelled'
        with patch.object(preview,'build_filter_graph',side_effect=compile_then_cancel):
            with self.assertRaises(AppError) as caught:self.execute(output=target,cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertFalse(target.exists())
        self.assertEqual(preview.cache_list(self.root)['entries'],[])

    def test_export_copy_failure_keeps_verified_cache_and_no_partial_directory(self):
        self.execute(0,1,'frame')
        target=self.root/'previews/copy-failed'
        with patch.object(preview.shutil,'copyfile',side_effect=OSError('simulated copy failure')):
            with self.assertRaises(AppError) as caught:self.execute(0,1,'frame',output=target)
        self.assertEqual(caught.exception.code,'PREVIEW_EXPORT_FAILED')
        self.assertFalse(target.exists());self.assertFalse(list(target.parent.glob('.tmp-*')))
        self.assertTrue(self.execute(0,1,'frame')['cache_hit'])

    def test_pruning_protects_current_project_asset_reference(self):
        result=self.execute(0,1,'frame')
        asset=next(v for v in self.project['assets'] if v['id']=='picture')
        asset['uri']=Path(result['path']).relative_to(self.root).as_posix()
        asset['sha256']=preview.artifact_digest(Path(result['path']))['sha256'];self.persist()
        pruned=preview.cache_prune(self.root)
        self.assertEqual(pruned['protected_reference_keys'],[result['cache_key']])
        self.assertEqual(pruned['removed'],[]);self.assertTrue(Path(result['path']).exists())

    def test_interval_adjustment_after_animation_matches_full_graph(self):
        self.project['settings']['adjustments']=[{'id':'interval','start_tick':22500,'duration_tick':45000,
            'effects':[{'type':'color_temperature','parameters':{'temperature':7000}}]}]
        self.persist();video,audio=self.reference();result=self.execute(1,7)
        self.assertEqual(self.decode(result['master']),video[64*64*4:7*64*64*4])
        self.assertEqual(self.decode(result['master'],audio=True),audio[6000*8:42000*8])

    def test_ntsc_partial_last_frame_matches_full_float_pcm(self):
        self.project['settings']['timebase']['display_fps']={'num':30000,'den':1001}
        self.sequence['duration_tick']=90001;self.persist()
        video,audio=self.reference();result=self.execute(29,30)
        self.assertEqual(self.decode(result['master']),video[29*64*64*4:30*64*64*4])
        self.assertEqual(self.decode(result['master'],audio=True),audio[46447*8:48001*8])

    def test_nested_reverse_and_interval_effects_keep_full_author_clock(self):
        child=copy.deepcopy(self.sequence);child['id']='child'
        self.project['sequences'].append(child)
        self.sequence['tracks'][0]['clips']=[{'id':'nested','sequence_id':'child','timeline_start_tick':0,
            'duration_tick':90000,'source_in_tick':0,'source_out_tick':90000,'reverse':True}]
        self.sequence['tracks'][1]['clips']=[];self.persist()
        video,audio=self.reference();result=self.execute(2,5)
        self.assertEqual(self.decode(result['master']),video[2*64*64*4:5*64*64*4])
        self.assertEqual(self.decode(result['master'],audio=True),audio[12000*8:30000*8])

    def test_cli_frame_range_cache_and_prune_are_discoverable(self):
        for args in [('frame','--frame','3'),('range','--start-frame','2','--end-frame','4')]:
            code,result=invoke('preview',*args,'--project',self.root)
            self.assertEqual(code,0,result);self.assertTrue(Path(result['data']['path']).is_file())
        code,result=invoke('preview','cache-list','--project',self.root)
        self.assertEqual(code,0,result);self.assertEqual(len(result['data']['entries']),2)
        code,result=invoke('preview','cache-prune','--project',self.root,'--dry-run')
        self.assertEqual(code,0,result);self.assertEqual(len(preview.cache_list(self.root)['entries']),2)
        code,result=invoke('preview','cache-prune','--project',self.root)
        self.assertEqual(code,0,result);self.assertEqual(preview.cache_list(self.root)['entries'],[])


if __name__ == '__main__':
    unittest.main()
