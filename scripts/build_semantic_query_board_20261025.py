"""Show every frozen GPU query, including negation/OOD failures, as actual previews."""
from pathlib import Path
import hashlib,json
from PIL import Image,ImageDraw,ImageFont,ImageOps

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base=ROOT/'docs/validation/evidence/semantic-20261025-r1/development-r1/queries'
    response=json.loads((base/'01.stdout.json').read_bytes())
    quality=json.loads((base/'quality.json').read_bytes())
    results={r['query']['id']:r for r in response['data']['results']}
    project=ROOT/'workspace/semantic-20261025-development-r1'
    demo=ROOT/'workspace/semantic-20261025-demo-development-r1/project'
    font_asset=next(a for a in json.loads((demo/'project.json').read_bytes())['assets'] if a['id']=='asset_demo_font')
    font_path=demo/font_asset['uri'];font=ImageFont.truetype(str(font_path),20)
    small=ImageFont.truetype(str(font_path),17);title=ImageFont.truetype(str(font_path),26)
    output=ROOT/'docs/assets/semantic-20261025-r1';image=output/'all-query-results.png'
    receipt=output/'query-board.json';assert not image.exists() and not receipt.exists()
    canvas=Image.new('RGB',(1440,1740),'#101821');draw=ImageDraw.Draw(canvas)
    draw.text((18,12),'Actual GPU retrieval / 全部 20 条查询：保留失败与库外候选',font=title,fill='white')
    draw.text((18,50),'Cosine is not probability. Fixed truth is used only for scoring after inference.',font=small,fill='#c4deed')
    rows=[]
    for position,scored in enumerate(quality['queries']):
        answer=results[scored['id']];hit=answer['hits'][0]
        unknown=scored['group']=='out_of_domain'
        passed=scored['top1_relevant'] is True
        status='NO MATCH → CANDIDATE' if unknown else 'PASS' if passed else 'FAIL'
        color='#e4b65e' if unknown else '#72d6ad' if passed else '#ff827d'
        x=(position%4)*360+8;y=(position//4)*324+90
        draw.rounded_rectangle((x,y,x+344,y+312),radius=8,fill='#1c2935',outline=color,width=2)
        draw.text((x+10,y+8),scored['id']+'  '+status,font=small,fill=color)
        text=answer['query']['text'];lines=['']
        for character in text:
            if draw.textlength(lines[-1]+character,font=font)>320:lines.append('')
            lines[-1]+=character
        assert len(lines)<=3
        draw.multiline_text((x+10,y+36),'\n'.join(lines),font=font,spacing=2,fill='white')
        preview=project/hit['preview_uri'];assert 'sha256:'+sha(preview)==hit['preview_sha256']
        with Image.open(preview) as original:
            thumb=ImageOps.pad(original.convert('RGB'),(324,170),color='#080b0f')
            canvas.paste(thumb,(x+10,y+106));thumb.close()
        label=hit['asset_id']+' @'+str(hit['sample_seconds'])+'s / '+format(hit['score'],'.5f')
        draw.text((x+10,y+282),label,font=small,fill='#c4deed')
        rows.append(dict(query_id=scored['id'],group=scored['group'],status=status,asset_id=hit['asset_id'],
                         time=hit['sample_seconds'],score=hit['score'],preview_sha256=hit['preview_sha256']))
    draw.text((18,1714),'Static public images / still-image montage; no natural-action, identity or broad advertising acceptance.',font=small,fill='#c4deed')
    canvas.save(image);canvas.close()
    data=dict(status='rendered_actual_results',files=[dict(path=image.relative_to(ROOT).as_posix(),sha256=sha(image))],
        gpu_response_sha256=sha(base/'01.stdout.json'),quality_sha256=sha(base/'quality.json'),rows=rows,
        all_twenty_queries_included=True,failed_negation_retained=True,ood_candidates_retained=True,
        human_acceptance=False,font='Noto Sans SC / OFL-1.1',generator_sha256=sha(Path(__file__)))
    receipt.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status=data['status'],queries=len(rows),output=str(image)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
