"""Execute real source/installed/registered-Skill runs against the unchanged frozen protocol."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT/'docs/validation/evidence/semantic-decision-20261025-r1/frozen'
PROTOCOL_SHA = '74b6c3c38d15284fd9a7814083378f82170cf516161898907bbf901fe997026b'
HEAVY = Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')
LIGHT = 'C:/Python313/python.exe'


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def metrics(response, labels):
    answers = {r['query']['id']:r for r in response['data']['results']}
    rows = []
    for query in labels['queries']:
        answer = answers[query['id']]; hits = answer['hits']; expected = query['expected_asset_ids']
        rows.append(dict(**query, decision=answer['decision'], clauses=answer['clauses'],
            top1_correct=bool(hits and hits[0]['asset_id'] in expected) if expected else None,
            rejected=not bool(hits),
            hits=[{k:h[k] for k in ('asset_id','sample_seconds','score')} for h in hits]))
    result = dict(queries=rows)
    for group in sorted({r['group'] for r in rows}):
        selected = [r for r in rows if r['group'] == group]
        absent = all(not r['expected_asset_ids'] for r in selected)
        result[group] = dict(count=len(selected),
            correct=sum(r['rejected'] if absent else bool(r['top1_correct']) for r in selected),
            rate=sum(r['rejected'] if absent else bool(r['top1_correct']) for r in selected)/len(selected))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--phase', choices=('setup','index','calibrate','heldout','regression','list'), required=True)
    parser.add_argument('--device', choices=('cpu','cuda'), default='cuda')
    parser.add_argument('--installed', type=Path)
    parser.add_argument('--skill', action='store_true')
    parser.add_argument('--project', type=Path, help='existing owned test project for installed/Skill verification')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and not (args.installed and args.skill)
    protocol_path = FROZEN/'protocol.json'; assert sha(protocol_path) == PROTOCOL_SHA
    protocol = json.loads(protocol_path.read_bytes())
    for path, key in [('calibration.json','calibration_sha256'),('heldout-labels.json','heldout_sha256'),
                      ('regression-labels.json','regression_sha256')]:
        assert sha(FROZEN/path) == protocol[key]
    evidence = ROOT/'docs/validation/evidence/semantic-decision-20261025-r1'/args.run/(args.phase+'-'+args.device)
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    project = (args.project or ROOT/'workspace'/('semantic-decision-20261025-'+args.run)).resolve()
    assert project.is_relative_to(ROOT/'workspace')
    if args.skill:
        prefix = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                  'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
        site = Path(json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())['installed_directory'])/'site'
    elif args.installed:
        prefix = [LIGHT,'-I','-S','-B','-u','-X','utf8',str(args.installed.resolve(strict=True)/'run.py')]
        site = args.installed.resolve()/'site'
    else:
        prefix = [str(HEAVY),'-E','-B','-u','-X','utf8','-c',
            'import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())',
            str(ROOT/'product/src')]
        site = ROOT/'product/src'
    def freeze():
        return [dict(path=p.name,sha256=sha(p)) for p in sorted((site/'ai_ad_editor').glob('*.py'))]
    before = freeze(); calls = []
    def cli(*arguments, timeout=900):
        command = prefix + [str(a) for a in arguments]
        started = time.monotonic()
        process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=timeout,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        number = len(calls)+1
        stdout=evidence/f'{number:02}.stdout.json'; stderr=evidence/f'{number:02}.stderr.txt'
        stdout.write_bytes(process.stdout); stderr.write_bytes(process.stderr)
        value=json.loads(process.stdout.decode('utf-8-sig'))
        row=dict(argv=command, exit_code=process.returncode, elapsed_seconds=time.monotonic()-started,
            stdout_sha256=sha(stdout), stderr_sha256=sha(stderr), ok=value.get('ok'),status=value.get('status'))
        calls.append(row); save(evidence/'calls.json', calls)
        print(json.dumps(dict(call=number,command=value.get('command'),exit_code=process.returncode,
            status=value.get('status'),errors=value.get('errors')),ensure_ascii=False),flush=True)
        assert process.returncode==0 and value['ok'] and value['status']=='succeeded', value
        return value
    result=dict(status='running',phase=args.phase,device=args.device,project=str(project),site=str(site),
        registered_skill=args.skill,installed=bool(args.installed or args.skill),protocol_sha256=PROTOCOL_SHA,
        started_at_utc=datetime.now(timezone.utc).isoformat(),new_renders=0,human_review=False)
    try:
        options=['--project',project,'--index-id','images-v1']
        if args.phase=='setup':
            assert not project.exists()
            cli('version'); cli('project','init',project,'--name','Calibrated visual retrieval')
            for asset in protocol['assets']:
                assert sha(ROOT/asset['path'])==asset['sha256']
                cli('media','ingest','--project',project,'--input',ROOT/asset['path'],
                    '--asset-id',asset['asset_id'],'--license-spdx',asset['license_spdx'],
                    '--creator',asset['creator'],'--evidence',ROOT/'docs/assets/semantic-decision-20261025-r1/SOURCE.json',
                    '--source-url','local://frozen-semantic-source/'+asset['asset_id'],
                    '--verification-status','verified')
            runtime=json.loads((ROOT/'local/agent-ffmpeg/semantic-runtime.json').read_bytes())
            cli('semantic','adapter-register','--project',project,'--adapter-id','siglip2',
                '--python-executable',runtime['python_executable'],'--model-path',runtime['model_path'],
                '--evidence',runtime['evidence'],'--creator',runtime['creator'],'--license-spdx',runtime['license_spdx'],
                '--verification-status',runtime['verification_status'])
        elif args.phase=='index':
            value=cli('semantic','index',*options,'--adapter-id','siglip2','--all-visual-assets',
                '--device',args.device,'--batch-size','8')
            result['inference']=value['data']['inference']
        elif args.phase=='calibrate':
            value=cli('semantic','calibrate',*options,'--calibration-id','accept-'+args.device,
                '--kind','image','--input',FROZEN/'calibration.json','--device',args.device,
                '--false-accept-rate',protocol['false_accept_rate'],
                '--minimum-coverage',protocol['minimum_calibration_correct_positive_coverage'])
            result.update(fit=value['data']['profile']['fit'],inference=value['data']['profile']['inference'])
        elif args.phase in ('heldout','regression'):
            names=('project.json','rights-ledger.json'); immutable={n:sha(project/n) for n in names}
            value=cli('semantic','search',*options,'--queries-file',FROZEN/(args.phase+'-queries.json'),
                '--kind','image','--calibration-id','accept-'+args.device,'--device',args.device,'--limit','3')
            quality=metrics(value,json.loads((FROZEN/(args.phase+'-labels.json')).read_bytes()))
            result.update(quality=quality,inference=value['data']['inference'])
            if args.phase=='heldout':
                gates=dict(positive=quality['positive']['rate']>=protocol['gates']['heldout_positive_correct_coverage'],
                    negation=quality['negation']['rate']>=protocol['gates']['heldout_negation_correct_coverage'],
                    absent=quality['out_of_library']['rate']>=protocol['gates']['heldout_out_of_library_rejection'])
            else:
                gates=dict(positive=quality['positive']['rate']>=protocol['gates']['original_positive_correct_coverage'],
                    negation=quality['negation']['correct']==protocol['gates']['original_negation_correct'],
                    absent=quality['out_of_domain']['correct']==protocol['gates']['original_out_of_library_rejected'])
                # Retain the original whole-sentence ranking as a separate actual run.
                raw=cli('semantic','search',*options,'--queries-file',FROZEN/'regression-queries.json',
                    '--kind','image','--query-mode','raw','--device',args.device,'--limit','3')
                result['raw_regression']=metrics(raw,json.loads((FROZEN/'regression-labels.json').read_bytes()))
            result.update(gates=gates,quality_gates_passed=all(gates.values()),
                          project_and_rights_unchanged=immutable=={n:sha(project/n) for n in names})
            assert result['project_and_rights_unchanged']
            # This is intentionally not an assertion on model quality. Failures
            # are a terminal, inspectable result, not a discarded/retried run.
        else:
            cli('semantic','verify',*options)
            cli('semantic','calibration-list','--project',project)
        assert freeze()==before
        result.update(status='completed-with-quality-evidence',calls=len(calls),source_bytes_unchanged=True,
                      finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_source_files=before)
    except BaseException as exc:
        result.update(status='failed',error_type=type(exc).__name__,error=str(exc)[-5000:])
        save(evidence/'verification.json',result); raise
    save(evidence/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('quality','raw_regression','inference','frozen_source_files')},
        ensure_ascii=False),flush=True)


if __name__=='__main__': main()
