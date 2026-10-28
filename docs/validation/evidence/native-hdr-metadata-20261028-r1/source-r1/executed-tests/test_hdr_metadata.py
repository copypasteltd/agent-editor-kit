"""Exact declared units and real HEVC output, failure publication and packages."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from ai_ad_editor.errors import AppError
from ai_ad_editor.hdr_metadata import normalize, encoder_arguments, encoded_fields, verify_probe, verify_output
from ai_ad_editor.project import save_project, load_project, project_write_lock
from ai_ad_editor.render import output_settings, render_project
from ai_ad_editor.schema_contract import make_validator

RECEIPTS=[]
DECLARATION={'mastering_display':{'red_xy':[.68,.32],'green_xy':[.265,.69],
    'blue_xy':[.15,.06],'white_xy':[.3127,.329], 'min_luminance_nits':.0001,'max_luminance_nits':1000},
    'content_light':{'max_cll_nits':1000,'max_fall_nits':400}}


def probe():
    # Independent integer-unit fixture from x265's documented P3D65 example.
    fields={'red_x':'34000/50000','red_y':'16000/50000','green_x':'13250/50000',
        'green_y':'34500/50000','blue_x':'7500/50000','blue_y':'3000/50000',
        'white_x':'15635/50000','white_y':'16450/50000',
        'min_luminance':'1/10000','max_luminance':'10000000/10000'}
    sides=[dict(side_data_type='Mastering display metadata',**fields),
           dict(side_data_type='Content light level metadata',max_content=1000,max_average=400)]
    return dict(streams=[dict(codec_name='hevc',pix_fmt='yuv420p10le',color_primaries='bt2020',
        color_transfer='smpte2084',color_space='bt2020nc',color_range='tv')],
        frames=[dict(best_effort_timestamp=0,side_data_list=sides)])


class MetadataUnitTests(unittest.TestCase):
    def test_fixed_units_match_independent_documented_x265_string(self):
        args=encoder_arguments(DECLARATION)
        self.assertEqual(args,['-x265-params','master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):max-cll=1000,400:hdr10=1:cll=1'])
        self.assertEqual(encoded_fields(DECLARATION)['min_luminance'],Fraction(1,10000))
        self.assertEqual(encoder_arguments(None),[])

    def test_no_silent_rounding_for_color_coordinates_or_nits(self):
        for key,value in [('white_xy',[.312701,.329]),('min_luminance_nits',.00015),('max_luminance_nits',1000.00001)]:
            v=copy.deepcopy(DECLARATION);v['mastering_display'][key]=value
            with self.subTest(key=key),self.assertRaises(AppError) as c:normalize(v)
            self.assertEqual(c.exception.code,'HDR_METADATA_PRECISION')

    def test_rejects_nonfinite_boolean_unknown_missing_and_injected_values(self):
        for value in [None,{},[],{**DECLARATION,'x265':'evil'}, {**DECLARATION,'content_light':None}]:
            with self.subTest(value=value),self.assertRaises(AppError):normalize(value)
        for value in (True,float('nan'),float('inf'),'1000):lossless=1'):
            v=copy.deepcopy(DECLARATION);v['mastering_display']['max_luminance_nits']=value
            with self.subTest(value=value),self.assertRaises(AppError):normalize(v)

    def test_gamut_triangle_white_point_and_xy_domain_are_checked(self):
        for key,value in [('red_xy',[.8,.4]),('white_xy',[.01,.01]),('red_xy',[.265,.69]),
                          ('green_xy',[.4,0]),('blue_xy',[.1])]:
            v=copy.deepcopy(DECLARATION);v['mastering_display'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(AppError):normalize(v)

    def test_rejects_invalid_luminance_intervals_and_content_light_relations(self):
        for key,value in [('min_luminance_nits',1000),('max_luminance_nits',10001),('min_luminance_nits',-1)]:
            v=copy.deepcopy(DECLARATION);v['mastering_display'][key]=value
            with self.subTest(key=key),self.assertRaises(AppError):normalize(v)
        for cll,fall in [(100,101),(True,0),(1.5,1),(10001,100),(-1,0)]:
            v=copy.deepcopy(DECLARATION);v['content_light']=dict(max_cll_nits=cll,max_fall_nits=fall)
            with self.subTest(cll=cll,fall=fall),self.assertRaises(AppError):normalize(v)

    def test_zero_content_levels_explicitly_mean_unknown(self):
        for cll,fall in ((0,0),(1000,0),(0,500)):
            v=copy.deepcopy(DECLARATION);v['content_light']=dict(max_cll_nits=cll,max_fall_nits=fall)
            self.assertEqual(normalize(v)['content_light'],v['content_light'])

    def test_normalization_owns_nested_values(self):
        value=copy.deepcopy(DECLARATION);result=normalize(value)
        value['mastering_display']['red_xy'][0]=0;value['content_light']['max_cll_nits']=0
        self.assertEqual(result,DECLARATION)

    def test_probe_accepts_equal_rationals_and_discloses_prefix_not_measured(self):
        raw=probe();raw['frames'][0]['side_data_list'][0]['red_x']='17/25'
        receipt=verify_probe(raw,DECLARATION)
        self.assertEqual(receipt['verified_decoded_frames'],1)
        self.assertEqual(receipt['scope'],'decoded-prefix-only');self.assertFalse(receipt['content_peaks_measured'])
        self.assertFalse(receipt['HDR_monitor_accepted'])

    def test_probe_rejects_missing_duplicate_changed_and_later_conflicting_SEI(self):
        for kind in ('missing','duplicate','changed','later','light','badfraction'):
            raw=probe();s=raw['frames'][0]['side_data_list']
            if kind=='missing':s.pop(0)
            elif kind=='duplicate':s.append(copy.deepcopy(s[0]))
            elif kind=='changed':s[0]['green_x']='13251/50000'
            elif kind=='light':s[1]['max_average']=401
            elif kind=='badfraction':s[0]['max_luminance']='1/0'
            else:
                raw['frames'].append(copy.deepcopy(raw['frames'][0]));raw['frames'][-1]['side_data_list'][0]['red_y']='1/10'
            with self.subTest(kind=kind),self.assertRaises(AppError):verify_probe(raw,DECLARATION)

    def test_probe_requires_actual_matching_hevc_ten_bit_PQ_VUI(self):
        for key,value in [('pix_fmt','yuv420p'),('codec_name','h264'),('color_transfer','arib-std-b67'),('color_range','pc')]:
            raw=probe();raw['streams'][0][key]=value
            with self.subTest(key=key),self.assertRaises(AppError):verify_probe(raw,DECLARATION)

    def test_probe_malformed_transport_is_structured_error(self):
        for raw in (None,[],{},dict(streams=[],frames=[]),dict(streams=[None],frames=[{}]),
                    dict(streams=probe()['streams'],frames=[None]),
                    dict(streams=probe()['streams'],frames=[dict(side_data_list=[None])])):
            with self.subTest(raw=raw),self.assertRaises(AppError):verify_probe(raw,DECLARATION)


class MetadataIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_float_hdr import HDRIntegrationTests
        self.h=HDRIntegrationTests('runTest');self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.f=self.h.f;self.h.source()
        s=self.f.p['settings'];s['output']['video'].update(codec='libx265',pixel_format='yuv420p10le',crf=10)
        s['output']['hdr10']=copy.deepcopy(DECLARATION)

    def test_actual_HEVC_SEI_is_verified_before_publishing(self):
        result=self.f.execute();r=result['delivery']['hdr10_static_metadata']
        self.assertEqual(r['status'],'verified');self.assertEqual(r['verified_decoded_frames'],8)
        self.assertEqual(r['declaration'],DECLARATION)
        self.assertEqual(verify_output(result['path'],DECLARATION)['verified_decoded_frames'],8)
        manifest=json.loads(Path(result['manifest']).read_bytes())
        self.assertEqual(manifest['delivery']['hdr10_static_metadata'],r)
        RECEIPTS.append(dict(test=self.id(),result=result));self.f.assert_clean()

    def test_actual_unknown_content_levels_are_written_as_zero(self):
        self.f.p['settings']['output']['hdr10']['content_light']=dict(max_cll_nits=0,max_fall_nits=0)
        r=self.f.execute();self.assertEqual(r['delivery']['hdr10_static_metadata']['declaration']['content_light'],dict(max_cll_nits=0,max_fall_nits=0))
        RECEIPTS.append(dict(test=self.id(),result=r));self.f.assert_clean()

    def test_actual_MP4_main10_and_SEI_are_retained(self):
        self.f.p['settings']['output'].update(container='mp4',audio=dict(codec='aac',bitrate='128k'))
        r=self.f.execute('actual.mp4');self.assertEqual(r['probe']['video']['codec'],'hevc')
        self.assertEqual(r['delivery']['hdr10_static_metadata']['verified_decoded_frames'],8)
        RECEIPTS.append(dict(test=self.id(),result=r));self.f.assert_clean()

    def test_metadata_absent_after_real_encoder_prevents_replacing_existing_delivery(self):
        target=self.f.root/'renders/keep.mkv';target.write_bytes(b'old complete delivery')
        save_project(self.f.root,self.f.p);before=(self.f.root/'project.json').read_bytes()
        with patch('ai_ad_editor.hdr_metadata.encoder_arguments',return_value=[]),self.assertRaises(AppError) as c:
            self.f.execute('keep.mkv')
        self.assertEqual(c.exception.code,'HDR_METADATA_MISSING')
        self.assertEqual(target.read_bytes(),b'old complete delivery')
        self.assertFalse(target.with_suffix('.mkv.manifest.json').exists())
        self.assertEqual((self.f.root/'project.json').read_bytes(),before)
        operations=[json.loads(p.read_bytes()) for p in (self.f.root/'operations').glob('render*.json')]
        self.assertTrue(any(v.get('error',{}).get('code')=='HDR_METADATA_MISSING' for v in operations))
        RECEIPTS.append(dict(test=self.id(),rejection=c.exception.as_dict(),prior_delivery_preserved=True))
        self.f.assert_clean()

    def test_configuration_rejects_SDR_HLG_legacy_eight_bit_wrong_encoder_and_full_range(self):
        settings=self.f.p['settings']
        variants=[]
        for field,value in [('codec','libx264'),('pixel_format','yuv420p'),('pixel_format','yuv444p10le')]:
            s=copy.deepcopy(settings);s['output']['video'][field]=value;variants.append(s)
        for transfer in ('srgb','hlg-bt2100'):
            s=copy.deepcopy(settings);s['pixel_pipeline']['output_signal']['transfer']=transfer;variants.append(s)
        s=copy.deepcopy(settings);s.pop('pixel_pipeline');variants.append(s)
        s=copy.deepcopy(settings);s['color']['range']='full';variants.append(s)
        for s in variants:
            with self.subTest(settings=s),self.assertRaises(AppError) as c:output_settings(s)
            self.assertEqual(c.exception.code,'HDR_METADATA_CONTEXT')

    def test_schema_and_runtime_validate_explicit_metadata_without_rewriting(self):
        save_project(self.f.root,self.f.p);before=(self.f.root/'project.json').read_bytes()
        self.assertEqual(list(make_validator().iter_errors(self.f.p)),[])
        code,r=self.f.invoke('validate','--project',self.f.root);self.assertEqual(code,0,r)
        bad=copy.deepcopy(self.f.p);bad['settings']['output']['hdr10']['content_light']['max_cll_nits']=True
        self.assertTrue(list(make_validator().iter_errors(bad)))
        bad=copy.deepcopy(self.f.p);bad['settings'].pop('pixel_pipeline')
        self.assertTrue(list(make_validator().iter_errors(bad)))
        self.assertEqual(before,(self.f.root/'project.json').read_bytes())

    def test_dry_run_contains_fixed_declaration_and_SEI_flags_without_publication(self):
        r=self.f.execute(dry_run=True);self.assertEqual(r['status'],'planned')
        self.assertEqual(r['plan']['encoder']['hdr10'],DECLARATION)
        self.assertIn('-x265-params',r['plan']['command'])
        self.assertFalse(Path(r['plan']['output']).exists());self.f.assert_clean()

    def test_SDR_previews_preserve_HDR_author_declaration_and_have_no_HDR_SEI(self):
        save_project(self.f.root,self.f.p);before=(self.f.root/'project.json').read_bytes()
        code,r=self.f.invoke('preview','range','--project',self.f.root,'--start-frame','0','--end-frame','3','--height','64')
        self.assertEqual(code,0,r);self.assertFalse(r['data']['request']['HDR_reference_preserved'])
        self.assertEqual(before,(self.f.root/'project.json').read_bytes());self.f.assert_clean()
        RECEIPTS.append(dict(test=self.id(),result=r['data']))

    def test_editable_package_retains_declaration_and_identical_decoded_picture(self):
        f=self.f;first=f.execute('before.mkv');archive=f.root/'exports/hdr10.zip'
        code,r=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package');self.assertEqual(code,0,r)
        restored=f.base/'restored';code,r=f.invoke('convert','import','--input',archive,'--output',restored);self.assertEqual(code,0,r)
        _,p=load_project(restored);self.assertEqual(p['settings']['output']['hdr10'],DECLARATION)
        with project_write_lock(restored):second=render_project(restored,p,p['sequences'][0],restored/'renders/after.mkv')
        self.assertEqual(second['delivery']['hdr10_static_metadata']['declaration'],DECLARATION)
        self.assertEqual(f.decode_y(first['path'],32,16).tobytes(),f.decode_y(second['path'],32,16).tobytes())
        RECEIPTS.append(dict(test=self.id(),before=first,after=second));f.assert_clean()

    def test_probe_respects_cancel_before_start_and_never_publishes(self):
        marker=self.f.root/'cancel';marker.write_text('cancel')
        with self.assertRaises(AppError) as c:verify_output(self.f.root/'not-created.mkv',DECLARATION,cancel_file=marker)
        self.assertEqual(c.exception.code,'CANCELLED');self.f.assert_clean()


if __name__=='__main__':unittest.main()
