"""Compile 500 distinct, attributable SDR creative looks from pinned data."""
from pathlib import Path
from collections import Counter
import gzip
import hashlib
import json
import re

import numpy as np
from PIL import Image

from build_look_catalog import read_table, tetra
from build_look_profile_docs import traditional

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'product/src/ai_ad_editor/look_data'
EVIDENCE = ROOT/'docs/validation/evidence/look500-sources-20261024-r1'
LABELS = {'film-bw':'黑白胶片','instant-consumer':'大众拍立得','instant-pro':'专业拍立得',
          'film-negative':'彩色负片','film-slide':'反转片','creative':'创意色彩',
          'cinema':'电影色彩','landscape':'风景色彩','infrared':'红外创意','lomography':'Lomo'}
SAMPLES = np.array([[0,0,0],[.1,.1,.1],[.25,.25,.25],[.5,.5,.5],[.75,.75,.75],[.9,.9,.9],[1,1,1],
                    [245/255,219/255,198/255],[207/255,155/255,123/255],[129/255,84/255,56/255],
                    [.8,.2,.2],[.2,.8,.2],[.2,.2,.8]],dtype=np.float64)
SAMPLE_NAMES = ['gray_0','gray_10','gray_25','gray_50','gray_75','gray_90','gray_100',
                'skin_light','skin_medium','skin_deep','red','green','blue']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def cached_table(path):
    cache=ROOT/'product/.runtime/look500-build/table-cache'
    cache.mkdir(parents=True,exist_ok=True)
    key=sha(path.read_bytes());target=cache/(key+'.npy')
    if target.exists():
        table=np.load(target,allow_pickle=False)
        return table,round(len(table)**(1/3))
    table,size=read_table(path)
    np.save(target,table,allow_pickle=False)
    return table,size


def natron_id(path):
    stem=str(Path(path).with_suffix('')).lower().replace('\\','/')
    stem=re.sub(r'_([+]+|[-]+)$',lambda m:'-curve-'+('plus' if m[1][0]=='+' else 'minus')+'-'+str(len(m[1])),stem)
    stem=stem.replace('+','-plus-')
    return 'nt-'+re.sub('[^a-z0-9]+','-',stem).strip('-')


def grid(n):
    b,g,r=np.meshgrid(*([np.linspace(0,1,n)]*3),indexing='ij')
    return np.stack([r,g,b],axis=-1).reshape(-1,3)


def descriptions(table):
    out=np.clip(tetra(table,SAMPLES),0,1)
    y=out@np.array([.2126,.7152,.0722])*255
    middle=float(y[3]-127.5)
    span=float((y[4]-y[2])/127.5)
    warm=float((out[3,0]-out[3,2])*255)
    gray=bool(np.max(np.ptp(table,axis=1))<=1/255)
    tone='提亮中灰' if middle>3 else '压暗中灰' if middle< -3 else '中灰近原值'
    bias='黑白' if gray else '中性' if abs(warm)<3 else '暖色' if warm>0 else '冷色'
    contrast='中段拉开' if span>1.06 else '中段收窄' if span<.94 else '中段跨度接近原值'
    rgb=lambda a:'#'+''.join(f'{int(v):02X}' for v in np.rint(a*255))
    swatches={k:{'input':rgb(a),'output':rgb(b),'output_rgb':[round(float(x),7) for x in b]}
              for k,a,b in zip(SAMPLE_NAMES,SAMPLES,out)}
    zh=(f'50% 灰输出 Y′ {y[3]:.1f}/255（变化 {middle:+.1f} 码值）；25%–75% 灰跨度比 {span:.3f}。'
        f'中灰红减蓝 {warm:+.1f} 码值。浅/中/深肤色色块分别输出 '
        + '、'.join(rgb(v) for v in out[7:10])+'；红/绿/蓝测试块分别输出 '
        +'、'.join(rgb(v) for v in out[10:13])+'。')
    en=(f'50% gray Y′ {y[3]:.1f}/255 ({middle:+.1f} code values); 25–75% gray span ratio {span:.3f}; '
        f'mid-gray red minus blue {warm:+.1f} code values. Light/medium/deep skin swatches: '
        +', '.join(rgb(v) for v in out[7:10])+'. Red/green/blue swatches: '+', '.join(rgb(v) for v in out[10:13])+'.')
    scene='黑白纪实、建筑与轮廓试片' if gray else ('暖色生活、餐饮与怀旧试片' if warm>3 else '冷色城市、夜景与科技试片' if warm< -3 else '产品、生活与风景对照试片')
    caution='强度低于 1 会混回原始彩色。' if gray else '逐项比较肤色与品牌色，强度过高可能改变产品颜色。'
    if np.max(np.abs(table-np.clip(table,0,1)))>0:
        caution+='此表含超出 0..1 的输出，SDR 导出会截断。'
    caution+='仅像素颜色映射，不生成颗粒、光晕、暗角、空间雾或美颜；未做自然画质验收。'
    english_bias='monochrome' if gray else 'neutral' if abs(warm)<3 else 'warm' if warm>0 else 'cool'
    return dict(summary_zh=f'{bias} · {tone} · {contrast}',summary_en=f'{english_bias}; middle gray {middle:+.1f}; span {span:.3f}',
        description_zh=zh,description_en=en,suggested_use_zh=scene,suggested_use_en='Compare on your own SDR product, portrait and landscape footage before selecting.',
        cautions_zh=caution,cautions_en='Pixel color mapping only; no grain, glow, vignette, spatial haze or beauty effects. Natural footage quality is unaccepted. Check skin/product colors and clipped output.',
        suggested_strength_range=[1.,1.] if gray else [.35,.8],
        metrics={'gray50_y_code':round(float(y[3]),5),'gray50_delta_code':round(middle,5),
                 'mid_span_ratio':round(span,6),'gray50_red_minus_blue_code':round(warm,5),
                 'all_vertices_achromatic_within_one_code':gray,'samples':swatches})


def main():
    base=json.loads((DEST/'catalog.json').read_bytes())
    # Existing LUT bytes, stable IDs and ordering are a compatibility boundary.
    records=base['records'][:100]
    if len(records)!=100 or any(not r['id'].startswith(('sp-','t3-')) for r in records):
        raise ValueError('The released 100-look baseline is required')
    acquisition=json.loads((EVIDENCE/'acquisition.json').read_bytes())
    ref=np.asarray(Image.open(DEST/'previews/reference.png').convert('RGB'))/255.
    common=grid(17); random=np.random.default_rng(500).uniform(0,1,(8192,3))
    signatures=set();previews=set();audit=[]
    notes=json.loads((ROOT/'docs/local/LOOK_PRESET_NOTES.json').read_bytes())
    notes={r[0]:r for r in notes['records']}
    for i,row in enumerate(records,1):
        if 'legacy_provenance_sha256' not in row:
            old_provenance={'look':dict(row),'catalog_version':'1.0.0',
                'license_notice':f'assets/look-evidence/{row["id"]}/LICENSE.txt',
                'conversion':'Creative LUT. See source commit, SHA-256, grid size and normalization measurements above.'}
            row['legacy_provenance_sha256']=sha((json.dumps(old_provenance,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
        raw=gzip.decompress((DEST/row['lut']).read_bytes())
        scratch=ROOT/'product/.runtime/look500-build/base.cube'
        scratch.parent.mkdir(parents=True,exist_ok=True);scratch.write_bytes(raw)
        table,_=cached_table(scratch)
        signatures.add(sha(np.round(tetra(table,common),5).astype('<f4').tobytes()))
        previews.add(row['preview_sha256'])
        row.update(number=i,**descriptions(table))
        row['suggested_use_zh']=notes[row['id']][2]
        row['editorial_notes_zh']=notes[row['id']][1]
        row['name_zh_tw']=traditional(row['name_zh'])
        row['license']['obligations']=['Retain MIT copyright and license notice.']
    for spdx in ('CC-BY-SA-4.0','CC0-1.0'):
        extra=('NatronGitHub/clut; Pat David and Marc Roovers. Hald-to-CUBE conversion and thumbnails by agent editor kit contributors. '
               'Adapted LUT data and corresponding thumbnails are distributed under CC-BY-SA-4.0; app code remains MIT.\n'
               if spdx.startswith('CC-BY') else 'FreshLUTs uploaders, via pinned cyberhirsch/LUTr mirror. CC0 according to FreshLUTs terms; individual authors retained in catalog.\n')
        notice=extra+(EVIDENCE/(spdx+'.txt')).read_text('utf-8')
        if spdx.startswith('CC-BY'):
            notice+='\nOriginal source notice:\n'+(EVIDENCE/'Natron-README.md').read_text('utf-8')
        (DEST/'licenses'/(spdx+'.txt')).write_text(notice,encoding='utf-8',newline='\n')
    for source in acquisition['candidates']:
        if len(records)==500:
            break
        path=ROOT/source['local_path'];raw_source=path.read_bytes()
        if sha(raw_source)!=source['sha256']:
            raise ValueError('Acquired source changed')
        if source['repository'].startswith('Natron'):
            category={'bw':'film-bw','instant_consumer':'instant-consumer','instant_pro':'instant-pro',
                'negative_color':'film-negative','negative_new':'film-negative','negative_old':'film-negative',
                'colorslide':'film-slide','picturefx':'creative'}[source['path'].split('/')[0]]
            title=source['title'].title()
            look_id=natron_id(source['path'])
            table,size=cached_table(path)
            normalized=tetra(table,grid(33));out_size=33
            method='native-depth-Hald-to-33-tetrahedral-v1'
        else:
            title=source['title'].strip(' \"')
            look_id=source['upstream_id'].replace('freshluts--','fl-')
            cube=ROOT/'product/.runtime/look500-build/upstream.cube'
            decoded=gzip.decompress(raw_source)
            # Reject contradictory restrictive headers even if site terms say CC0.
            header='\n'.join(x for x in decoded.decode('utf-8-sig').splitlines() if x.startswith('#'))
            if re.search(r'all rights reserved|non.?commercial|personal use only|do not redistribute',header,re.I):
                audit.append({'source':source['path'],'excluded':'conflicting-header'});continue
            cube.write_bytes(decoded);table,size=cached_table(cube)
            normalized=table;out_size=size;method='native-CUBE-grid-retained-v1'
            category='creative'
            if 'cinematic' in source.get('tags',[]):category='cinema'
            if 'landscape' in source.get('tags',[]):category='landscape'
        signature=sha(np.round(tetra(normalized,common),5).astype('<f4').tobytes())
        if signature in signatures:
            audit.append({'source':source['path'],'excluded':'same-17-grid-transform-at-5-decimals'});continue
        output=tetra(normalized,ref.reshape(-1,3))
        image=Image.fromarray(np.rint(np.clip(output,0,1)*255).astype('uint8').reshape(ref.shape))
        image.thumbnail((240,150))
        preview_rel=f'previews/{look_id}.webp';image.save(DEST/preview_rel,lossless=True,method=4)
        preview_hash=sha((DEST/preview_rel).read_bytes())
        if preview_hash in previews:
            (DEST/preview_rel).unlink();audit.append({'source':source['path'],'excluded':'same-reference-preview'});continue
        payload=(f'TITLE "AEK {look_id}"\nLUT_3D_SIZE {out_size}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n'
                 +''.join('%.7f %.7f %.7f\n'%tuple(x) for x in normalized)).encode('ascii')
        packed=gzip.compress(payload,compresslevel=9,mtime=0)
        lut_rel=f'luts/{look_id}.cube.gz';(DEST/lut_rel).write_bytes(packed)
        error=np.abs(tetra(table,random)-tetra(normalized,random))
        detail=descriptions(normalized)
        spdx=source['license'];notice_rel='licenses/'+spdx+'.txt'
        obligations=(['Credit the named creator and source; retain the CC-BY-SA-4.0 notice and indicate changes.',
                      'Redistributed adapted LUT data and thumbnails must use CC-BY-SA-4.0 or a compatible license; no additional restrictions.']
                     if spdx.startswith('CC-BY') else ['CC0: no attribution condition; source and creator retained for provenance.'])
        row=dict(id=look_id,number=len(records)+1,name=title,
            name_zh=f'{"黑白负片" if category=="film-negative" and detail["metrics"]["all_vertices_achromatic_within_one_code"] else LABELS[category]} · {title}｜{detail["summary_zh"]}',category=category,
            tags=[LABELS[category],source['repository'],spdx,'SDR',detail['summary_zh']]+source.get('tags',[]),
            recommended_strength=1.,grid_size=out_size,lut=lut_rel,bytes=len(payload),sha256=sha(payload),
            packed_sha256=sha(packed),transform_sha256=sha(normalized.astype('<f4').tobytes()),
            preview=preview_rel,preview_sha256=preview_hash,
            source={k:source[k] for k in ('repository','commit','path','sha256','git_blob','source_url','input_basis')},
            license=dict(spdx=spdx,file=notice_rel,sha256=sha((DEST/notice_rel).read_bytes()),creator=source['creator'],
                url='https://creativecommons.org/licenses/by-sa/4.0/' if spdx.startswith('CC-BY') else 'https://freshluts.com/termsandconditions',
                obligations=obligations),
            normalization=dict(method=method,source_bit_depth=path.read_bytes()[24] if path.suffix=='.png' else None,
                source_grid_size=size,sample_count=len(random),sampled_max_abs_rgb_error=float(error.max()),
                sampled_mean_abs_rgb_error=float(error.mean())),**detail)
        row['name_zh_tw']=traditional(row['name_zh'])
        records.append(row);signatures.add(signature);previews.add(preview_hash)
        if len(records)%20==0:print(json.dumps({'compiled':len(records),'target':500}),flush=True)
    if len(records)!=500 or len({r['id'] for r in records})!=500 or len(previews)!=500:
        raise ValueError(f'Not enough unique verified transforms: {len(records)}')
    value=dict(base,version='2.0.0',count=500,records=records)
    value['license_counts']=dict(Counter(r['license']['spdx'] for r in records))
    value['naming']='001–100 retain released IDs and LUT bytes. 101–500 use source-qualified IDs; localized names include measured mid-gray and span descriptions. Strength variants do not count as separate looks.'
    (DEST/'catalog.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    wanted={r['lut'] for r in records}|{r['preview'] for r in records}
    for sub in ('luts','previews'):
        for path in (DEST/sub).iterdir():
            if (path.is_file() and path.name.startswith(('nt-','fl-'))
                    and path.relative_to(DEST).as_posix() not in wanted):
                if not path.resolve().is_relative_to(DEST.resolve()):raise ValueError('Cleanup outside owned look data')
                path.unlink()
    report=dict(status='passed',count=500,license_counts=value['license_counts'],
        unique_transform_signatures=len(signatures),signature_method='17x17x17 tetrahedral samples rounded to 5 decimals, float32 little endian',
        unique_preview_hashes=len(previews),exclusions=audit,existing_100_lut_bytes_preserved=True,
        packed_lut_bytes=sum((DEST/r['lut']).stat().st_size for r in records),
        catalog_sha256=sha((DEST/'catalog.json').read_bytes()))
    (EVIDENCE/'compilation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
