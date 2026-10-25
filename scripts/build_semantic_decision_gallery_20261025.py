"""Publish every actual heldout/regression decision, including failures, without rerunning a model."""
from __future__ import annotations
import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--heldout',type=Path,required=True,help='actual installed verification.json')
    parser.add_argument('--regression',type=Path,required=True,help='actual installed verification.json')
    args=parser.parse_args()
    assert args.run.replace('-','').isalnum()
    project=args.project.resolve(strict=True)
    output=ROOT/'docs/assets/semantic-decision-20261025-r1'/args.run
    output.mkdir(parents=True,exist_ok=False);(output/'previews').mkdir()
    data=json.loads((project/'project.json').read_bytes());assets={a['id']:a for a in data['assets']}
    index=next(r for r in data['extensions']['local_semantic']['indexes'] if r['index_id']=='images-v1')
    manifest=json.loads((project/assets[index['asset_id']]['uri']).read_bytes())
    preview_rows={r['asset_id']:r for r in manifest['rows']}
    images={}
    for aid,row in preview_rows.items():
        source=project/row['preview_uri'];assert 'sha256:'+sha(source)==row['preview_sha256']
        target=output/'previews'/(aid+'.png');shutil.copyfile(source,target)
        images[aid]='previews/'+target.name
    records=[];sources=[]
    for label,path in [('heldout',args.heldout),('regression',args.regression)]:
        value=json.loads(path.read_bytes());assert value['installed'] and value['status']=='completed-with-quality-evidence'
        sources.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),gates=value['gates']))
        for query in value['quality']['queries']:
            good=query['top1_correct'] if query['expected_asset_ids'] else query['rejected']
            records.append(dict(**query,evaluation=label,correct=bool(good),
                actual_image=images.get(query['hits'][0]['asset_id']) if query['hits'] else None,
                expected_image=images.get(query['expected_asset_ids'][0]) if query['expected_asset_ids'] else None))
    font_path=ROOT/'product/src/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
    font=ImageFont.truetype(str(font_path),17);small=ImageFont.truetype(str(font_path),14)
    title=ImageFont.truetype(str(font_path),24)
    def wrap(draw,text,width,face):
        lines=['']
        for character in text:
            if draw.textlength(lines[-1]+character,font=face)>width:lines.append('')
            lines[-1]+=character
        return '\n'.join(lines)
    pages=[]
    for first in range(0,len(records),20):
        canvas=Image.new('RGB',(1440,1900),'#101821');draw=ImageDraw.Draw(canvas)
        draw.text((18,12),'Actual calibrated retrieval / 全部实际结果，含失败',font=title,fill='white')
        draw.text((18,48),'Frozen labels are for evaluation only; cosine is not probability; shared familiar static images.',font=small,fill='#c4deed')
        for ordinal,row in enumerate(records[first:first+20]):
            x=8+(ordinal%4)*360;y=86+(ordinal//4)*356;color='#72d6ad' if row['correct'] else '#ff827d'
            draw.rounded_rectangle((x,y,x+344,y+342),radius=8,fill='#1c2935',outline=color,width=2)
            draw.text((x+10,y+8),row['id']+' / '+('PASS' if row['correct'] else 'FAIL'),font=small,fill=color)
            draw.multiline_text((x+10,y+34),wrap(draw,row['text'],320,font),font=font,spacing=2,fill='white')
            draw.text((x+10,y+120),'ACTUAL / 实际',font=small,fill='#c4deed')
            if row['actual_image']:
                with Image.open(output/row['actual_image']) as image:
                    thumb=ImageOps.pad(image.convert('RGB'),(324,142),color='#080b0f')
                    canvas.paste(thumb,(x+10,y+145));thumb.close()
            else:
                draw.rectangle((x+10,y+145,x+334,y+287),fill='#080b0f')
                draw.text((x+25,y+194),'NO CALIBRATED MATCH',font=small,fill='#c4deed')
            accepted=','.join(h['asset_id'] for h in row['hits']) or '(none)'
            draw.text((x+10,y+294),accepted,font=small,fill='#c4deed')
            expected=','.join(row['expected_asset_ids']) or '(absent from library)'
            draw.text((x+10,y+316),'expected: '+expected,font=small,fill='#c4deed')
        draw.text((18,1874),'No human semantic acceptance, natural-action, identity, audio or universal rejection claim.',font=small,fill='#c4deed')
        path=output/('results-'+str(len(pages)+1)+'.png');canvas.save(path);canvas.close();pages.append(path)
    cards=[]
    for row in records:
        actual=('<img src="'+html.escape(row['actual_image'],quote=True)+'" alt="Actual returned preview">') if row['actual_image'] else '<div class="empty">No calibrated match / 暂无经校准候选</div>'
        expected=html.escape(', '.join(row['expected_asset_ids']) or 'absent from library')
        cards.append('<article data-group="'+html.escape(row['group'],quote=True)+'" data-result="'+('pass' if row['correct'] else 'fail')+'"><header>'+html.escape(row['id'])+' · '+('PASS' if row['correct'] else 'FAIL')+'</header><p>'+html.escape(row['text'])+'</p>'+actual+'<p>'+html.escape(row['decision'])+'</p><small>Frozen expectation: '+expected+'</small></article>')
    document='''<!doctype html><html lang="zh-Hans"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Actual semantic decisions</title><style>
body{margin:0;background:#101821;color:#eaf1f7;font:16px system-ui,sans-serif}main{max-width:1440px;margin:auto;padding:24px}h1{font-size:28px}p{line-height:1.55}nav{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}button{background:#243848;color:inherit;border:1px solid #54758d;border-radius:6px;padding:8px 14px;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}article{background:#1c2935;border:2px solid #72d6ad;border-radius:9px;padding:14px}article[data-result=fail]{border-color:#ff827d}article img,.empty{width:100%;height:180px;object-fit:contain;background:#080b0f}.empty{display:grid;place-items:center;text-align:center}header{font-weight:700}small{color:#c4deed}article[hidden]{display:none}</style><main><h1>真实语义检索与拒识 / Actual semantic decisions</h1><p>All 60 heldout-wording queries and 20 original regression queries. Frozen labels are evaluated after inference. Shared familiar static images; no independent human acceptance, action/identity/audio benchmark or universal rejection guarantee. Every failure remains visible.</p><nav><button data-filter="all">全部 / All</button><button data-filter="fail">失败 / Failures</button><button data-filter="positive">正向 / Positive</button><button data-filter="negation">否定 / Negation</button><button data-filter="absent">库外 / Absent</button></nav><div class="grid">'''+''.join(cards)+'''</div><p>Credits and licenses: <a href="../SOURCE.json">SOURCE.json</a>; Noto Sans SC is OFL-1.1. NASA images imply no endorsement or personality-rights clearance. Model weights and runtimes are not included.</p></main><script>document.querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('article').forEach(c=>{const f=b.dataset.filter;c.hidden=!(f==='all'||c.dataset.result===f||c.dataset.group===f||(f==='absent'&&['out_of_library','out_of_domain'].includes(c.dataset.group)));});}));</script></html>'''
    (output/'index.html').write_text(document,encoding='utf-8',newline='\n')
    (output/'decisions.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    notice=ROOT/'docs/assets/semantic-20261025-r1/NOTICE.txt'
    (output/'SOURCE_AND_LICENSES.md').write_text('# Sources and licenses\n\nActual copied index previews; per-input origins and hashes are in [SOURCE.json](../SOURCE.json).\n\n'+notice.read_text('utf-8')+'\nAdditional brick texture: CC0 Textures, CC0-1.0. Horse: Andreas Preuss (marauder), CC0-1.0. Font: Noto Sans SC, OFL-1.1.\n\nTechnical evaluation only; frozen labels are not human acceptance.\n',encoding='utf-8',newline='\n')
    receipt=dict(status='rendered-all-actual-decisions',queries=len(records),failures=sum(not r['correct'] for r in records),
        model_executions=0,sources=sources,generator_sha256=sha(Path(__file__)),
        files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
               for p in sorted(output.rglob('*')) if p.is_file()])
    (output/'verification.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('files','sources')},ensure_ascii=False))


if __name__=='__main__':main()
