"""Actual native pixels: independent geometry, cuts, nested clocks and reuse."""
from decimal import Decimal, localcontext
import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import unittest

from PIL import Image
from ai_ad_editor.clip_windows import slice_clip
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import load_project, save_project
from ai_ad_editor.render import build_filter_graph
import test_motion_pack as helpers
from test_magnetic_reorder import invoke


class MotionPackNative(unittest.TestCase):
    setUpClass=classmethod(lambda cls:helpers.MotionPackCLI.setUpClass())
    setUp=helpers.MotionPackCLI.setUp
    command=helpers.MotionPackCLI.command
    apply=helpers.MotionPackCLI.apply

    def render(self, project, sequence=None):
        sequence=sequence or project['sequences'][0]
        inputs,graph,metadata,warnings=build_filter_graph(self.root,project,sequence)
        canvas=sequence.get('canvas') or project['settings']['canvas'];w,h=canvas['width'],canvas['height']
        script=self.work/'native-graph.txt';script.write_text(graph,encoding='utf8')
        result=subprocess.run([ffmpeg_path(),'-hide_banner','-v','error','-filter_threads','1','-filter_complex_threads','1',
            *map(str,inputs),'-filter_complex_script',str(script),'-map','[vout]','-fps_mode','passthrough',
            '-f','rawvideo','-pix_fmt','rgba','pipe:1','-map','[aout]','-f','null','NUL'],
            cwd=self.root,capture_output=True,timeout=120)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        fps=project['settings']['timebase']['display_fps'];rate=Fraction(fps['num'],fps['den'])
        count=math.ceil(Fraction(sequence['duration_tick'],90000)*rate);size=w*h*4
        self.assertEqual(len(result.stdout),count*size)
        return [result.stdout[n*size:(n+1)*size] for n in range(count)],(w,h)

    def configure(self):
        p=load_project(self.root)[1]
        p['settings']['canvas']={'width':160,'height':90,'background':'#000000'}
        p['settings']['timebase']={'ticks_per_second':90000,'display_fps':{'num':24,'den':1}}
        save_project(self.root,p)
        return p

    def centroid(self,raw,size):
        w,h=size;points=[(i%w,i//w) for i in range(w*h) if raw[i*4]>180 and raw[i*4+1]<90 and raw[i*4+2]<90]
        self.assertTrue(points,'red reference marker must remain visible')
        return sum(x for x,y in points)/len(points),sum(y for x,y in points)/len(points)

    def test_actual_orbit_pixels_follow_independent_analytic_circle(self):
        self.configure();self.apply('--name','orbit_focus','--param','zoom=0','--param','radius=0.12')
        p=load_project(self.root)[1];frames,size=self.render(p)
        for n,raw in enumerate(frames):
            x,y=self.centroid(raw,size);phase=2*math.pi*n/48
            self.assertLessEqual(abs(x-(80+19.2*math.cos(phase))),2.1,(n,x))
            self.assertLessEqual(abs(y-(45+6.48*math.sin(phase))),2.1,(n,y))

    def test_split_presentation_windows_retain_identical_author_motion_pixels(self):
        self.configure();self.apply('--name','bezier_sweep')
        p=load_project(self.root)[1];before,size=self.render(p)
        original=p['sequences'][0]['tracks'][0]['clips'][0]
        p['sequences'][0]['tracks'][0]['clips']=[slice_clip(original,0,90000,clip_id='left'),
                                                slice_clip(original,90000,180000,clip_id='right')]
        after,_=self.render(p)
        self.assertEqual(after,before)

    def test_nonlinear_nested_reverse_samples_author_clock_instead_of_parent_progress(self):
        self.configure();self.apply('--name','orbit_focus','--param','zoom=0','--param','radius=0.12')
        p=load_project(self.root)[1];child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        for t in child['tracks']:t['id']='child_'+t['id']
        with localcontext() as ctx:
            ctx.prec=50;duration=int((Decimal(2)*Decimal(3).ln()*90000).to_integral_value())
        root=p['sequences'][0];root['duration_tick']=duration
        root['tracks'][0]['clips']=[dict(id='parent',sequence_id='child',timeline_start_tick=0,
            duration_tick=duration,source_in_tick=0,source_out_tick=180000,reverse=True,
            speed_curve=dict(keyframes=[dict(at_tick=0,speed=.5),dict(at_tick=180000,speed=1.5)]))]
        p['sequences'].append(child)
        frames,size=self.render(p)
        for n,raw in enumerate(frames):
            # Integral inversion of ds/dt = .5 + s/2, evaluated backwards.
            progress=1-Fraction(n*90000,24*duration)
            if progress<0:continue
            source_seconds=3**float(progress)-1
            phase=math.pi*source_seconds
            x,y=self.centroid(raw,size)
            self.assertLessEqual(abs(x-(80+19.2*math.cos(phase))),2.1,(n,x,source_seconds))
            self.assertLessEqual(abs(y-(45+6.48*math.sin(phase))),2.1,(n,y,source_seconds))

    def test_capture_reuses_native_easing_in_another_canvas_and_duration(self):
        self.configure();self.apply('--name','arc_push','--param','zoom=0')
        original=load_project(self.root)[1];a,size=self.render(original)
        output=self.work/'reuse.json'
        self.command('capture','--project',self.root,'--clip-id','hero','--id','reuse','--title','Reuse',
            '--creator','test','--license','MIT','--output',output)
        p=load_project(self.root)[1];p['sequences'][0]['tracks'][0]['clips'][0].pop('keyframes')
        p['settings']['canvas']['width']=320;p['settings']['canvas']['height']=180
        p['sequences'][0]['duration_tick']=360000
        target=p['sequences'][0]['tracks'][0]['clips'][0];target['duration_tick']=360000;target['source_out_tick']=360000
        save_project(self.root,p);self.apply('--input',output)
        b,new_size=self.render(load_project(self.root)[1])
        for n in range(len(a)):
            x,y=self.centroid(a[n],size);xx,yy=self.centroid(b[n*2],new_size)
            self.assertLessEqual(abs(xx/2-x),1.5)
            self.assertLessEqual(abs(yy/2-y),1.5)

    def test_all_six_recipes_produce_distinct_fully_decodable_native_frames(self):
        self.configure();fingerprints=set()
        for name in ('orbit_focus','arc_push','bezier_sweep','whip_settle','breathe_float','detail_scan'):
            p=load_project(self.root)[1];p['sequences'][0]['tracks'][0]['clips'][0].pop('keyframes',None);save_project(self.root,p)
            self.apply('--name',name)
            frames,size=self.render(load_project(self.root)[1])
            self.assertEqual(len(frames),48)
            for raw in frames:self.centroid(raw,size)
            import hashlib
            fingerprints.add(hashlib.sha256(b''.join(frames)).hexdigest())
        self.assertEqual(len(fingerprints),6)


if __name__=='__main__':unittest.main()
