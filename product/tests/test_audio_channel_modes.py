"""Actual local R3 channel fidelity, phase tradeoffs and compatible defaults."""
from __future__ import annotations
import array
import hashlib
import json
import math
from pathlib import Path
from unittest import mock
import unittest
import wave

from ai_ad_editor.audio_stretch import configuration
from ai_ad_editor.errors import AppError
from ai_ad_editor.utils import atomic_write_json
import test_audio_stretch as fixtures

decode=fixtures.decode
peak_hz=fixtures.peak_hz


class AudioChannelModeTests(unittest.TestCase):
    setUpClass=classmethod(fixtures.OfflineAudioStretchTests.setUpClass.__func__)
    tearDownClass=fixtures.OfflineAudioStretchTests.__dict__['tearDownClass']
    setUp=fixtures.OfflineAudioStretchTests.setUp
    call=fixtures.OfflineAudioStretchTests.call
    config=fixtures.OfflineAudioStretchTests.config
    prepare=fixtures.OfflineAudioStretchTests.prepare
    render=fixtures.OfflineAudioStretchTests.render

    def set_mode(self, mode):
        p=json.loads((self.root/'project.json').read_text(encoding='utf-8-sig'))
        p['settings']['audio_stretch']['channel_mode']=mode
        atomic_write_json(self.root/'project.json',p)

    def material(self, kind):
        p=self.base/f'{kind}.wav';values=array.array('h')
        for i in range(144000):
            value=round(.2*32767*math.sin(2*math.pi*400*i/48000))
            values.extend((value,) if kind=='mono' else (value,0 if kind=='left-only' else -value))
        with wave.open(str(p),'wb') as h:h.setparams((1 if kind=='mono' else 2,2,48000,0,'NONE',''));h.writeframes(values.tobytes())
        self.stereo=p

    def test_default_mode_retains_explicit_together_pcm_and_cache(self):
        self.prepare();one,first,_=self.render('implicit');a=decode(one)
        self.set_mode('together');two,second,_=self.render('explicit')
        self.assertEqual(first['key'],second['key']);self.assertEqual(a,decode(two))
        self.assertEqual(first['execution']['channel_mode'],'together')
        self.assertIn('--centre-focus',first['execution']['command'])

    def test_apart_mode_keeps_low_tone_dominant_in_left_channel(self):
        self.prepare(left=.201,right=.205,duration=.25,nested=True);self.set_mode('apart');output,job,_=self.render()
        values=decode(output);left=values[:24000:2];right=values[1:24000:2]
        def energy(samples,hz):
            a=sum(v*math.cos(2*math.pi*hz*i/48000) for i,v in enumerate(samples))
            b=sum(v*math.sin(2*math.pi*hz*i/48000) for i,v in enumerate(samples))
            return a*a+b*b
        self.assertGreater(energy(left,375),energy(left,800)*5)
        self.assertGreater(energy(right,820),energy(right,400)*5)
        self.assertNotIn('--centre-focus',job['execution']['command'])
        self.assertEqual(job['engine']['channel_mode'],'apart')
        # Dominant bands are separated; these pitches still fail +/-5 Hz.
        self.assertGreater(abs(peak_hz(left,400)-400),5)
        self.assertFalse(job['execution']['pitch_and_listening_accepted'])

    def test_together_preserves_exact_antiphase_cancellation(self):
        self.material('antiphase');self.prepare();output,job,_=self.render();values=decode(output)
        self.assertGreater(max(abs(x) for x in values),.01)
        self.assertTrue(all(a+b==0 for a,b in zip(values[::2],values[1::2])))
        self.assertFalse(job['execution']['stereo_phase_accepted'])

    def test_apart_preserves_proven_exact_antiphase_without_muting_audio(self):
        self.material('antiphase');self.prepare();self.set_mode('apart');output,job,_=self.render();values=decode(output)
        self.assertGreater(max(abs(value) for value in values),.01)
        self.assertTrue(all(a+b==0 for a,b in zip(values[::2],values[1::2])))
        proof=job['execution']['exact_channel_links']
        self.assertEqual(proof['links'],[{'channel':1,'reference':0,'gain':-1}])
        self.assertGreater(proof['engine_output_max_abs_change'][0]['maximum'],.001)
        self.assertFalse(proof['arbitrary_stereo_phase_accepted'])

    def test_left_only_input_keeps_right_channel_exactly_silent(self):
        self.material('left-only');self.prepare()
        for mode in ('together','apart'):
            with self.subTest(mode=mode):
                self.set_mode(mode);output,job,_=self.render(mode);values=decode(output)
                self.assertTrue(any(values[::2]));self.assertFalse(any(values[1::2]))
                self.assertEqual(job['execution']['output_pcm']['nonzero_samples'][1],0)

    def test_mono_input_has_identical_actual_pcm_in_both_modes(self):
        self.material('mono');self.prepare();one,a,_=self.render('mono-together');values=decode(one)
        self.set_mode('apart');two,b,_=self.render('mono-apart')
        self.assertEqual(values,decode(two));self.assertEqual(a['channels'],1);self.assertEqual(b['channels'],1)

    def test_invalid_modes_fail_before_native_execution(self):
        for value in (None,True,0,[],{},'auto','independent','APART',''):
            with self.subTest(value=value),mock.patch('ai_ad_editor.audio_stretch.run_process') as process:
                config=self.config();config['channel_mode']=value
                with self.assertRaises(AppError) as caught:configuration(self.root,config)
                self.assertEqual(caught.exception.code,'AUDIO_STRETCH_CONFIG_INVALID');process.assert_not_called()

    def test_channel_modes_use_distinct_immutable_cache_files(self):
        self.prepare(left=.201,right=.205,duration=.25);one,a,_=self.render('together');cached=Path(a['output']);before=cached.read_bytes()
        self.set_mode('apart');two,b,_=self.render('apart')
        self.assertNotEqual(a['key'],b['key']);self.assertNotEqual(decode(one),decode(two))
        self.assertEqual(cached.read_bytes(),before);self.assertEqual('sha256:'+hashlib.sha256(before).hexdigest(),a['execution']['output_pcm']['sha256'])

    def test_apart_normal_scalar_stretch_retains_both_tones(self):
        self.prepare();self.set_mode('apart');output,_,_=self.render();values=decode(output)
        for channel,hz in enumerate((400,800)):
            self.assertLessEqual(abs(peak_hz(values[channel:24000:2],hz)-hz),5)
        self.assertTrue(all(x==0 for x in values[24000:]))

    def test_apart_dry_run_does_not_decode_or_create_pcm_cache(self):
        self.prepare();self.set_mode('apart')
        with mock.patch('ai_ad_editor.audio_stretch.run_process',side_effect=AssertionError('dry run decoded media')):
            result=self.call('render','--project',self.root,'--output',self.root/'renders/planned.mkv','--container','mkv','--dry-run')
        self.assertEqual(result['data']['status'],'planned');self.assertFalse((self.root/'cache/audio-stretch').exists())


if __name__=='__main__':unittest.main()
