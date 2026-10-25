"""Native RGBA equivalence, independent geometry and slice/timestamp isolation."""
from __future__ import annotations

import math
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from PIL import Image, ImageDraw

from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.motion_pack import builtin, compile_pack
from ai_ad_editor.render import _affine_video_filters, _expr_arg, _transform_exprs
from ai_ad_editor.runtime import configure_local_runtime


def legacy_affine(transform):
    """Frozen 0de972db/CLI 0.1.16 sampler, retained as a regression oracle."""
    values = {k: re.sub(r'\bt\b', 'T', v) for k,v in transform.items()}
    angle = f"({values['rotation']})*PI/180"
    setup = (
        f"st(0,cos({angle}));st(1,sin({angle}));"
        f"st(2,X+0.5-({values['position_x']})*W);"
        f"st(3,Y+0.5-({values['position_y']})*H);"
        f"st(4,max(0.00000001,abs({values['scale']})));"
        f"st(5,({values['anchor_x']})*W+(ld(2)*ld(0)+ld(3)*ld(1))/ld(4)-0.5);"
        f"st(6,({values['anchor_y']})*H+(-ld(2)*ld(1)+ld(3)*ld(0))/ld(4)-0.5);"
        "st(7,gte(ld(5),-0.5)*lt(ld(5),W-0.5)*gte(ld(6),-0.5)*lt(ld(6),H-0.5));"
    )
    def plane(name):
        return _expr_arg(setup+f"if(ld(7),{name}(clip(ld(5),0,W-1),clip(ld(6),0,H-1)),0)")
    return ['format=gbrapf32le', 'premultiply=inplace=1',
            f"geq=r={plane('r')}:g={plane('g')}:b={plane('b')}:a={plane('alpha')}:interpolation=bilinear",
            'unpremultiply=inplace=1', 'format=rgba']


class AffineScanlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.image = Image.new('RGBA', (77, 61))
        self.image.putdata([((x*23)%256, (y*31)%256, ((x+y)*17)%256,
                             (0, 23, 128, 255)[(x+y)%4]) for y in range(61) for x in range(77)])
        self.image.save(self.base/'pattern.png')

    def transform(self, **values):
        result = dict(scale='0.91', rotation='23+T*31', position_x='0.47',
                      position_y='0.53', anchor_x='0.39', anchor_y='0.62', opacity='1')
        result.update(values)
        return result

    def render(self, transform, *, legacy=False, threads=1, clock=None, frames=4, image=None):
        source = self.base/'input.png'
        (image or self.image).save(source)
        filters = ["format=rgba"]
        if clock:
            filters.append('setpts='+_expr_arg(clock))
        filters.extend((legacy_affine if legacy else _affine_video_filters)(transform))
        script = self.base/'graph.txt'; script.write_text(','.join(filters), encoding='utf8')
        result = subprocess.run([ffmpeg_path(), '-hide_banner', '-v', 'error', '-filter_threads', str(threads),
            '-loop', '1', '-framerate', '4', '-i', str(source), '-filter_script:v', str(script),
            '-frames:v', str(frames), '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1'],
            capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf8', 'replace'))
        self.assertEqual(len(result.stdout), 77*61*4*frames)
        return result.stdout

    def compare(self, transform, **options):
        actual = self.render(transform, **options)
        expected = self.render(transform, legacy=True, **options)
        self.assertEqual(actual, expected)
        self.assertGreater(max(actual[3::4]), 100, 'An invisible frame cannot prove equivalence')
        return actual

    def test_static_extreme_anchors_rotations_and_scales_match_old_pixels(self):
        for angle, scale, anchor in ((0,1,.5), (90,.4,0), (-31,1.7,1), (379,.9,.27)):
            with self.subTest(angle=angle):
                self.compare(self.transform(rotation=str(angle), scale=str(scale), anchor_x=str(anchor)))

    def test_all_sampled_motion_paths_match_legacy_with_forced_affine(self):
        for name in ('orbit_focus','arc_push','bezier_sweep','whip_settle','breathe_float','detail_scan'):
            with self.subTest(name=name):
                clip = dict(id='hero', duration_tick=90000, timeline_start_tick=0,
                            source_in_tick=0, source_out_tick=90000)
                clip, _, _ = compile_pack(builtin(name), clip)
                self.compare(_transform_exprs(clip, 0, 90000))

    def test_slice_threads_have_identical_independent_state(self):
        transform = self.transform(scale='.7+T*.2', position_x='.4+T*.2', anchor_y='.3+T*.1')
        reference = self.compare(transform, threads=1)
        for threads in (2, 7):
            with self.subTest(threads=threads):
                self.assertEqual(self.compare(transform, threads=threads), reference)

    def test_repeated_and_backward_timestamps_do_not_reuse_another_frame(self):
        self.compare(self.transform(), threads=7, clock='if(lt(N,2),2,if(eq(N,2),1,3))/TB')

    def test_bezier_hold_nonzero_start_and_nested_reverse_clock(self):
        clip = dict(timeline_start_tick=45000, keyframes=[
            dict(property='transform.rotation', keyframes=[
                dict(at_tick=0, value=-30, interpolation='bezier', control_points=[.2,.1,.8,.9]),
                dict(at_tick=90000, value=45, interpolation='hold')]),
            dict(property='transform.position.x', keyframes=[
                dict(at_tick=0,value=.3,interpolation='hold'), dict(at_tick=45000,value=.7)])])
        from ai_ad_editor.time_mapping import make_map
        mapping = make_map(dict(timeline_start_tick=45000, source_in_tick=0, source_out_tick=90000,
            duration_tick=90000, reverse=True), [], 90000)
        clip['_nested_keyframe_clock'] = dict(maps=[mapping], authored_start=0)
        self.compare(_transform_exprs(clip, .5, 90000), threads=7, clock='(N/4+0.5)/TB')

    def test_transparent_hidden_rgb_does_not_pollute_partial_alpha(self):
        first = self.image.copy(); second = self.image.copy()
        for y in range(61):
            for x in range(77):
                if not first.getpixel((x,y))[3]:
                    first.putpixel((x,y),(0,0,0,0)); second.putpixel((x,y),(0,255,0,0))
        a = self.compare(self.transform(), threads=7, image=first)
        b = self.compare(self.transform(), threads=7, image=second)
        self.assertEqual(a,b)

    def test_pixel_dependent_and_stateful_expressions_keep_legacy_semantics(self):
        for transform in (self.transform(rotation='T*17+X*.1'),
                          self.transform(position_x='0.5+st(8,0.02)'),
                          self.transform(scale='1+ld(9)*0')):
            with self.subTest(transform=transform):
                self.compare(transform, threads=2)

    def test_marker_follows_independent_forward_rotation_geometry(self):
        image = Image.new('RGBA', (77,61), (0,0,0,0))
        ImageDraw.Draw(image).ellipse((47,22,51,26), fill=(255,0,0,255))
        transform = self.transform(rotation='-20+T*60', scale='0.8', position_x='.5',
                                   position_y='.5', anchor_x='.5', anchor_y='.5')
        raw = self.render(transform, image=image, threads=7)
        size = 77*61*4
        for frame in range(4):
            data = raw[frame*size:(frame+1)*size]
            points = [(i%77,i//77) for i in range(77*61) if data[i*4] > 200 and data[i*4+3] > 100]
            self.assertTrue(points)
            actual = tuple(sum(p[axis] for p in points)/len(points) for axis in (0,1))
            angle = math.radians(-20+frame/4*60)
            dx,dy = (49+.5-77*.5)*.8,(24+.5-61*.5)*.8
            expected = (77*.5+dx*math.cos(angle)-dy*math.sin(angle)-.5,
                        61*.5+dx*math.sin(angle)+dy*math.cos(angle)-.5)
            for a,b in zip(actual,expected):self.assertLessEqual(abs(a-b),.65)


if __name__ == '__main__':
    unittest.main()
