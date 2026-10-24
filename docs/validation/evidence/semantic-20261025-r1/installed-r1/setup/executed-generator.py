"""Actual native CLI workflow against the pre-frozen semantic benchmark.

Each phase has fresh evidence. No labels enter the model or query requests.
Source development and isolated installed-release executions remain separate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
TRUTH=ROOT/'docs/validation/evidence/semantic-20261025-r1/benchmark-frozen/truth.json'
TRUTH_SHA='72bad6009500eddc9e34e4ff55e968c8b2ae56344cf382df110ab04c78f4023e'
HEAVY=Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')
MODEL=ROOT/'product/.runtime/models/siglip2-base-patch16-224-20261025'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def relevant(hit,query):
    if hit['kind']=='image':return hit['asset_id'] in query['relevant_image_ids']
    return hit['asset_id']=='asset_v1' and any(a<=hit['sample_seconds']<b for a,b in query['relevant_video_intervals'])


def metrics(response,truth):
    answers={r['query']['id']:r for r in response['data']['results']}
    results=[]
    for query in truth['queries']:
        hits=answers[query['id']]['hits']
        expected=set(query['relevant_image_ids'])|({'asset_v1'} if query['relevant_video_intervals'] else set())
        retrieved={h['asset_id'] for h in hits[:3] if relevant(h,query)}
        results.append(dict(id=query['id'],text=query['text'],group=query['group'],
            top1_relevant=bool(hits and relevant(hits[0],query)) if expected else None,
            recall_at_3=len(retrieved)/len(expected) if expected else None,
            expected_asset_ids=sorted(expected),top_hits=[dict(asset_id=h['asset_id'],sample_seconds=h['sample_seconds'],
                score=h['score'],relevant=relevant(h,query)) for h in hits],
            open_set_candidate_returned=bool(hits) if not expected else None))
    positive=[r for r in results if r['group']=='positive']
    return dict(queries=results,positive_queries=len(positive),
        positive_top1=sum(r['top1_relevant'] for r in positive)/len(positive),
        positive_mean_recall_at_3=sum(r['recall_at_3'] for r in positive)/len(positive),
        negation_successes=sum(bool(r['top1_relevant']) for r in results if r['group']=='negation'),
        out_of_domain_queries_with_candidates=sum(bool(r['open_set_candidate_returned']) for r in results if r['group']=='out_of_domain'),
        caveat='Small familiar static-image set; no calibrated open-set rejection, unseen-training or natural-action acceptance.')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',required=True,help='new workspace/evidence identifier')
    parser.add_argument('--phase',choices=('setup','index','queries','controls','demo'),required=True)
    parser.add_argument('--installed',type=Path)
    args=parser.parse_args()
    if not args.run.replace('-','').isalnum():raise ValueError('Use a short run identifier')
    project=ROOT/'workspace'/('semantic-20261025-'+args.run)
    evidence=ROOT/'docs/validation/evidence/semantic-20261025-r1'/args.run/args.phase
    assert not evidence.exists();evidence.mkdir(parents=True)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    assert sha(TRUTH)==TRUTH_SHA
    truth=json.loads(TRUTH.read_bytes())
    for asset in truth['assets']:assert sha(ROOT/asset['path'])==asset['sha256']
    if args.installed:
        installed=args.installed.resolve(strict=True)
        assert (installed/'receipt.json').is_file() and (installed/'site/ai_ad_editor/semantic.py').is_file()
        prefix=['C:/Python313/python.exe','-I','-S','-B','-u','-X','utf8',str(installed/'run.py')]
    else:
        prefix=['C:/Python313/python.exe','-E','-B','-u','-X','utf8','-c',
                'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())',str(ROOT/'product/src')]
    calls=[]
    from run_frozen_regression import frozen
    before=frozen()
    def cli(*arguments,expect=None,timeout=900):
        command=[*prefix,*map(str,arguments)]
        start=time.monotonic()
        p=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        ordinal=len(calls)+1
        stdout=evidence/f'{ordinal:02}.stdout.json';stderr=evidence/f'{ordinal:02}.stderr.txt'
        stdout.write_bytes(p.stdout);stderr.write_bytes(p.stderr)
        value=json.loads(p.stdout.decode('utf-8-sig'))
        row=dict(command=command,exit_code=p.returncode,elapsed_seconds=round(time.monotonic()-start,6),
                 stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),expected_error=expect,
                 response_ok=value.get('ok'),response_status=value.get('status'))
        calls.append(row);save(evidence/'calls.json',calls)
        print(json.dumps(dict(call=ordinal,command=value.get('command'),exit=p.returncode,status=value.get('status'),
                              errors=value.get('errors')),ensure_ascii=False),flush=True)
        if expect:
            assert p.returncode and not value['ok'] and value['errors'][0]['code']==expect,value
        else:assert p.returncode==0 and value['ok'] and value['status']=='succeeded',value
        return value
    result=dict(phase=args.phase,project=str(project),development_source_only=not bool(args.installed),
                installed_release_tested=bool(args.installed),truth_sha256=TRUTH_SHA,started_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        if args.phase=='setup':
            assert not project.exists()
            cli('version');cli('project','init',project,'--name','Frozen visual semantic benchmark')
            for asset in truth['assets']:
                cli('media','ingest','--project',project,'--input',ROOT/asset['path'],'--asset-id',asset['asset_id'],
                    '--license-spdx',asset['license_spdx'],'--creator',asset['creator'],'--evidence',ROOT/'docs/assets/semantic-20261025-r1/SOURCE.json',
                    '--source-url','local://semantic-demo/'+asset['asset_id'],'--verification-status','verified')
            registered=cli('semantic','adapter-register','--project',project,'--adapter-id','siglip2',
                '--python-executable',HEAVY,'--model-path',MODEL,'--evidence',MODEL/'README.md',
                '--creator','Google','--license-spdx','Apache-2.0','--verification-status','verified')
            assert registered['data']['verification']['ok'] and registered['data']['model_forward_calls']==0
            result['adapter_sha256']=registered['data']['adapter']['sha256']
        elif args.phase=='index':
            indexed=cli('semantic','index','--project',project,'--index-id','natural-gpu','--adapter-id','siglip2',
                '--all-visual-assets','--sample-interval-seconds','1','--device','cuda','--batch-size','8')
            assert indexed['data']['inference']['response']['device']=='cuda'
            verified=cli('semantic','verify','--project',project,'--index-id','natural-gpu')
            result.update(index_rows=verified['data']['rows'],source_assets=verified['data']['source_assets'],
                          inference=indexed['data']['inference'])
        elif args.phase=='queries':
            query_file=evidence/'queries.json'
            save(query_file,{'queries':[dict(id=q['id'],text=q['text']) for q in truth['queries']]})
            immutable={p:sha(project/p) for p in ('project.json','rights-ledger.json')}
            options=['--project',project,'--index-id','natural-gpu','--queries-file',query_file,'--limit','3']
            gpu=cli('semantic','search',*options,'--device','cuda')
            quality=metrics(gpu,truth)
            video=cli('semantic','search',*options,'--device','cuda','--kind','video','--all-samples')
            first={r['query']['id']:r['hits'][0] for r in video['data']['results']}
            video_correct=[dict(id=q['id'],hit=first[q['id']],passed=relevant(first[q['id']],q)) for q in truth['queries'][:6]]
            reference=ROOT/truth['reference_image']['path']
            gpu_image=cli('semantic','search','--project',project,'--index-id','natural-gpu','--image',reference,'--device','cuda','--kind','image')
            cpu=cli('semantic','search',*options,'--device','cpu')
            cpu_image=cli('semantic','search','--project',project,'--index-id','natural-gpu','--image',reference,'--device','cpu','--kind','image')
            import numpy as np
            record=next(r for r in json.loads((project/'project.json').read_bytes())['extensions']['local_semantic']['indexes'] if r['index_id']=='natural-gpu')
            assets={a['id']:a for a in json.loads((project/'project.json').read_bytes())['assets']}
            manifest=json.loads((project/assets[record['asset_id']]['uri']).read_bytes())
            vectors=np.fromfile(project/manifest['vectors']['uri'],dtype='<f4').reshape(len(manifest['rows']),768)
            positions={r['asset_id']:i for i,r in enumerate(manifest['rows']) if r['kind']=='image'}
            equal=bool(np.array_equal(vectors[positions['asset_c2']],vectors[positions['asset_i1']]))
            image_ids=[v['data']['results'][0]['hits'][0]['asset_id'] for v in (gpu_image,cpu_image)]
            cpu_quality=metrics(cpu,truth)
            quality.update(cpu=cpu_quality,video_timestamp_cases=video_correct,
                           video_timestamp_top1=sum(r['passed'] for r in video_correct)/6,
                           renamed_duplicate_vectors_equal=equal,reference_image_top1_ids=image_ids,
                           project_and_rights_unchanged=all(sha(project/p)==value for p,value in immutable.items()))
            gates=truth['gates']
            quality['gates_passed']=dict(
                gpu_positive_top1=quality['positive_top1']>=gates['positive_top1_minimum'],
                gpu_positive_recall_at_3=quality['positive_mean_recall_at_3']>=gates['positive_recall_at_3_minimum'],
                cpu_positive_top1=cpu_quality['positive_top1']>=gates['positive_top1_minimum'],
                cpu_positive_recall_at_3=cpu_quality['positive_mean_recall_at_3']>=gates['positive_recall_at_3_minimum'],
                video_timestamp=quality['video_timestamp_top1']>=gates['video_queries_first_6_timestamp_top1_minimum'],
                image_query=all(i in truth['reference_image']['relevant_image_ids'] for i in image_ids),
                renamed_duplicate=equal,project_unchanged=quality['project_and_rights_unchanged'])
            save(evidence/'quality.json',quality)
            result['quality_gates']=quality['gates_passed'];result['quality_all_gates_passed']=all(quality['gates_passed'].values())
            assert result['quality_all_gates_passed'],quality
        elif args.phase=='controls':
            immutable={p:sha(project/p) for p in ('project.json','rights-ledger.json')}
            cli('semantic','index','--project',project,'--index-id','natural-gpu','--adapter-id','siglip2',
                '--all-visual-assets',expect='SEMANTIC_INDEX_EXISTS')
            stop=project/'stop-semantic';stop.touch()
            cli('semantic','search','--project',project,'--index-id','natural-gpu','--query','cat',
                '--cancel-file',stop,expect='CANCELLED')
            cli('semantic','search','--project',project,'--index-id','natural-gpu','--query','cat '*200,
                '--device','cpu',expect='SEMANTIC_TEXT_TOKEN_BUDGET')
            cli('semantic','search','--project',project,'--index-id','natural-gpu','--query','cat',
                '--device','cuda','--device-index','31',expect='GPU_UNAVAILABLE')
            data=json.loads((project/'project.json').read_bytes());assets={a['id']:a for a in data['assets']}
            record=data['extensions']['local_semantic']['indexes'][0]
            manifest_path=project/assets[record['asset_id']]['uri'];manifest=json.loads(manifest_path.read_bytes())
            for label,path,expected in [('vectors',project/manifest['vectors']['uri'],'SEMANTIC_INDEX_INVALID'),
                                        ('source',project/assets['asset_b4']['uri'],'SEMANTIC_SOURCE_CHANGED'),
                                        ('manifest',manifest_path,'SEMANTIC_INDEX_INVALID')]:
                raw=path.read_bytes()
                try:
                    changed=bytearray(raw);changed[-1]^=1;path.write_bytes(changed)
                    cli('semantic','verify','--project',project,'--index-id','natural-gpu',expect=expected)
                finally:path.write_bytes(raw)
            cli('semantic','verify','--project',project,'--index-id','natural-gpu')
            assert all(sha(project/p)==value for p,value in immutable.items())
            result['project_and_rights_unchanged']=True
        else:
            raise NotImplementedError('Demo phase is authored after actual retrieval quality is known; it must use actual returned candidates.')
        assert before==frozen(),'Product or tests changed during phase'
        result.update(status='passed',commands=len(calls),frozen_equal=True,finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      generator_sha256=sha(Path(__file__)),human_viewing_accepted=False,human_listening_accepted=False)
        save(evidence/'verification.json',result)
        print(json.dumps(dict(status='passed',phase=args.phase,commands=len(calls)),ensure_ascii=False),flush=True)
    except BaseException as exc:
        result.update(status='failed',commands=len(calls),error_type=type(exc).__name__,message=str(exc)[:10000],
                      frozen_equal=before==frozen(),generator_sha256=sha(Path(__file__)))
        save(evidence/'failure.json',result)
        raise


if __name__=='__main__':main()
