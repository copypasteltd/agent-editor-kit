"""Reproduce candidate delivery/preview disagreement using only installed CLI."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--installed',type=Path,required=True);ap.add_argument('--expect-fixed',action='store_true');a=ap.parse_args()
 out=BASE/('preview-probe-'+a.run);out.mkdir(exist_ok=False);(out/'executed-probe.py').write_bytes(Path(__file__).read_bytes())
 project=ROOT/'local/agent-ffmpeg'/('oklab-preview-probe-'+a.run);calls=[]
 def cli(name,*args):
  cmd=[sys.executable,'-I','-S','-B','-X','utf8',str(a.installed/'run.py'),*map(str,args)]
  r=subprocess.run(cmd,cwd=ROOT,capture_output=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
  (out/(name+'.stdout.json')).write_bytes(r.stdout);(out/(name+'.stderr.txt')).write_bytes(r.stderr)
  v=json.loads(r.stdout);calls.append(dict(name=name,command=cmd,exit_code=r.returncode,ok=v['ok']))
  print(json.dumps(calls[-1]),flush=True);return v
 assert cli('import','convert','import','--input',ROOT/'docs/assets/oklab-gamut-20261029-r3/editable-oklab.aevpkg.zip','--output',project)['ok']
 # The historical low-level numerical fixture reused asset ID "sound" as
 # an audio clip ID. Repair only this owned import before CLI validation.
 author=json.loads((project/'project.json').read_bytes())
 author['sequences'][0]['tracks'][1]['clips'][0]['id']='audio_clip'
 (project/'project.json').write_text(json.dumps(author,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
 assert cli('validate','validate','--project',project)['ok']
 before=(project/'project.json').read_bytes()
 frame=cli('frame','preview','frame','--project',project,'--frame','9','--height','216')
 window=cli('range','preview','range','--project',project,'--start-frame','0','--end-frame','10','--height','216')
 assert before==(project/'project.json').read_bytes()
 if a.expect_fixed:
  assert frame['ok'] and window['ok'],(frame,window)
  for value,count in ((frame,1),(window,10)):
   data=value['data'];assert data['request']['display_mapping_source']=='display_mapping'
   transport=data['pixel_pipeline']['transport'];assert transport['frames']==count
   assert transport['owned_process_exit_code']==0 and transport['owned_threads_closed']
  corrected=project/'exports/corrected-oklab.aevpkg.zip'
  assert cli('export-corrected','convert','export','--project',project,'--output',corrected,'--target-format','package')['ok']
  replay=project.parent/(project.name+'-replay')
  assert cli('import-corrected','convert','import','--input',corrected,'--output',replay)['ok']
  assert cli('validate-corrected','validate','--project',replay)['ok']
  assert cli('preview-corrected','preview','frame','--project',replay,'--frame','9','--height','216')['ok']
  assert before==(project/'project.json').read_bytes()
  result=dict(status='passed',corrected_package=str(corrected),corrected_package_sha256=hashlib.sha256(corrected.read_bytes()).hexdigest(),
   installed=str(a.installed),source_fallback=False,calls=calls,
   author_unchanged=True,fixture_correction='Imported historical C61 audio clip ID sound -> audio_clip; validated before preview.',
   scope='Actual installed frame and 10-frame range previews inherit formal SDR display mapping; no source fallback.')
 else:
  assert not frame['ok'] and not window['ok']
  assert all(v['errors'][0]['code']!='PROJECT_INVALID' for v in (frame,window))
  result=dict(status='confirmed-preview-defect',installed=str(a.installed),source_fallback=False,calls=calls,
   frame_errors=frame['errors'],range_errors=window['errors'],author_unchanged=True,
   scope='Candidate has valid display_mapping but no preview_mapping; previews omit the declared SDR delivery map.')
 (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
