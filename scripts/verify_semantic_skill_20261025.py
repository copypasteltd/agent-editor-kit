"""Exercise frozen queries through the one actual Codex-discovered installed Skill."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess,time
from verify_semantic_20261025 import ROOT,TRUTH,TRUTH_SHA,metrics,sha,save
from run_frozen_regression import frozen


def main():
    evidence=ROOT/'docs/validation/evidence/semantic-20261025-r1/skill-r1'
    evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    assert sha(TRUTH)==TRUTH_SHA
    truth=json.loads(TRUTH.read_bytes())
    project=ROOT/'workspace/semantic-20261025-installed-r1'
    entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    names=sorted(p.name for p in entry.parent.glob('agent-ffmpeg-local-*') if (p/'SKILL.md').is_file())
    assert names==['agent-ffmpeg-local-editor'],names
    manifest=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
    assert manifest['cli_version']=='0.1.5' and manifest['skill_count']==1 and manifest['module_count']==17
    for row in manifest['files']:assert sha(ROOT/row['path'])==row['sha256']
    runtime=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
    assert runtime['release']==manifest['release']=='v0.1.0-alpha.4-local.3'
    assert Path(runtime['semantic_config']).is_file()
    immutable={p:sha(project/p) for p in ('project.json','rights-ledger.json')}
    before=frozen();calls=[]
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(entry/'scripts/run.ps1')]
    def call(*arguments):
        started=time.monotonic();command=[*prefix,*map(str,arguments)]
        completed=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        ordinal=len(calls)+1
        stdout=evidence/f'{ordinal:02}.stdout.json';stderr=evidence/f'{ordinal:02}.stderr.txt'
        stdout.write_bytes(completed.stdout);stderr.write_bytes(completed.stderr)
        response=json.loads(completed.stdout.decode('utf-8-sig'))
        calls.append(dict(command=command,exit_code=completed.returncode,elapsed_seconds=round(time.monotonic()-started,6),
            stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),response_ok=response.get('ok'),response_status=response.get('status')))
        save(evidence/'calls.json',calls)
        print(json.dumps(dict(call=ordinal,command=response.get('command'),exit=completed.returncode,status=response.get('status'))),flush=True)
        assert completed.returncode==0 and response['ok'] and response['status']=='succeeded',response
        return response
    result=dict(started_at_utc=datetime.now(timezone.utc).isoformat(),release=runtime['release'],cli_version='0.1.5',
        project=str(project),registered_skills=names,internal_modules=17,source_fallback=False,
        native_windows=True,virtualization=False,truth_sha256=TRUTH_SHA,human_viewing_accepted=False,human_listening_accepted=False)
    try:
        version=call('version');assert version['data']['cli_version']=='0.1.5'
        call('doctor');caps=call('capabilities');call('schema','show');call('gpu','inspect');call('model-pack','list')
        call('semantic','index-list','--project',project)
        queries=evidence/'queries.json'
        save(queries,{'queries':[dict(id=q['id'],text=q['text']) for q in truth['queries']]})
        response=call('semantic','search','--project',project,'--index-id','natural-gpu',
            '--queries-file',queries,'--limit','10','--device','auto')
        assert response['data']['inference']['response']['device']=='cuda'
        quality=metrics(response,truth)
        gates=dict(positive_top1=quality['positive_top1']>=truth['gates']['positive_top1_minimum'],
                   positive_recall_at_3=quality['positive_mean_recall_at_3']>=truth['gates']['positive_recall_at_3_minimum'])
        save(evidence/'quality.json',quality)
        image=call('semantic','search','--project',project,'--index-id','natural-gpu',
            '--image',ROOT/truth['reference_image']['path'],'--kind','image','--device','cpu')
        assert image['data']['inference']['response']['device']=='cpu'
        gates['cpu_reference_image']=image['data']['results'][0]['hits'][0]['asset_id'] in truth['reference_image']['relevant_image_ids']
        gates['project_and_rights_unchanged']=all(sha(project/p)==v for p,v in immutable.items())
        assert all(gates.values()),gates
        assert before==frozen(),'Product or tests changed during actual Skill verification'
        result.update(status='passed-with-quality-limits',commands=len(calls),gates=gates,frozen_equal=True,
            positive_top1=quality['positive_top1'],positive_mean_recall_at_3=quality['positive_mean_recall_at_3'],
            negation_successes=quality['negation_successes'],out_of_domain_queries_with_candidates=quality['out_of_domain_queries_with_candidates'],
            gpu_inference=response['data']['inference'],cpu_reference_inference=image['data']['inference'],
            actual_demo_query_response='08.stdout.json',generator_sha256=sha(Path(__file__)),finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(evidence/'verification.json',result)
        print(json.dumps(dict(status=result['status'],commands=len(calls),gates=gates)),flush=True)
    except BaseException as exc:
        result.update(status='failed',commands=len(calls),error_type=type(exc).__name__,message=str(exc)[:10000],frozen_equal=before==frozen())
        save(evidence/'failure.json',result)
        raise


if __name__=='__main__':main()
