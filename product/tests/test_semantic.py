"""Retrieval integrity, source clocks and project integration; no model mocks as quality evidence."""
from array import array
import contextlib
import io
import json
import math
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor import semantic
from ai_ad_editor.cli import build_parser, main
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project
from ai_ad_editor.semantic_contract import check_vectors, json_object, local_file, rank, sample_times
from ai_ad_editor.semantic_sampling import choose_video_frames, extract, plan
from ai_ad_editor.utils import run_process


def call(arguments):
    output=io.StringIO()
    with contextlib.redirect_stdout(output):code=main(arguments)
    value=json.loads(output.getvalue())
    if code:raise AssertionError(value)
    return value


def basis(index=0):
    value=np.zeros(768,dtype='<f4');value[index]=1
    return value


class SemanticMathTests(unittest.TestCase):
    def test_unit_vector_validation_rejects_nonfinite_zero_wrong_shape_and_norm(self):
        for value in (np.zeros((1,768)),np.full((1,768),float('nan')),np.ones((1,768)),np.ones((1,767))):
            with self.subTest(shape=value.shape),self.assertRaises(AppError):check_vectors(value,1)
        np.testing.assert_array_equal(check_vectors(basis()[None],1),basis()[None])

    def test_cosine_has_negative_scores_and_is_not_probability(self):
        rows=[dict(asset_id='x',kind='image',sample_seconds=0),dict(asset_id='y',kind='image',sample_seconds=0)]
        values=np.array([-basis(),basis()])
        hits=rank(values,basis(),rows,limit=2)
        self.assertEqual([(h['asset_id'],h['score']) for h in hits],[('y',1.),('x',-1.)])
        self.assertTrue(all(h['score_kind']=='cosine_similarity_not_probability' and h['review_required'] for h in hits))

    def test_asset_dedup_kind_threshold_and_deterministic_ties(self):
        rows=[dict(asset_id='b',kind='video',sample_seconds=2),dict(asset_id='a',kind='image',sample_seconds=0),
              dict(asset_id='b',kind='video',sample_seconds=1)]
        values=np.array([basis(),basis(),basis()])
        self.assertEqual([(h['asset_id'],h['sample_seconds']) for h in rank(values,basis(),rows,limit=3)],[('a',0),('b',1)])
        self.assertEqual(len(rank(values,basis(),rows,limit=3,distinct_assets=False)),3)
        self.assertEqual(len(rank(values,basis(),rows,limit=3,kind='video')),1)
        self.assertEqual(rank(values,-basis(),rows,limit=3,minimum=0),[])

    def test_invalid_rank_controls_refuse(self):
        rows=[dict(asset_id='a',kind='image',sample_seconds=0)]
        for controls in (dict(limit=0),dict(limit=True),dict(limit=101),dict(limit=1,minimum=float('nan')),
                         dict(limit=1,minimum=2),dict(limit=1,kind='audio')):
            with self.subTest(controls=controls),self.assertRaises(AppError):rank(basis()[None],basis(),rows,**controls)

    def test_sampling_budget_never_silently_truncates(self):
        self.assertEqual(sample_times(2.1,interval=1,per_asset=3),[0,1,2])
        self.assertEqual(sample_times(2,interval=1,per_asset=3),[0,1])
        for duration,interval,budget in ((2.1,1,2),(1,float('nan'),2),(True,1,2),(1,1,True)):
            with self.subTest(values=(duration,interval,budget)),self.assertRaises(AppError):sample_times(duration,interval=interval,per_asset=budget)

    def test_vfr_nonzero_container_origin_and_held_frame_bins(self):
        rows,meta=choose_video_frames(array('q',[50,53,59]),array('q',[3,6,1]),{'time_base':'1/10'},
                                     {'start_time':'5'},interval=.2,per_asset=10)
        self.assertEqual([r['native_frame_index'] for r in rows],[0,1])
        self.assertEqual([r['sample_seconds'] for r in rows],[0,.3])
        self.assertEqual(meta['requested_bins'],5)
        self.assertEqual(rows[0]['requested_seconds'],[0,.2])
        self.assertEqual(rows[1]['requested_seconds'],[.4,.6,.8])

    def test_late_video_start_excludes_audio_only_prefix(self):
        rows,meta=choose_video_frames(array('q',[20,25]),array('q',[5,5]),{'time_base':'1/10'},
                                     {'start_time':'0'},interval=.5,per_asset=2)
        self.assertEqual(meta['window_start_seconds'],2.)
        self.assertEqual(rows[0]['requested_seconds'],[2.])

    def test_unknown_last_duration_is_an_error(self):
        with self.assertRaises(AppError):choose_video_frames([0],[0],{'time_base':'1/10'},{'start_time':'0'},interval=1,per_asset=10)

    def test_strict_json_and_local_input_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'value.json'
            for text in ('{"x":1,"x":2}','{"x":NaN}','[]'):
                path.write_text(text,encoding='utf8')
                with self.assertRaises(AppError):json_object(path)
            path.write_text('{}',encoding='utf8')
            with self.assertRaises(AppError):json_object(path,max_bytes=1)
        for value in ('https://example.invalid/a.png',r'\\server\a.png'):
            with self.assertRaises(AppError):local_file(value)

    def test_query_answers_extra_fields_duplicates_and_empty_text_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);path=root/'queries.json'
            for rows in ([dict(id='a',text='cat',answer='cat')],[dict(id='a',text='')],
                         [dict(id='a',text='cat'),dict(id='a',text='dog')]):
                path.write_text(json.dumps({'queries':rows}),encoding='utf8')
                with self.assertRaises(AppError):semantic.queries_from(queries_file=str(path),root=root)
            task,items=semantic.queries_from(query='  A CAT 中文  ',root=root)
            self.assertEqual((task,items[0]['text']),('text','  A CAT 中文  '))

    def test_auto_cuda_failure_is_preserved_and_explicit_cpu_retry_is_reported(self):
        error=AppError('SEMANTIC_CUDA_FAILED','CUDA out of memory',exit_code=6)
        with (tempfile.TemporaryDirectory() as temporary,
              patch.object(semantic,'select_device',return_value=dict(selected='cuda')),
              patch.object(semantic,'_invoke',side_effect=[error,(basis()[None],{'status':'succeeded'})]) as invoke):
            _,report=semantic.embed(Path(temporary),{'model_path':'local','python_executable':'python.exe'},[{'id':'a'}],'text',
                job=Path(temporary),device='auto',device_index=0,batch_size=1,deadline=time.monotonic()+10,marker=None)
            self.assertEqual(invoke.call_count,2)
            self.assertEqual(report['selection']['fallback_reason'],'cuda_worker_failed')
            self.assertEqual(report['attempts'][0]['error']['code'],'SEMANTIC_CUDA_FAILED')

    def test_integrity_failure_never_retries_cpu(self):
        with (tempfile.TemporaryDirectory() as temporary,
              patch.object(semantic,'select_device',return_value=dict(selected='cuda')),
              patch.object(semantic,'_invoke',side_effect=AppError('SEMANTIC_ADAPTER_INTEGRITY_FAILED','changed')) as invoke):
            with self.assertRaises(AppError):semantic.embed(Path(temporary),{'model_path':'local','python_executable':'python.exe'},[{'id':'a'}],'text',
                job=Path(temporary),device='auto',device_index=0,batch_size=1,deadline=time.monotonic()+10,marker=None)
            self.assertEqual(invoke.call_count,1)


class SemanticNativeClockTests(unittest.TestCase):
    def test_real_cfr_vfr_and_nonzero_pts_match_decoded_frames(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            cases={'cfr':None,'nonzero':'setpts=PTS+5/TB','vfr':'select=eq(n\\,0)+eq(n\\,2)+eq(n\\,7)'}
            for label,filter_text in cases.items():
                with self.subTest(label=label):
                    source=root/(label+'.nut')
                    command=[ffmpeg_path(),'-nostdin','-v','error','-f','lavfi','-i','testsrc2=s=96x64:r=8:d=1']
                    if filter_text:command+=['-vf',filter_text]
                    result=run_process(command+['-fps_mode','passthrough','-c:v','ffv1','-n',str(source)],timeout=30)
                    self.assertEqual(result.returncode,0,result.stderr)
                    deadline=time.monotonic()+30
                    samples,meta=plan(source,'video',interval=.25,per_asset=10,deadline=deadline,marker=None)
                    actual,report=extract(source,'video',samples,root/(label+'-frames'),deadline=deadline,marker=None)
                    self.assertTrue(report['native_pts_checked'])
                    self.assertEqual(len(actual),len(samples))
                    self.assertEqual(actual[0]['sample_seconds'],0)
                    self.assertEqual(actual[0]['preview_probe']['video']['width'],512)
                    if label=='nonzero':self.assertEqual(meta['container_start_seconds'],'5')
                    if label=='vfr':self.assertEqual([r['native_frame_index'] for r in samples],[0,1])


class SemanticIndexIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.base=Path(self.temporary.name)
        self.root,self.project=create_project(self.base/'project')
        self.source=self.base/'source.png'
        result=run_process([ffmpeg_path(),'-nostdin','-v','error','-f','lavfi','-i','testsrc2=s=96x64:r=1:d=1',
                            '-frames:v','1','-pix_fmt','rgb24','-n',str(self.source)],timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        call(['media','ingest','--project',str(self.root),'--input',str(self.source),'--asset-id','asset_visual'])
        self.project=load_project(self.root)[1]
        self.adapter={'sha256':'sha256:'+'a'*64,'rights_ref':'test_model','adapter_id':'model'}
        self.checked=patch.object(semantic,'_checked_adapter',return_value=self.adapter);self.checked.start();self.addCleanup(self.checked.stop)
        self.embedding=patch.object(semantic,'embed',side_effect=lambda root,adapter,items,task,**kw:
                                   (np.tile(basis(),(len(items),1)),{'development_test_stub':True}))
        self.embedding.start();self.addCleanup(self.embedding.stop)

    def build(self):
        value=semantic.build_index(self.root,self.project,index_id='index',adapter_id='model',asset_ids=['asset_visual'])
        self.project=load_project(self.root)[1]
        return value

    def test_registered_index_is_verified_and_queries_preserve_project_and_rights(self):
        self.build();before={name:(self.root/name).read_bytes() for name in ('project.json','rights-ledger.json')}
        report=semantic.search(self.root,self.project,index_id='index',query='a visual',device='cpu')
        self.assertEqual(report['results'][0]['hits'][0]['asset_id'],'asset_visual')
        self.assertTrue(report['results'][0]['hits'][0]['editable_reference']['point_sample_only'])
        for name,value in before.items():self.assertEqual((self.root/name).read_bytes(),value)

    def test_vector_corruption_is_rejected(self):
        result=self.build();path=Path(result['manifest']).with_name('vectors.f32')
        raw=bytearray(path.read_bytes());raw[-1]^=1;path.write_bytes(raw)
        with self.assertRaises(AppError):semantic.read_index(self.root,self.project,'index')

    def test_manifest_corruption_is_rejected(self):
        result=self.build();path=Path(result['manifest']);path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(AppError):semantic.read_index(self.root,self.project,'index')

    def test_source_corruption_is_rejected(self):
        self.build();path=self.root/next(a for a in self.project['assets'] if a['id']=='asset_visual')['uri']
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(AppError):semantic.read_index(self.root,self.project,'index')

    def test_ingested_copy_is_independent_of_later_external_original_edits(self):
        self.build();self.source.write_bytes(self.source.read_bytes()+b' ')
        manifest,_,_=semantic.read_index(self.root,self.project,'index')
        self.assertEqual(manifest['sources'][0]['asset_id'],'asset_visual')

    def test_preview_corruption_is_rejected(self):
        result=self.build();manifest=json.loads(Path(result['manifest']).read_bytes());path=self.root/manifest['rows'][0]['preview_uri']
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(AppError):semantic.read_index(self.root,self.project,'index')

    def test_stale_adapter_is_rejected(self):
        self.build();self.adapter['sha256']='sha256:'+'b'*64
        with self.assertRaises(AppError):semantic.read_index(self.root,self.project,'index')

    def test_duplicate_index_does_not_overwrite_existing_outputs(self):
        result=self.build();original=Path(result['manifest']).read_bytes()
        with self.assertRaises(AppError):semantic.build_index(self.root,self.project,index_id='index',adapter_id='model',asset_ids=['asset_visual'])
        self.assertEqual(Path(result['manifest']).read_bytes(),original)

    def test_cancelled_index_keeps_project_and_never_embeds(self):
        marker=self.root/'stop';marker.touch();before=(self.root/'project.json').read_bytes()
        with patch.object(semantic,'embed',side_effect=AssertionError('must not infer')),self.assertRaises(AppError) as caught:
            semantic.build_index(self.root,self.project,index_id='index',adapter_id='model',asset_ids=['asset_visual'],cancel_file='stop')
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_dry_run_does_not_create_outputs_or_load_model(self):
        before=(self.root/'project.json').read_bytes()
        with patch.object(semantic,'embed',side_effect=AssertionError('must not infer')):
            result=semantic.build_index(self.root,self.project,index_id='index',adapter_id='model',asset_ids=['asset_visual'],dry_run=True)
        self.assertFalse(Path(result['destination']).exists());self.assertFalse((self.root/'cache/semantic-jobs').exists())
        self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_index_failure_removes_unregistered_derivatives(self):
        before=(self.root/'project.json').read_bytes()
        with patch.object(semantic,'embed',side_effect=AppError('SEMANTIC_WORKER_FAILED','test')),self.assertRaises(AppError):
            semantic.build_index(self.root,self.project,index_id='index',adapter_id='model',asset_ids=['asset_visual'])
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        self.assertFalse(any((self.root/'assets/semantic').glob('*/index.json')))

    def test_cli_requires_explicit_source_and_query_choices(self):
        parser=build_parser()
        args=parser.parse_args(['semantic','search','--project','p','--index-id','i','--query','猫'])
        self.assertEqual((args.device,args.batch_size,args.query),('auto',8,'猫'))
        output=io.StringIO()
        with contextlib.redirect_stderr(output),self.assertRaises(SystemExit):
            parser.parse_args(['semantic','search','--project','p','--index-id','i','--query','cat','--image','x.png'])


if __name__=='__main__':unittest.main()
