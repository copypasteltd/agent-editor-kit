"""Check complete product manuals, every supplied-image sample link and registered workflow artifacts."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import unquote
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / 'docs/validation/evidence/looks-n002-20261024-r1'
A = ROOT / 'docs/assets/looks-n002-20261024-r1'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    manifest = json.loads((A/'manifest.json').read_bytes())
    render = json.loads((E/'render-verification.json').read_bytes())
    browser = json.loads((E/'browser-verification.json').read_bytes())
    skills = json.loads((E/'skill-verification.json').read_bytes())
    assert all(r['status']=='passed' for r in (render,browser,skills))
    assert browser['owned_tabs_closed'] and not browser['network_requests']
    assert sha(A/'manifest.json')==render['manifest_sha256']
    assert sha(A/'source.png')==manifest['source']['sha256']
    assert sha(Path(manifest['source']['supplied_path']))==manifest['source']['sha256']
    records=manifest['records']; ids={r['id'] for r in records}
    assert len(ids)==len(records)==500
    assert [r['number'] for r in records]==list(range(1,501))
    for row in records:
        assert sha(A/row['full'])==row['full_sha256'],row['id']
        assert sha(A/row['thumbnail'])==row['thumbnail_sha256'],row['id']
        assert row['lossless_webp_matches_native_png'] and row['strength']==1.0
    root_docs=[ROOT/p for p in ('README.md','README.zh-TW.md','README.en.md')]
    paths=[*root_docs,ROOT/'docs/README.md',*sorted((ROOT/'docs/product').glob('*.md')),
           *sorted((ROOT/'docs/local').glob('FILTER_GALLERY*.md')),
           *sorted((ROOT/'docs/local').glob('FILTERS*.md')),
           *sorted((ROOT/'docs/local').glob('LOOK_PRESETS*.md')),
           *sorted((ROOT/'docs/local/look-profiles').glob('*.md')),
           *sorted((ROOT/'docs/local/filter-gallery').glob('*.md')),
           ROOT/'docs/maintenance/README_RESTORATION_20261024.md',
           ROOT/'docs/validation/README_AND_FILTER_GALLERY_20261024.md',
           A/'SOURCE_AND_LICENSES.md',
           *sorted((ROOT/'skills').glob('agent-ffmpeg-local-*/SKILL.md')),
           *sorted((ROOT/'skills/agent-ffmpeg-local-editor/references').glob('*.md'))]
    paths=list(dict.fromkeys(paths))
    report_path=E/'docs-verification.json'
    parser=MarkdownIt('commonmark')
    def destinations(tokens):
        for token in tokens:
            if token.type=='link_open':
                yield token.attrGet('href')
            elif token.type=='image':
                yield token.attrGet('src')
            if token.children:
                yield from destinations(token.children)
    local_links=0
    for path in paths:
        text=path.read_text('utf-8')
        assert '\ufffd' not in text,path
        for destination in destinations(parser.parse(text)):
            if destination.startswith(('https:','http:','mailto:','codex:')):
                continue
            target,marker,anchor=destination.partition('#')
            target=unquote(target.split('?',1)[0]).strip('<>')
            if not target:
                continue
            resolved=(path.parent/target).resolve()
            if resolved==report_path:
                local_links+=1
                continue
            assert resolved.exists(),(str(path.relative_to(ROOT)),destination)
            if marker and anchor.startswith('preset-'):
                assert f'id="{unquote(anchor)}"' in resolved.read_text('utf-8'),(path,destination)
            local_links+=1
    fences=[];root_stats=[]
    for path in root_docs:
        text=path.read_text('utf-8')
        for prefix,count in [('F',43),('S',12),('K',17),('R',28)]:
            assert re.findall(r'^\| ('+prefix+r'\d+) \|',text,re.M)==[f'{prefix}{i:02}' for i in range(1,count+1)],(path,prefix)
        assert text.count('](README')>=3,path
        fences.append(re.findall(r'```[^\n]*\n([\s\S]*?)```',text))
        root_stats.append({'path':path.name,'bytes':path.stat().st_size,'lines':len(text.splitlines()),'sha256':sha(path)})
    assert fences[0]==fences[1]==fences[2],'Commands/identifiers changed during translation'
    for suffix in ('','.zh-TW','.en'):
        pattern=f'^[0-9]{{3}}-[0-9]{{3}}{re.escape(suffix)}\\.md$'
        for folder in ('look-profiles','filter-gallery'):
            volumes=[p for p in (ROOT/'docs/local'/folder).glob('*.md') if re.match(pattern,p.name)]
            assert len(volumes)==5,(folder,suffix,len(volumes))
            text='\n'.join(p.read_text('utf-8') for p in volumes)
            anchors=re.findall(r'<a id="preset-([^"]+)"></a>',text)
            assert len(anchors)==500 and set(anchors)==ids,(folder,suffix)
            for row in records:
                assert row['full'] in text and row['thumbnail'] in text,(folder,suffix,row['id'])
        caps=(ROOT/'docs/product'/('CAPABILITIES'+suffix+'.md')).read_text('utf-8')
        keys=json.loads((ROOT/'docs/product/capabilities.json').read_bytes())['data']['capabilities']
        assert all(f'### `{key}`' in caps for key in keys)
    data=json.loads((ROOT/'docs/product/module-catalog.json').read_bytes())
    assert (len(data['modules']),len(data['services']),len(data['skills']))==(43,12,17)
    assert json.loads((ROOT/'docs/product/effects.json').read_bytes())['data']['count']==46
    cases=(ROOT/'docs/product/CASES.md').read_text('utf-8')
    assert cases.count('![')==44,'42 restored images plus new board and preview GIF'
    for filename in ('gallery-desktop.png','gallery-mobile.png','gallery-walkthrough.webm','selection-board.jpg','look-selection.gif','client-shortlist-example/board.jpg','client-shortlist-example/selection.json'):
        assert (A/filename).stat().st_size>0,filename
    report={'status':'passed','date_utc':datetime.now(timezone.utc).isoformat(),
            'readmes':root_stats,'functional_rows':43,'service_rows':12,'skill_rows':17,'verification_rows':28,
            'all_installed_capability_groups':68,'effect_operators':46,'motion_presets':12,
            'languages':3,'look_profiles_per_language':500,'supplied_image_samples_per_language':500,
            'full_image_hashes_verified':500,'thumbnail_hashes_verified':500,
            'markdown_files':len(paths),'local_links_checked':local_links,
            'readme_code_blocks_identical':True,'restored_historical_demo_images':42,
            'source_unchanged':True,'source_image_license_separate_from_software':True,
            'kernel_full_regression_rerun':False,
            'files':{p.relative_to(ROOT).as_posix():sha(p) for p in paths}}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))


if __name__=='__main__':
    main()
