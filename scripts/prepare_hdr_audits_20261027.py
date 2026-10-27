"""Derive byte/history audits with HDR-specific actual case checks."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
baseline='af9fc64391945901a641fc33b86438d26754a00d'
def common(s):
    for old,new in [('highlight-glow','native-hdr'),('cb69d750a67ce5705e4845ecad560604d669e824',baseline),
        ('alpha.4-local.37','alpha.4-local.38'),('0.1.39','0.1.40'),('r40','r41'),
        ('installation-final-r2','installation-final-r1'),('unpacked-r2','unpacked-r1'),
        ('8eccc163d7a6fd937d7fa3b0409922a40c264038df43823e05b3f90f9746e5f3','ea1e439a7ffb6ca7da065cc2ddd872b6b567d47e9275a0dd8b40ee099c5340f4')]:s=s.replace(old,new)
    for old,new in [('239','240'),('734','993'),('124','126')]:s=re.sub(r'(?<!\d)'+old+r'(?!\d)',new,s)
    s=re.sub(r'(?<!\d)78(?!\d)','79',s)
    return s

for original,target in [('audit_highlight_glow_stage_20261027.py','audit_hdr_stage_20261027.py'),
                         ('verify_highlight_glow_postpush_20261027.py','verify_hdr_postpush_20261027.py')]:
    s=common((ROOT/'scripts'/original).read_text('utf8')).replace('installed optical delivery','installed HDR delivery')
    (ROOT/'scripts'/target).write_text(s,encoding='utf8',newline='\n')

s=common((ROOT/'scripts/audit_highlight_glow_20261027.py').read_text('utf8'))
s=s.replace("'scripts/test_float_glow_20261027.py'","'scripts/test_hdr_20261027.py'")
s=s.replace("[('source-glow-r2',21),('source-glow-gpu-r2',3),('source-glow-integration-r1',6)]", "[('source-numeric-r4',12),('source-compat-r1',239)]")
start=s.index("        case=load(BASE/'case-r1/verification.json')")
end=s.index("        namespace=load(ROOT/",start)
block="""        case=load(BASE/'case-r3/verification.json')
        assert case['status']=='passed' and case['all_48_decoded_10bit_frames_equal'] and case['all_384000_PCM_equal'] and case['PCM_nonzero']
        assert case['editable_absolute_signals_preserved'] and case['author_bytes_unchanged_by_preview'] and case['GIF_frames']==48 and case['GIF_duration_ms']==4000
        assert not case['source_fallback'] and case['registered_skill'] and not case['HDR_monitor_accepted'] and not case['natural_quality_accepted']
        assert load(BASE/'case-r3/version.stdout.json')['data']['cli_version']=='0.1.40'
        work=ROOT/'local/agent-ffmpeg/native-hdr-case-r3'
        for group,names,expected_bytes,digest in [
            ('video',['decode-pq.bin','decode-restored.bin'],48*640*360*6,case['decoded_video_sha256']),
            ('audio',['audio-pq.bin','audio-restored.bin'],384000*4,case['decoded_PCM_sha256'])]:
            for name in names:assert (work/name).stat().st_size==expected_bytes and sha(work/name)==digest
        media=Path(case['public']);m=load(media/'media-manifest.json');assert m['frames']==48 and m['fps']==12 and m['duration_seconds']==4
        for r in m['files']:assert sha(media/r['path'])==r['sha256'] and (media/r['path']).stat().st_size==r['bytes']
        assert sha(media/'editable-native-hdr.aevpkg.zip')==case['package_sha256']
        for name,transfer in [('pq','smpte2084'),('hlg','arib-std-b67'),('sdr','iec61966-2-1')]:
            assert case['streams'][name]['color_transfer']==transfer and case['streams'][name]['pix_fmt']=='yuv444p10le'
            manifest=load(media/(name+'-master.mkv.manifest.json'))
            assert manifest['delivery']['pixel_pipeline']['transport']['frames']==48
            g=manifest['delivery']['pixel_pipeline']['projection_acceleration']
            assert g['operations']['glow']==48 and g['worker_closed'] and g['shared_handles_closed']
            assert g['control']['threads_closed'] and g['control']['streams_closed'] and not g['runtime_failure_CPU_fallback']
            assert g['probe']['actual_gpu_operations']==17 and g['probe']['glow_gpu_operations']==8
        review=load(BASE/'static-chart-review.json');assert review['status']=='reviewed' and not review['continuous_human_playback'] and not review['human_listening'] and not review['HDR_monitor_accepted']
        for name,digest in review['files'].items():assert sha(media/name)==digest
        usage=load(BASE/'documented-workflow-r1/verification.json')
        assert usage['status']=='passed' and usage['exact_documented_workflow_executed'] and usage['all_48_frames_match_case'] and usage['CLI_calls']==5
        assert usage['guide_sha256']==sha(ROOT/'docs/product/HDR_DISPLAY.md')
"""
s=s[:start]+block+s[end:]
s=s.replace("'docs/product/HIGHLIGHT_GLOW.md'", "'docs/product/HDR_DISPLAY.md'")
s=s.replace("assert caps['highlight_glow']['protocol']=='highlight-derived-separable-float32-glow-v1'", "assert caps['native_hdr_display_pipeline']['protocol']=='explicit-display-nits-PQ-HLG-float32-v1'")
s=s.replace("len(old)==265 and len(rows(text,'R'))==271", "len(old)==271 and len(rows(text,'R'))==277")
s=s.replace("len(rows(text,'F'))==65", "len(rows(text,'F'))==66").replace("len(rows(manual,'F'))==65", "len(rows(manual,'F'))==66")
s=s.replace("local.37/final-r2/installed", "local.38/final-r1/installed")
s=s.replace("glow_effects=2,animated_case_tracks=6", "HDR_transfers=2,actual_HDR_SDR_case=True")
s=s.replace("readme_prior_R_rows_preserved=265,readme_R_rows=271", "readme_prior_R_rows_preserved=271,readme_R_rows=277")
(ROOT/'scripts/audit_hdr_20261027.py').write_text(s,encoding='utf8',newline='\n')
print('Prepared HDR audits; no product/test mutations or new rendering.')
