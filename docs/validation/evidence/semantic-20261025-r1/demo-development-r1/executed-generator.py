"""Render actual retrieved video candidates as a separate editable project.

Run with an existing native Python providing Pillow. Product CLI invocations use
the explicit native CPython below, with source and installed runs distinguished.
Retrieval points do not determine event durations: this authored demo chooses
exactly one second after each returned point and retains every selected hit.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PYTHON='C:/Python313/python.exe'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):
    assert not path.exists(),path
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    parser.add_argument('--source-project',type=Path,required=True)
    parser.add_argument('--response',type=Path,required=True)
    parser.add_argument('--installed',type=Path)
    args=parser.parse_args()
    if not args.run.replace('-','').isalnum():raise ValueError('Use a short run identifier')
    source=args.source_project.resolve(strict=True);response_path=args.response.resolve(strict=True)
    assert source.is_relative_to(ROOT/'workspace') and response_path.is_relative_to(ROOT/'docs/validation/evidence')
    work=ROOT/'workspace'/('semantic-20261025-demo-'+args.run)
    output=ROOT/'docs/assets/semantic-20261025-r1'/('demo-'+args.run)
    evidence=ROOT/'docs/validation/evidence/semantic-20261025-r1'/('demo-'+args.run)
    for path in (work,output,evidence):path.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    source_data=json.loads((source/'project.json').read_bytes())
    source_assets={a['id']:a for a in source_data['assets']}
    response=json.loads(response_path.read_bytes())
    assert response['ok'] and response['status']=='succeeded' and response['data']['kind']=='video'
    answers={r['query']['id']:r for r in response['data']['results']}
    selected=[]
    # Fixed presentation order, selecting each actual rank-one video hit.
    for ident,label in [('q03','Cat / 猫'),('q01','Coffee / 咖啡'),('q05','Astronaut / 宇航员')]:
        answer=answers[ident];hit=answer['hits'][0];asset=source_assets[hit['asset_id']]
        assert hit['kind']=='video' and hit['editable_reference']['asset_id']==asset['id']
        assert hit['source_sha256']==asset['sha256']=='sha256:'+sha(source/asset['uri'])
        assert hit['preview_sha256']=='sha256:'+sha(source/hit['preview_uri'])
        point=hit['editable_reference']['source_seek_seconds']
        assert point>=0 and point+1<=float(asset['probe']['duration_seconds'])+1e-9
        selected.append(dict(query=answer['query'],label=label,hit=hit,
            duration_seconds=1.,range_policy='authored_one_second_after_returned_point_not_inferred_event_extent'))
    save(output/'selected-hits.json',dict(response_sha256=sha(response_path),selected=selected,
        candidate_review_required=True,automatic_human_acceptance=False))
    if args.installed:
        installed=args.installed.resolve(strict=True)
        prefix=[PYTHON,'-I','-S','-B','-u','-X','utf8',str(installed/'run.py')]
    else:
        prefix=[PYTHON,'-E','-B','-u','-X','utf8','-c',
            'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())',str(ROOT/'product/src')]
    calls=[]
    def cli(*arguments):
        command=[*prefix,*map(str,arguments)]
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        number=len(calls)+1
        (evidence/f'{number:02}.stdout.json').write_bytes(result.stdout)
        (evidence/f'{number:02}.stderr.txt').write_bytes(result.stderr)
        value=json.loads(result.stdout.decode('utf-8-sig'))
        calls.append(dict(argv=command,exit_code=result.returncode,status=value.get('status'),
                          stdout_sha256=sha(evidence/f'{number:02}.stdout.json')))
        (evidence/'calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        print(json.dumps(dict(call=number,command=value.get('command'),status=value.get('status')),ensure_ascii=False),flush=True)
        assert result.returncode==0 and value['ok'] and value['status']=='succeeded',value
        return value['data']
    result=dict(status='running',development_source_only=not bool(args.installed),installed=str(args.installed) if args.installed else None,
                project=str(work/'project'),response_sha256=sha(response_path),started_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        project=work/'project';cli('project','init',project,'--name','Actual semantic candidates / editable demo')
        for asset_id in dict.fromkeys(r['hit']['asset_id'] for r in selected):
            asset=source_assets[asset_id]
            cli('media','ingest','--project',project,'--input',source/asset['uri'],'--asset-id',asset_id,
                '--creator','Original sequence; CC0 / NASA source credits in SOURCE.json',
                '--license-spdx','LicenseRef-Mixed-CC0-NASA','--evidence',ROOT/'docs/assets/semantic-20261025-r1/SOURCE.json',
                '--source-url','local://semantic-demo/'+asset_id,'--verification-status','verified')
        cli('materials','ingest','--project',project,'--id','noto-sans-sc-variable','--asset-id','asset_demo_font')
        data=json.loads((project/'project.json').read_bytes());tps=data['settings']['timebase']['ticks_per_second']
        assert tps==source_data['settings']['timebase']['ticks_per_second']
        operations=[dict(op='update_sequence',sequence_id='seq_main',patch=dict(canvas=dict(width=640,height=360))),
                    dict(op='add_track',track_id='track_labels',kind='subtitle')]
        for index,row in enumerate(selected):
            reference=row['hit']['editable_reference'];start=reference['source_in_tick']
            assert start==round(reference['source_seek_seconds']*tps)
            operations.append(dict(op='append_clip',track_id='track_video_1',asset_id=reference['asset_id'],
                source_in_tick=start,source_out_tick=start+tps,duration_tick=tps,timeline_start_tick=index*tps))
            operations.append(dict(op='append_clip',track_id='track_labels',generator=dict(type='text'),
                source_in_tick=0,source_out_tick=tps,duration_tick=tps,timeline_start_tick=index*tps,
                subtitle=dict(text=row['label']+'\nsource '+str(reference['source_seek_seconds'])+'s / 1s excerpt',
                    style=dict(font_asset_id='asset_demo_font',fontsize=22,fontcolor='#FFFFFF',max_width=600,
                               x='(w-text_w)/2',y='20',borderw=2,bordercolor='#111111',line_spacing=4))))
        changes=work/'changes.json';save(changes,dict(sequence_id='seq_main',operations=operations))
        cli('timeline','compose','--project',project,'--input',changes)
        cli('validate','--project',project)
        video=project/'renders/semantic-cut.mp4'
        cli('render','--project',project,'--output',video,'--width','640','--height','360')
        cli('quality','check','--project',project,'--input',video,'--width','640','--height','360')
        archive=output/'editable-project.aevpkg.zip'
        cli('convert','export','--project',project,'--target-format','package','--output',archive)
        restored=work/'restored';cli('convert','import','--input',archive,'--output',restored)
        cli('validate','--project',restored)
        restored_video=restored/'renders/restored.mp4'
        cli('render','--project',restored,'--output',restored_video,'--width','640','--height','360')
        commands=[]
        def ff(*arguments):
            command=list(map(str,arguments));value=subprocess.run(command,capture_output=True,timeout=120)
            commands.append(dict(argv=command,exit_code=value.returncode))
            assert value.returncode==0,value.stderr.decode('utf8','replace')[-3000:]
            return value
        fingerprints=[]
        for index,path in enumerate((video,restored_video)):
            decoded=ff('ffmpeg','-nostdin','-v','error','-i',path,'-map','0:v:0','-f','framemd5','-')
            (evidence/f'decoded-{index}.framemd5').write_bytes(decoded.stdout)
            fingerprints.append([line for line in decoded.stdout.splitlines() if not line.startswith(b'#')])
        assert fingerprints[0]==fingerprints[1]
        probe=ff('ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',video)
        (evidence/'probe.json').write_bytes(probe.stdout);probed=json.loads(probe.stdout)
        visual=next(s for s in probed['streams'] if s['codec_type']=='video')
        fps=Fraction(visual['avg_frame_rate']);frames=int(visual['nb_read_frames'])
        assert frames==3*fps and (visual['width'],visual['height'])==(640,360)
        target=output/'semantic-cut.mp4';shutil.copyfile(video,target)
        gif=output/'semantic-cut.gif'
        ff('ffmpeg','-nostdin','-v','error','-i',video,'-filter_complex',
           '[0:v]fps=8,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=sierra2_4a',
           '-an','-loop','0','-n',gif)
        from PIL import Image,ImageDraw,ImageFont,ImageOps
        font_asset=next(a for a in data['assets'] if a['id']=='asset_demo_font')
        font=ImageFont.truetype(str(project/font_asset['uri']),24)
        board=Image.new('RGB',(1440,650),'#101821');draw=ImageDraw.Draw(board)
        draw.text((24,12),'Actual model candidates → editable clips / 实际检索候选 → 可编辑片段',font=font,fill='white')
        for index,row in enumerate(selected):
            raw=Image.open(source/row['hit']['preview_uri']).convert('RGB')
            board.paste(ImageOps.pad(raw,(464,261)),(8+index*480,50));raw.close()
            draw.text((18+index*480,318),row['label']+' / source '+str(row['hit']['sample_seconds'])+'s',font=font,fill='#c4deed')
            still=output/f'output-{index+1}.png'
            ff('ffmpeg','-nostdin','-v','error','-ss',str(index+.5),'-i',video,'-frames:v','1','-n',still)
            rendered=Image.open(still).convert('RGB');board.paste(ImageOps.pad(rendered,(464,261)),(8+index*480,360));rendered.close()
        board.save(output/'candidate-to-output.png');board.close()
        (evidence/'media-commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        shutil.copyfile(ROOT/'docs/assets/semantic-20261025-r1/SOURCE.json',output/'SOURCE.json')
        shutil.copyfile(ROOT/'docs/assets/semantic-20261025-r1/NOTICE.txt',output/'NOTICE.txt')
        result.update(status='passed-with-review-limits',commands=len(calls),duration_seconds=3,frames=frames,fps=str(fps),
            dimensions=[640,360],full_video_decode=True,package_roundtrip_decoded_pixels_equal=True,
            publish_gate_executed=False,human_continuous_viewing=False,human_listening=False,
            audio_included=any(s['codec_type']=='audio' for s in probed['streams']),
            natural_moving_action_benchmark=False,automatic_event_extent_inferred=False,
            files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                   for p in sorted(output.iterdir()) if p.is_file()],generator_sha256=sha(Path(__file__)))
        save(evidence/'verification.json',result);save(output/'verification.json',result)
        print(json.dumps(dict(status=result['status'],commands=len(calls),frames=frames),ensure_ascii=False),flush=True)
    except BaseException as exc:
        result.update(status='failed',message=str(exc)[:5000],commands=len(calls),generator_sha256=sha(Path(__file__)))
        save(evidence/'failure.json',result);raise


if __name__=='__main__':main()
