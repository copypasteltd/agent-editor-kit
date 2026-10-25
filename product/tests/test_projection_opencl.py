"""Admission, fallback and native CPU integration without requiring an ICD."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor.errors import AppError
from ai_ad_editor.projection_opencl import ProjectionSession, configuration, apply_overrides, affine_body
from ai_ad_editor.render import render_project
from ai_ad_editor.render_queue import normalize_job
from ai_ad_editor.schema_contract import make_validator
from ai_ad_editor.hardware_acceleration import hardware_failure
from ai_ad_editor.utils import atomic_write_json
import test_sequence_compositing as fixtures


class ProjectionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='projection-policy-')
        self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def session(self,mode='prefer',**values):
        return ProjectionSession(self.root,{'projection_acceleration':{'mode':mode,**values}},'test')

    def selected(self,session):
        cpu=['format=rgba','null']
        gpu=session.select(cpu,kind='test',expressions=['1','0','.5','.5','1','.5','.5'],
            source=(32,24),target=(32,24),body=affine_body(),prefix=['format=gbrapf32le'],suffix=['format=rgba'])
        return cpu,gpu,'[0:v]'+','.join(gpu)+'[vout]'

    def test_strict_configuration_rejects_coercion_and_extensions(self):
        for value in ([],True,{'mode':True},{'mode':[]},{'device':'cuda'}, {'device':'0:0'},
                      {'device':'0.0;other'}, {'unknown':1},{'max_working_bytes':True},
                      {'max_working_bytes':'1024'},{'max_working_bytes':0},{'max_working_bytes':64*1024**3+1},
                      {'probe_timeout_seconds':0},{'probe_timeout_seconds':121}):
            with self.subTest(value=value),self.assertRaises(AppError):configuration(value)
        self.assertEqual(configuration()['mode'],'off')

    def test_schema_has_the_same_strict_policy(self):
        from jsonschema import Draft202012Validator
        checker=Draft202012Validator(make_validator().schema['$defs']['settings']['properties']['projection_acceleration'])
        self.assertFalse(list(checker.iter_errors(configuration({'mode':'require'}))))
        for value in ({'mode':True},{'device':'0.0\n'},{'unknown':1},{'max_working_bytes':0}):
            self.assertTrue(list(checker.iter_errors(value)),value)

    def test_queue_cli_overrides_preserve_explicit_policy(self):
        raw={'job_id':'test','projection_acceleration':'require','projection_device':'1.2','projection_memory_mib':256}
        job=normalize_job(self.root,raw);settings={};apply_overrides(settings,job)
        self.assertEqual(settings['projection_acceleration'],configuration({'mode':'require','device':'1.2','max_working_bytes':256*1024**2}))
        from ai_ad_editor.cli import build_parser,_render_settings_for_args,_queue_job_args
        parser=build_parser();args=parser.parse_args(['render','--project',str(self.root),
            '--projection-acceleration','require','--projection-device','1.2','--projection-memory-mib','256'])
        project={'settings':{'canvas':{'width':160,'height':96}},'sequences':[{'id':'seq_main'}]}
        effective,_=_render_settings_for_args(project,args)
        self.assertEqual(effective['projection_acceleration'],settings['projection_acceleration'])
        queued=_queue_job_args(self.root,job,argparse.Namespace())
        self.assertEqual(queued.projection_acceleration,'require');self.assertEqual(queued.projection_device,'1.2')
        self.assertNotIn('projection_acceleration',project['settings'])
        for raw in ({'projection_acceleration':'gpu'},{'projection_device':'https://invalid'},
                    {'projection_memory_mib':True},{'projection_memory_mib':65537}):
            with self.assertRaises(AppError):normalize_job(self.root,raw)

    def test_output_reuse_cannot_bypass_per_job_projection_probe(self):
        from ai_ad_editor.queue_reuse import _dependency_paths
        for mode in ('prefer','require'):
            with self.subTest(mode=mode),self.assertRaises(AppError) as caught:
                _dependency_paths(self.root,{'assets':[]},{'projection_acceleration':{'mode':mode}})
            self.assertEqual(caught.exception.code,'QUEUE_REUSE_UNSUPPORTED')

    def test_planning_never_creates_diagnostics_or_context(self):
        session=self.session();self.selected(session)
        self.assertFalse(session.path.exists());self.assertFalse(session.directory.exists())
        self.assertEqual(session.evidence['status'],'planned')

    def test_quota_and_unsafe_expressions_choose_cpu_or_reject(self):
        for mode in ('prefer','require'):
            session=self.session(mode,max_working_bytes=1)
            if mode=='require':
                with self.assertRaises(AppError):self.selected(session)
            else:
                cpu,gpu,_=self.selected(session);self.assertEqual(cpu,gpu)
                self.assertEqual(session.evidence['nodes'][0]['selected'],'cpu')
            self.assertFalse(session.directory.exists())
        session=self.session('require')
        with self.assertRaises(AppError):
            session.select(['null'],kind='stateful',expressions=['st(0,T)'],source=(32,24),target=(32,24),
                body='',prefix=[],suffix=[],pure=False)

    def test_preflight_fallback_restores_exact_cpu_chain(self):
        session=self.session();cpu,gpu,graph=self.selected(session)
        args=['ffmpeg','-filter_complex',graph]
        with patch.object(session,'preflight',side_effect=OSError('ICD unavailable')):
            actual,result=session.prepare(args,graph)
        self.assertEqual(result,'[0:v]'+','.join(cpu)+'[vout]')
        self.assertEqual(actual,['ffmpeg','-filter_complex',result]);self.assertNotIn('-init_hw_device',actual)
        self.assertEqual(json.loads(session.path.read_bytes())['status'],'cpu_fallback')

    def test_require_preflight_failure_never_executes_cpu(self):
        session=self.session('require');_,_,graph=self.selected(session)
        with patch.object(session,'preflight',side_effect=OSError('missing')),self.assertRaises(AppError) as caught:
            session.prepare(['ffmpeg','-filter_complex',graph],graph)
        self.assertEqual(caught.exception.code,'PROJECTION_REQUIRED_UNAVAILABLE')
        self.assertEqual(session.evidence['status'],'preflight_failed')

    def test_cancellation_does_not_become_prefer_fallback(self):
        session=self.session();_,_,graph=self.selected(session)
        for code in ('CANCELLED','PROCESS_TIMEOUT'):
            with patch.object(session,'preflight',side_effect=AppError(code,code,exit_code=8)),self.assertRaises(AppError) as caught:
                session.prepare(['ffmpeg','-filter_complex',graph],graph)
            self.assertEqual(caught.exception.code,code)
            self.assertNotEqual(session.evidence['status'],'cpu_fallback')

    def test_no_applicable_projection_is_explicit(self):
        for mode in ('prefer','require'):
            session=self.session(mode)
            if mode=='require':
                with self.assertRaises(AppError) as caught:session.prepare(['ffmpeg','-filter_complex','null'],'null')
                self.assertEqual(caught.exception.code,'PROJECTION_NOT_APPLICABLE')
            else:self.assertEqual(session.prepare(['ffmpeg','-filter_complex','null'],'null')[1],'null')
            self.assertEqual(session.evidence['status'],'not_applicable')

    def test_kernel_files_are_pinned_and_never_overwritten(self):
        session=self.session();self.selected(session);session.write_programs()
        with self.assertRaises(AppError):session.write_programs()
        path=next(iter(session.programs));path.write_text('modified',encoding='utf8')
        with self.assertRaises(AppError) as caught:session.verify_programs()
        self.assertEqual(caught.exception.code,'PROJECTION_PROGRAM_CHANGED')

    def test_opencl_runtime_failure_is_not_an_encoder_retry(self):
        for text in ('program_opencl: CUDA device lost','aek_projection: hwdownload failed',
                     'OpenCL failed, h264_nvenc aborted'):
            self.assertFalse(hardware_failure(text))
        self.assertTrue(hardware_failure('h264_nvenc: device lost'))
        session=self.session();self.selected(session);session.evidence['status']='prepared'
        session.finish(subprocess.CompletedProcess([],1,'retained stdout','program_opencl failed'))
        self.assertEqual(session.evidence['status'],'render_failed')
        self.assertEqual((session.directory/'render.stderr.log').read_text('utf8'),'program_opencl failed')


class ProjectionNativeFallbackTests(unittest.TestCase):
    setUpClass=fixtures.SequenceCompositingTests.__dict__['setUpClass']
    tearDownClass=fixtures.SequenceCompositingTests.__dict__['tearDownClass']
    setUp=fixtures.SequenceCompositingTests.setUp
    call=fixtures.SequenceCompositingTests.call
    layer=fixtures.SequenceCompositingTests.layer

    def project(self,mode='prefer'):
        self.layer('seq_main','track_video_1','red_clip','red',transform={'rotation':17.})
        path=self.base/'ops.json';atomic_write_json(path,{'operations':self.ops})
        self.call('timeline','compose','--project',self.root,'--input',path)
        project=json.loads((self.root/'project.json').read_bytes())
        project['settings']['projection_acceleration']={'mode':mode}
        return project,next(s for s in project['sequences'] if s['id']=='seq_main')

    def test_real_prefer_cpu_fallback_decodes_to_identical_frames(self):
        project,sequence=self.project()
        with patch('ai_ad_editor.projection_opencl.device_info',side_effect=OSError('ICD missing')):
            actual=render_project(self.root,project,sequence,self.root/'renders/prefer.mkv')
        self.assertEqual(actual['projection_acceleration']['status'],'cpu_fallback')
        project['settings']['projection_acceleration']={'mode':'off'}
        expected=render_project(self.root,project,sequence,self.root/'renders/off.mkv')
        from ai_ad_editor.media import ffmpeg_path
        def decode(path):
            return subprocess.check_output([ffmpeg_path(),'-v','error','-i',path,'-pix_fmt','rgba','-f','rawvideo','pipe:1'])
        self.assertEqual(decode(actual['path']),decode(expected['path']))
        self.assertEqual(actual['delivery']['clock']['expected_video_frames'],8)

    def test_dry_run_never_probes_or_writes_kernels(self):
        project,sequence=self.project('require')
        with patch.object(ProjectionSession,'preflight',side_effect=AssertionError('unexpected context')):
            result=render_project(self.root,project,sequence,self.root/'renders/dry.mkv',dry_run=True)
        self.assertEqual(result['plan']['projection_acceleration']['status'],'planned')
        self.assertTrue(result['plan']['projection_acceleration']['nodes'])
        self.assertFalse((self.root/'renders/diagnostics').exists())

    def test_require_keeps_existing_output_and_failure_operation(self):
        project,sequence=self.project('require');output=self.root/'renders/old.mkv';output.write_bytes(b'old')
        with (patch('ai_ad_editor.projection_opencl.device_info',side_effect=OSError('missing')),
              self.assertRaises(AppError) as caught):
            render_project(self.root,project,sequence,output)
        self.assertEqual(caught.exception.code,'PROJECTION_REQUIRED_UNAVAILABLE')
        self.assertEqual(output.read_bytes(),b'old')
        operation=json.loads((self.root/'operations'/f'{caught.exception.operation_id}.json').read_bytes())
        self.assertEqual(operation['plan']['projection_acceleration']['status'],'failed')

    def test_cancel_keeps_existing_output_and_does_not_compile(self):
        project,sequence=self.project('require');output=self.root/'renders/old.mkv';output.write_bytes(b'old')
        cancel=self.root/'cancel.flag';cancel.touch()
        with (patch.object(ProjectionSession,'preflight',side_effect=AssertionError('unexpected context')),
              self.assertRaises(AppError) as caught):
            render_project(self.root,project,sequence,output,cancel_file=cancel)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertEqual(output.read_bytes(),b'old')
        report=next((self.root/'renders/diagnostics').glob('projection_*/report.json'))
        self.assertEqual(json.loads(report.read_bytes())['status'],'cancelled')
