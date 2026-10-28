"""Actual unified Skill HDR420/PQ/HLG render, independent post-codec oracle and replay."""
from pathlib import Path
from fractions import Fraction
import argparse,copy,hashlib,json,math,shutil,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'
PS=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File']
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8',newline='\n')
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')

def oracle(raw,probe,signal):
 frames=probe['frames'];stream=probe['streams'][0];w,h=stream['width'],stream['height'];tb=Fraction(stream['time_base'])
 cw,ch=(w+1)//2,(h+1)//2;stride=w*h+2*cw*ch
 data=np.memmap(raw,dtype='<u2',mode='r',shape=(len(frames),stride));payload=hashlib.sha256();clock=hashlib.sha256()
 xy=np.array([[.708,.292],[.170,.797],[.131,.046]]);xyz=np.array([[x/y,1,(1-x-y)/y] for x,y in xy]).T
 luma=np.linalg.solve(xyz,np.array([.3127/.329,1,(1-.3127-.329)/.329]))
 xc=np.clip(np.arange(w)/2,0,cw-1);yc=np.clip((np.arange(h)-.5)/2,0,ch-1)
 y0=np.floor(yc).astype(int);y1=np.minimum(y0+1,ch-1);dy=yc-y0
 def upsample(plane):
  horizontal=np.stack([np.interp(xc,np.arange(cw),row) for row in plane])
  return horizontal[y0]*(1-dy[:,None])+horizontal[y1]*dy[:,None]
 peaks={};falls={};weighted=dict(maxrgb=0.,cie_y=0.);duration=Fraction(0);minimum=float('inf');negative=over=0
 for i,frame in enumerate(frames):
  planes=data[i];yy=(planes[:w*h].reshape(h,w).astype(np.float64)-64)/876
  u=(upsample(planes[w*h:w*h+cw*ch].reshape(ch,cw))-512)/896
  v=(upsample(planes[w*h+cw*ch:].reshape(ch,cw))-512)/896
  kr,kb=.2627,.0593;kg=1-kr-kb
  rgb=np.stack([yy+2*(1-kr)*v,yy-2*kb*(1-kb)/kg*u-2*kr*(1-kr)/kg*v,yy+2*(1-kb)*u],axis=-1).astype(np.float32)
  rgba=np.ones((h,w,4),np.float32);rgba[:,:,:3]=rgb;payload.update(rgba.astype('<f4').tobytes())
  negative+=int(np.count_nonzero(rgb<0));over+=int(np.count_nonzero(rgb>1))
  encoded=np.clip(rgb.astype(np.float64),0,1)
  if signal['transfer']=='pq-st2084':
   q=encoded**(1/(2523/32));light=(np.maximum(q-3424/4096,0)/(2413/128-2392/128*q))**(1/(2610/16384))*10000
  else:
   peak=signal['display_peak_nits'];gamma=signal['system_gamma'];black=signal.get('display_black_nits',0)
   beta=math.sqrt(3*(black/peak)**(1/gamma)) if black else 0
   encoded=(1-beta)*encoded+beta;a=.17883277;b=1-4*a;c=.5-a*math.log(4*a)
   scene=np.where(encoded<=.5,encoded**2/3,(np.exp((encoded-c)/a)+b)/12)
   y=scene[:,:,0]*.2627+scene[:,:,1]*.6780+scene[:,:,2]*.0593
   scale=np.zeros_like(y);np.power(y,gamma-1,out=scale,where=y>0)
   light=scene*scale[:,:,None]*peak
  minimum=min(minimum,float(np.min(light)))
  metrics=dict(maxrgb=np.max(light,axis=-1),cie_y=light[:,:,0]*luma[0]+light[:,:,1]*luma[1]+light[:,:,2]*luma[2])
  dt=int(frame.get('duration',frame.get('pkt_duration',0)))*tb;assert dt>0;duration+=dt
  record=canonical(dict(frame=i,pts=int(frame['best_effort_timestamp']),duration=int(frame.get('duration',frame.get('pkt_duration',0))),time_base=str(tb)))
  clock.update(len(record).to_bytes(8,'big'));clock.update(record)
  for key,values in metrics.items():
   value=float(np.max(values));average=float(np.mean(values));pos=int(np.argmax(values));y,x=divmod(pos,w)
   if key not in peaks or value>peaks[key]['nits']:peaks[key]=dict(nits=value,frame=i,x=x,y=y)
   if key not in falls or average>falls[key]['nits']:falls[key]=dict(nits=average,frame=i)
   weighted[key]+=average*float(dt)
 del data
 return dict(frames=len(frames),pixels=len(frames)*w*h,peak_pixel=peaks,maximum_frame_average=falls,
  duration_weighted_frame_average_nits={k:v/float(duration) for k,v in weighted.items()},minimum_RGB_component_nits=minimum,
  decoded_RGBA32_sha256='sha256:'+payload.hexdigest(),native_clock_sha256='sha256:'+clock.hexdigest(),
  analyzed_duration_seconds=str(duration),negative_components=negative,over_one_components=over,
  no_product_colour_or_meter_helpers=True,upsampling='independent two-pass numpy.interp horizontal and vertical bilinear; explicit left progressive')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
 out=BASE/('installed-case-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 work=ROOT/'local/agent-ffmpeg'/('native-hdr-media-installed-case-'+a.run);work.mkdir(exist_ok=False)
 public=ROOT/'docs/assets'/('native-hdr-media-installed-20261029-'+a.run);public.mkdir(exist_ok=False)
 namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';pin=sha(namespace)
 assert SKILL.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
 assert json.loads(namespace.read_bytes())['cli_version']=='0.1.50'
 calls=[];checks=[];ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
 def call(name,argv,json_cli=False,allow_failure=False,output=None):
  result=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
  (out/(name+'.stderr.txt')).write_bytes(result.stderr)
  dest=output or out/(name+'.stdout.json');dest.write_bytes(result.stdout)
  calls.append(dict(name=name,argv=list(map(str,argv)),exit_code=result.returncode,stdout_sha256=sha(dest),stdout_bytes=len(result.stdout),json_cli=json_cli));save(out/'calls.json',calls)
  print(json.dumps(dict(name=name,exit_code=result.returncode)),flush=True)
  if not allow_failure:assert result.returncode==0,(name,result.stdout[-2000:],result.stderr[-2000:])
  if json_cli:
   v=json.loads(result.stdout);assert v['provenance']['cli_version']=='0.1.50'
   if not allow_failure:assert v['ok'],v
   return v
  return result.stdout
 def cli(name,*argv,allow_failure=False):return call(name,[*PS,SKILL/'scripts/run.ps1',*argv],True,allow_failure)
 def check(name,condition):
  checks.append(dict(name=name,passed=bool(condition)));save(out/'checks.json',checks);assert condition,name
 cli('version','version')
 project=work/'project';cli('import','convert','import','--input',ROOT/'docs/assets/native-hdr-measure-20261029-r2/editable-hdr-measure.aevpkg.zip','--output',project)
 p=json.loads((project/'project.json').read_bytes());original=copy.deepcopy(p);sequence=p['sequences'][0]['id'];results={}
 for label,signal,transfer in [
  ('pq420',dict(primaries='bt2020',transfer='pq-st2084',reference_white_nits=203),'smpte2084'),
  ('hlg420',dict(primaries='bt2020',transfer='hlg-bt2100',reference_white_nits=203,display_peak_nits=1000,system_gamma=1.2,display_black_nits=1),'arib-std-b67')]:
  p=copy.deepcopy(original);p['settings']['output']['video'].update(codec='libx265',crf=18,preset='ultrafast',pixel_format='yuv420p10le')
  p['settings']['color'].update(primaries='bt2020',transfer=transfer,matrix='bt2020nc',range='limited')
  p['settings']['pixel_pipeline'].update(output_signal=signal,range_policy='clip')
  save(project/'project.json',p);save(out/(label+'-project.json'),p);signal_file=project/(label+'-signal.json');save(signal_file,signal)
  cli(label+'-validate','validate','--project',project)
  movie=project/'renders'/(label+'.mkv');cli(label+'-render','render','--project',project,'--sequence-id',sequence,'--output',movie)
  before=dict(project=sha(project/'project.json'),movie=sha(movie),signal=sha(signal_file))
  args=['surface','measure-media','--project',project,'--input',movie,'--signal-json',signal_file,'--pixel-family','yuv',
        '--yuv-matrix','bt2020nc','--yuv-range','limited','--chroma-location','left','--scan','progressive']
  cli(label+'-dryrun',*args,'--dry-run')
  response=cli(label+'-reject',*args,allow_failure=True);rejected=not response['ok']
  if rejected:
   check(label+'-only-range-rejection',response['errors'][0]['code']=='HDR_MEASURE_RANGE')
   response=cli(label+'-clip',*args,'--range-policy','clip')
  meter=response['data'];save(public/(label+'-measurement.json'),meter)
  raw=work/(label+'.yuv');call(label+'-decode',[ffmpeg,'-nostdin','-v','error','-noautorotate','-i',movie,'-map','0:v:0','-an','-sn','-dn','-fps_mode','passthrough','-pix_fmt','yuv420p10le','-f','rawvideo','pipe:1'],output=raw)
  probe=json.loads(call(label+'-probe',[ffprobe,'-v','error','-select_streams','v:0','-show_frames','-show_streams','-of','json',movie]))
  stream=probe['streams'][0];check(label+'-native-Main10-VUI',stream['codec_name']=='hevc' and stream['pix_fmt']=='yuv420p10le' and stream['color_primaries']=='bt2020' and stream['color_transfer']==transfer and stream['color_space']=='bt2020nc' and stream['color_range']=='tv' and stream['chroma_location']=='left')
  independent=oracle(raw,probe,signal);save(out/(label+'-independent-oracle.json'),independent)
  check(label+'-full-decoded-pixel-and-clock',meter['decoded_RGBA32_sha256']==independent['decoded_RGBA32_sha256'] and meter['native_clock_sha256']==independent['native_clock_sha256'])
  errors=[]
  for key in ('maxrgb','cie_y'):
   errors += [abs(meter['peak_pixel'][key]['nits']-independent['peak_pixel'][key]['nits']),abs(meter['maximum_frame_average'][key]['nits']-independent['maximum_frame_average'][key]['nits']),abs(meter['duration_weighted_frame_average_nits'][key]-independent['duration_weighted_frame_average_nits'][key])]
   check(label+'-'+key+'-peak-location',all(meter['peak_pixel'][key][k]==independent['peak_pixel'][key][k] for k in ('frame','x','y')))
  errors.append(abs(meter['minimum_RGB_component_nits']-independent['minimum_RGB_component_nits']))
  check(label+'-independent-light-math',max(errors)<1e-7)
  check(label+'-native-duration',meter['analyzed_duration_seconds']==independent['analyzed_duration_seconds'])
  check(label+'-range-counts',meter['range_counts']['negative_components']==independent['negative_components'] and meter['range_counts']['over_one_components']==independent['over_one_components'])
  check(label+'-readonly',before==dict(project=sha(project/'project.json'),movie=sha(movie),signal=sha(signal_file)))
  check(label+'-all-frames-cleanup',meter['frames']==48 and meter['all_source_frames_measured'] and meter['full_canvas_measured'] and meter['native_decoder_exit_code']==0 and meter['owned_threads_terminated'])
  shutil.copyfile(movie,public/movie.name);shutil.copyfile(movie.with_suffix(movie.suffix+'.manifest.json'),public/(label+'.manifest.json'))
  results[label]=dict(frames=meter['frames'],pixels=independent['pixels'],maximum_metric_error_nits=max(errors),reject_failed=rejected,
                      peak_pixel=meter['peak_pixel'],range_counts=meter['range_counts'],decoded_RGBA32_sha256=meter['decoded_RGBA32_sha256'])
 # Preserve editable author state and prove post-codec measurement survives an actual package replay.
 package=project/'renders/editable-hlg420.aevpkg.zip';cli('export','convert','export','--project',project,'--target-format','package','--output',package);shutil.copyfile(package,public/package.name)
 replay=work/'replay';cli('replay-import','convert','import','--input',package,'--output',replay)
 replay_movie=replay/'renders/hlg420.mkv';cli('replay-render','render','--project',replay,'--sequence-id',sequence,'--output',replay_movie)
 replay_signal=replay/'signal.json';save(replay_signal,signal)
 replay_measure=cli('replay-measure','surface','measure-media','--project',replay,'--input',replay_movie,'--signal-json',replay_signal,
     '--pixel-family','yuv','--yuv-matrix','bt2020nc','--yuv-range','limited','--chroma-location','left','--scan','progressive','--range-policy','clip')['data']
 check('package-replay-full-decoded-RGBA',replay_measure['decoded_RGBA32_sha256']==results['hlg420']['decoded_RGBA32_sha256'])
 pcm=[]
 for label,path in [('original',movie),('replay',replay_movie)]:
  target=work/(label+'-pcm.f32');call(label+'-pcm',[ffmpeg,'-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'],output=target);pcm.append(sha(target))
 check('package-replay-complete-PCM',pcm[0]==pcm[1] and (work/'original-pcm.f32').stat().st_size==1536000)
 cli('SDR-preview','preview','range','--project',project,'--sequence-id',sequence,'--start-frame','0','--end-frame','48','--height','360')
 # Locate exact exported preview paths from the structured response, not a browser recording.
 preview_report=json.loads((out/'SDR-preview.stdout.json').read_bytes())['data'];save(out/'preview-response.json',preview_report)
 frame=cli('SDR-frame','preview','frame','--project',project,'--sequence-id',sequence,'--frame','18','--height','360')['data']
 def find_media(value,suffix):
  for item in value.values():
   if isinstance(item,str) and item.lower().endswith(suffix) and Path(item).is_file():return Path(item)
  for item in value.values():
   if isinstance(item,dict):
    found=find_media(item,suffix)
    if found:return found
  return None
 for report,suffix,name in [(preview_report,'.mp4','author-SDR-preview.mp4'),(frame,'.png','author-SDR-frame.png')]:
  path=find_media(report,suffix);assert path;shutil.copyfile(path,public/name)
 call('gif',[ffmpeg,'-nostdin','-v','error','-i',public/'author-SDR-preview.mp4','-vf',
  'fps=6,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',public/'author-SDR-preview.gif'])

 check('namespace-unchanged',sha(namespace)==pin)
 save(public/'SOURCE.json',dict(license_spdx='CC0-1.0',source='Original C59 synthetic chart/stereo project, reused by CLI0.1.50',
   existing_source_package='docs/assets/native-hdr-measure-20261029-r2/editable-hdr-measure.aevpkg.zip',
   generated_movies=list(results),native_windows=True,virtualization=False,physical_HDR_acceptance=False))
 save(public/'media-manifest.json',dict(rights='CC0 original synthetic diagnostic project',preview_scope='authored timeline SDR mapping, not physical HDR or encoded-output viewing',files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file() and p.name!='media-manifest.json']))
 save(out/'verification.json',dict(status='passed',cases=results,checks=len(checks),process_calls=len(calls),
  installed_skill_used=True,cli_version='0.1.50',source_fallback=False,namespace_manifest_sha256=pin,
  package_replay_decoded_pixels_and_complete_PCM=True,new_model_forwards=0,new_renders=3,
  public_directory=str(public),preview_report=preview_report,physical_HDR_acceptance=False))
 print(json.dumps(dict(status='passed',cases=results,checks=len(checks))),flush=True)
if __name__=='__main__':main()
