"""Independent native interval oracles, cache integrity, bounds and owned cleanup."""
from array import array
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from ai_ad_editor import native_audio_clock as clock
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project,load_project,save_project
from test_audio_discontinuity import CASES,BLOCK,COUNT,RATE,fixture_sources,original_samples
from test_magnetic_reorder import invoke


def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


class NativeAudioPositionTests(unittest.TestCase):
    def info(self,**changes):return dict(sample_rate='48000',channels=2,time_base='1/48000',origin='0',channel_layout='stereo',**changes)

    def test_exact_native_single_sample_gap_is_retained(self):
        rows=array('q',[0,480,0,481,480,0]);stats=clock._positions(rows,self.info())
        self.assertEqual(list(rows),[0,480,0,481,480,481]);self.assertEqual(stats['gap_samples'],1)

    def test_coarse_quantization_preserves_1024_sample_packets(self):
        rows=array('q',sum(([round(i*1024/48),1024,0] for i in range(12)),[]))
        stats=clock._positions(rows,{**self.info(),'time_base':'1/1000'})
        self.assertEqual(list(rows[2::3]),[i*1024 for i in range(12)])
        self.assertFalse(stats['normalization_needed']);self.assertEqual(stats['logical_frames'],12288)

    def test_coarse_negative_container_origin_does_not_invent_packet_overlaps(self):
        rows=array('q',sum(([round((i-1)*1024/48),1024,0] for i in range(48)),[]))
        stats=clock._positions(rows,{**self.info(),'time_base':'1/1000','origin':'-0.021'})
        self.assertEqual(list(rows[2::3]),[i*1024 for i in range(48)])
        self.assertEqual((stats['gap_count'],stats['overlap_count']),(0,0))

    def test_coarse_gap_and_overlap_keep_cadence_from_each_real_edit_anchor(self):
        pts=[round((i-1)*1024/48)+(100 if i>=10 else 0)-(5 if i>=20 else 0) for i in range(48)]
        rows=array('q',sum(([point,1024,0] for point in pts),[]))
        stats=clock._positions(rows,{**self.info(),'time_base':'1/1000','origin':'-0.021'})
        expected=[i*1024 if i<10 else (pts[10]+21)*48+(i-10)*1024 if i<20 else (pts[20]+21)*48+(i-20)*1024 for i in range(48)]
        self.assertEqual(list(rows[2::3]),expected);self.assertEqual((stats['gap_count'],stats['overlap_count']),(1,1))

    def test_overlap_is_mapped_by_later_decoded_frame(self):
        rows=array('q',[0,480,0,240,480,0]);stats=clock._positions(rows,self.info())
        self.assertEqual(stats['overlap_samples'],240);self.assertEqual(stats['logical_frames'],720)

    def test_equal_nonzero_container_and_audio_origins_add_no_silence(self):
        rows=array('q',[240000,480,0,240480,480,0])
        stats=clock._positions(rows,{**self.info(),'origin':'5'})
        self.assertEqual(list(rows[2::3]),[0,480]);self.assertEqual(stats['logical_frames'],960)

    def test_negative_prefix_is_clipped_from_the_author_origin(self):
        rows=array('q',[-240,480,0,240,480,0]);stats=clock._positions(rows,self.info())
        self.assertEqual(list(rows[2::3]),[-240,240]);self.assertEqual(stats['logical_frames'],720)
        self.assertEqual(stats['negative_first_sample'],-240)

    def test_positive_first_frame_reports_native_leading_silence(self):
        rows=array('q',[2400,480,0]);stats=clock._positions(rows,self.info())
        self.assertEqual(stats['leading_gap_samples'],2400);self.assertEqual(stats['logical_frames'],2880)

    def test_missing_and_incomplete_native_frames_are_rejected(self):
        for rows in (array('q'),array('q',[0,1])):
            with self.subTest(rows=list(rows)),self.assertRaises(AppError):clock._positions(rows,self.info())

    def test_invalid_sample_rates_channels_and_timebases_are_rejected(self):
        for changes in ({'sample_rate':'0'},{'channels':33},{'time_base':'0'},{'time_base':'2'},{'channel_layout':[]}):
            with self.subTest(changes=changes),self.assertRaises(AppError):clock._positions(array('q',[0,480,0]),{**self.info(),**changes})

    def test_zero_negative_and_overlarge_frame_counts_are_rejected(self):
        for count in (0,-1,65537):
            with self.subTest(count=count),self.assertRaises(AppError):clock._positions(array('q',[0,count,0]),self.info())

    def test_sparse_huge_gap_rejects_before_allocating_PCM(self):
        with self.assertRaises(AppError) as caught:clock._positions(array('q',[0,480,0,2**40,480,0]),self.info())
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_DISK_BUDGET')

    def test_stored_sample_positions_are_verified_against_native_PTS(self):
        with self.assertRaises(AppError) as caught:clock._positions(array('q',[0,480,1]),self.info(),verify_positions=True)
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_INDEX_INVALID')


class NativeAudioCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        cls.shared=tempfile.TemporaryDirectory(prefix='native-audio-cache-tests-',dir=base);cls.addClassCleanup(cls.shared.cleanup)
        cls.fixture=Path(cls.shared.name);manifest=os.environ.get('AI_AD_EDITOR_AUDIO_CLOCK_FIXTURES')
        data=json.loads(Path(manifest).read_bytes()) if manifest else fixture_sources(cls.fixture/'originals')
        cls.sources={name:Path(row['path']) for name,row in data['cases'].items()}
        for name,row in data['cases'].items():
            if sha(row['path'])!=row['sha256']:raise AssertionError((name,'fixture changed'))

    def setUp(self):
        self.case=tempfile.TemporaryDirectory(prefix='case-',dir=self.fixture);self.addCleanup(self.case.cleanup)
        self.work=Path(self.case.name);self.root=self.work/'project';create_project(self.root)

    def acquire(self,name='gap',**options):
        return clock.acquire(self.root,self.sources[name],sha(self.sources[name]),persist=True,**options)

    def expected(self,name):
        import numpy as np
        gap,overlap,_,_=CASES[name];end=COUNT*BLOCK+gap-overlap
        result=np.zeros((end,2),dtype='<f4');source=original_samples()
        for i in range(COUNT):
            left=i*BLOCK+(gap if i>=5 else 0)-(overlap if i>=10 else 0)
            result[left:left+BLOCK]=source[i*BLOCK:(i+1)*BLOCK]
        return result.tobytes()

    def test_native_PCM_placement_matches_independent_gap_overlap_and_one_sample_oracles(self):
        for name in ('gap','overlap','mixed','one-sample-gap'):
            with self.subTest(name=name):
                item=self.acquire(name);self.assertEqual(Path(item['pcm_path']).read_bytes(),self.expected(name))
                self.assertEqual(item['stats']['decoded_frames'],COUNT*BLOCK)

    def test_verified_hit_never_reprobes_or_decodes_the_source(self):
        first=self.acquire()
        with mock.patch.object(clock,'probe',side_effect=AssertionError('cache reprobe')),mock.patch.object(clock,'_decode',side_effect=AssertionError('cache redecode')):
            again=self.acquire()
        self.assertEqual(again['key'],first['key']);self.assertEqual(again['source_index_decode_calls'],0)
        self.assertEqual(again['status'],'verified-cache-hit')

    def test_continuous_source_stays_on_original_input_without_a_PCM_decode(self):
        with mock.patch.object(clock,'_decode',side_effect=AssertionError('unnecessary PCM')):item=self.acquire('coarse-continuous')
        self.assertFalse(item['stats']['normalization_needed']);self.assertIsNone(item['pcm_path'])
        self.assertEqual(item['input_args'],['-i',str(self.sources['coarse-continuous'].resolve())])
        self.assertEqual((Path(item['index_path']).parent/'audio.pcm').stat().st_size,0)

    def AAC_source(self,*,edits=False):
        from fractions import Fraction
        import numpy as np
        from ai_ad_editor.media import ffmpeg_path,ffprobe_path
        from test_audio_discontinuity import native
        original=self.work/'AAC-original.f32';original.write_bytes(np.tile(original_samples(),(5,1)).tobytes())
        coded=self.work/'original.m4a';native([ffmpeg_path(),'-v','error','-f','f32le','-ar','48000','-ac','2','-i',original,'-c:a','aac','-b:a','192k',coded])
        target=self.work/'quantized.mkv';command=[ffmpeg_path(),'-v','error','-copyts','-i',coded,'-map','0:a:0','-c:a','copy']
        if edits:command+=['-bsf:a',"setts=pts='PTS+if(gte(N,10),0.1/TB,0)-if(gte(N,20),0.005/TB,0)':dts='DTS+if(gte(N,10),0.1/TB,0)-if(gte(N,20),0.005/TB,0)'"]
        native([*command,'-avoid_negative_ts','disabled',target])
        metadata=json.loads(native([ffprobe_path(),'-v','error','-select_streams','a:0','-show_frames','-show_streams','-show_format',
            '-show_entries','frame=pts,nb_samples:stream=time_base:format=start_time','-of','json',target]))
        raw=np.frombuffer(native([ffmpeg_path(),'-v','error','-i',target,'-map','0:a:0','-c:a','pcm_f32le','-f','f32le','pipe:1']),dtype='<f4').reshape(-1,2)
        frames=metadata['frames'];self.assertEqual(sum(frame['nb_samples'] for frame in frames),len(raw))
        if not edits:return target,raw.tobytes()
        tb=Fraction(metadata['streams'][0]['time_base']);origin=Fraction(metadata['format']['start_time']);cuts=[0,10,20,len(frames)]
        counts=[sum(row['nb_samples'] for row in frames[left:right]) for left,right in zip(cuts,cuts[1:])]
        starts=[round((frames[left]['pts']*tb-origin)*48000) for left in cuts[:-1]]
        expected=np.zeros((max(a+b for a,b in zip(starts,counts)),2),dtype='<f4');cursor=0
        for position,count in zip(starts,counts):expected[position:position+count]=raw[cursor:cursor+count];cursor+=count
        return target,expected.tobytes()

    def test_real_AAC_coarse_continuous_packets_keep_actual_decoded_samples(self):
        from ai_ad_editor.media import ffmpeg_path
        from test_audio_discontinuity import native
        source,expected=self.AAC_source();item=clock.acquire(self.root,source,sha(source),persist=True)
        self.assertFalse(item['stats']['normalization_needed']);self.assertEqual((item['stats']['gap_count'],item['stats']['overlap_count']),(0,0))
        actual=native([ffmpeg_path(),'-v','error',*item['input_args'],'-af','aresample=48000:osf=flt:first_pts=0','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(actual,expected)

    def test_real_AAC_gap_and_overlap_match_independent_actual_decode_group_placement(self):
        source,expected=self.AAC_source(edits=True);item=clock.acquire(self.root,source,sha(source),persist=True)
        self.assertEqual(Path(item['pcm_path']).read_bytes(),expected)
        self.assertEqual((item['stats']['gap_count'],item['stats']['overlap_count']),(1,1))

    def test_wrong_source_SHA_rejects_before_any_native_process(self):
        with mock.patch.object(clock,'_Pipe',side_effect=AssertionError('process started')):
            with self.assertRaises(AppError) as caught:clock.acquire(self.root,self.sources['gap'],'sha256:'+'0'*64,persist=True)
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_INPUT_CHANGED')

    def test_agent_discovery_agrees_with_the_executed_multicam_and_R3_clock(self):
        from ai_ad_editor.multicam import MULTICAM_SYNC_VERSION
        code,value=invoke('capabilities');self.assertEqual(code,0,value);caps=value['data']['capabilities']
        self.assertEqual(caps['native_audio_source_clock']['protocol'],clock.PROTOCOL)
        self.assertEqual(caps['media']['source_audio_clock']['protocol'],clock.PROTOCOL)
        self.assertEqual(caps['media']['multicam_source_coverage']['audio_source_clock'],clock.PROTOCOL)
        self.assertEqual(caps['media']['multicam_source_coverage']['version'],MULTICAM_SYNC_VERSION)

    def test_content_change_with_identical_size_and_mtime_invalidates_the_old_identity(self):
        source=self.work/'source.nut';source.write_bytes(self.sources['gap'].read_bytes());old=sha(source)
        first=clock.acquire(self.root,source,old,persist=True);before=source.stat();raw=bytearray(source.read_bytes());raw[-1]^=1;source.write_bytes(raw)
        os.utime(source,ns=(before.st_atime_ns,before.st_mtime_ns))
        with self.assertRaises(AppError) as caught:clock.acquire(self.root,source,old,persist=True)
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_INPUT_CHANGED');self.assertTrue(Path(first['index_path']).exists())

    def test_PCM_tamper_cannot_be_used_or_silently_overwritten(self):
        item=self.acquire();path=Path(item['pcm_path']);raw=path.read_bytes();bad=bytes([raw[0]^1])+raw[1:];path.write_bytes(bad)
        with self.assertRaises(AppError) as caught:self.acquire()
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_CACHE_HASH_MISMATCH');self.assertEqual(path.read_bytes(),bad)

    def test_rehashed_index_with_false_positions_is_rejected(self):
        item=self.acquire();metadata=Path(item['index_path']);record=json.loads(metadata.read_bytes());path=metadata.parent/'frames.i64le'
        rows=array('q');rows.frombytes(path.read_bytes());rows[2]+=1;path.write_bytes(rows.tobytes())
        record['files']['frames.i64le']['sha256']=sha(path);metadata.write_bytes(clock.canonical(record))
        with self.assertRaises(AppError) as caught:self.acquire()
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_INDEX_INVALID')

    def test_malformed_metadata_returns_a_structured_cache_error(self):
        item=self.acquire();path=Path(item['index_path']);value=json.loads(path.read_bytes());value['files']=None;path.write_bytes(clock.canonical(value))
        with self.assertRaises(AppError) as caught:self.acquire()
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_CACHE_INVALID')

    def test_unknown_cache_files_are_kept_and_rejected(self):
        item=self.acquire();extra=Path(item['index_path']).with_name('user-note.txt');extra.write_text('retain',encoding='utf8')
        with self.assertRaises(AppError) as caught:clock.cache_prune(self.root)
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_LAYOUT_INVALID');self.assertEqual(extra.read_text(),'retain')

    def test_active_registered_source_is_protected_until_removed_from_the_author_graph(self):
        code,value=invoke('media','ingest','--project',self.root,'--input',self.sources['gap']);self.assertEqual(code,0,value)
        item=self.acquire();code,value=invoke('cache','list','--project',self.root,'--kind','native-audio-clock');self.assertEqual(code,0,value)
        self.assertTrue(value['data']['entries'][0]['protected_source_reference'])
        code,value=invoke('cache','prune','--project',self.root,'--kind','native-audio-clock','--key',item['key']);self.assertEqual(code,0,value)
        self.assertEqual(value['data']['removed'],[]);self.assertIn(item['key'],value['data']['protected_reference_keys'])
        _,project=load_project(self.root);project['assets']=[];save_project(self.root,project)
        proposed=clock.cache_prune(self.root,key=item['key'],dry_run=True)
        self.assertEqual(proposed['removed'],[item['key']]);self.assertTrue(Path(item['index_path']).exists())
        removed=clock.cache_prune(self.root,key=item['key']);self.assertEqual(removed['removed'],[item['key']])
        self.assertFalse(Path(item['index_path']).exists());self.assertTrue(self.sources['gap'].is_file())

    def test_explicit_prune_removes_only_the_selected_unreferenced_key(self):
        first=self.acquire();second=self.acquire('overlap');removed=clock.cache_prune(self.root,key=first['key'])
        self.assertEqual(removed['removed'],[first['key']]);self.assertTrue(Path(second['index_path']).exists())

    def test_cancellation_before_preparation_does_not_start_processes_or_create_cache(self):
        marker=self.work/'cancel.flag';marker.touch()
        with mock.patch.object(clock,'_Pipe',side_effect=AssertionError('started')):
            with self.assertRaises(AppError) as caught:self.acquire(cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertFalse((self.root/'cache'/clock.KIND).exists())

    def test_cancellation_during_normalization_cleans_only_owned_staging(self):
        marker=self.work/'cancel.flag';real=clock._decode;sentinel=self.root/'cache'/'user.txt';sentinel.write_text('keep',encoding='utf8')
        def cancelled(*args,**kwargs):marker.touch();return real(*args,**kwargs)
        with mock.patch.object(clock,'_decode',side_effect=cancelled):
            with self.assertRaises(AppError) as caught:self.acquire(cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertEqual(sentinel.read_text(),'keep')
        self.assertFalse(any(p.name.startswith('.audio-clock-') for p in (self.root/'cache').iterdir()))
        self.assertEqual(list((self.root/'cache'/clock.KIND).iterdir()),[])

    def test_native_index_frame_budget_rejects_before_PCM_materialization(self):
        with mock.patch.object(clock,'MAX_FRAMES',1),mock.patch.object(clock,'_decode',side_effect=AssertionError('PCM started')):
            with self.assertRaises(AppError) as caught:self.acquire()
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_INDEX_BUDGET')

    def test_disk_admission_rejects_before_materialization(self):
        with mock.patch.object(clock.shutil,'disk_usage',return_value=type('Space',(),{'free':0})()),mock.patch.object(clock,'_decode',side_effect=AssertionError('PCM started')):
            with self.assertRaises(AppError) as caught:self.acquire()
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_DISK_BUDGET');self.assertFalse((self.root/'cache'/clock.KIND).exists())

    def test_metadata_change_is_caught_at_the_execution_boundary(self):
        item=self.acquire();path=Path(item['index_path']);path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(AppError) as caught:clock.verify_materialized(self.root,[{'native_audio_clock':item}])
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_CACHE_HASH_MISMATCH')

    def test_unmaterialized_analysis_leaves_no_project_cache_or_transient_directory(self):
        before={p.name for p in self.work.iterdir()}
        with clock.normalized_input(self.root,self.sources['gap'],sha(self.sources['gap']),persist=False) as item:
            path=Path(item['pcm_path']);self.assertTrue(path.is_file());self.assertTrue(item['ephemeral'])
            self.assertEqual(path.read_bytes(),self.expected('gap'))
        self.assertFalse(path.exists());self.assertEqual({p.name for p in self.work.iterdir()},before)
        self.assertFalse((self.root/'cache'/clock.KIND).exists())


class NativeAudioPipeTests(unittest.TestCase):
    def pipe(self,program):
        item=clock._Pipe([sys.executable,'-E','-B','-c',program],None);self.addCleanup(item.close);return item

    def test_blank_frame_lines_are_not_confused_with_end_of_stream(self):
        pipe=self.pipe("import sys;sys.stdout.buffer.write(b'\\npts=0|nb_samples=480\\n')")
        self.assertEqual(pipe.line(),b'');self.assertEqual(pipe.line(),b'pts=0|nb_samples=480');self.assertIsNone(pipe.line());pipe.finish()

    def test_nonzero_process_exit_has_a_bounded_stderr_tail(self):
        pipe=self.pipe("import sys;sys.stderr.buffer.write(b'e'*500000);sys.exit(7)")
        self.assertEqual(pipe.read(1),b'')
        with self.assertRaises(AppError) as caught:pipe.finish()
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_DECODE_FAILED');self.assertLessEqual(sum(map(len,pipe.tail)),131072)

    def test_timeout_terminates_the_owned_native_process(self):
        pipe=self.pipe('import time;time.sleep(30)');pipe.deadline=time.monotonic()-1
        with self.assertRaises(AppError) as caught:pipe.read(1)
        self.assertEqual(caught.exception.code,'NATIVE_AUDIO_PROCESS_TIMEOUT');pipe.close();self.assertIsNotNone(pipe.process.poll())


if __name__=='__main__':unittest.main()
