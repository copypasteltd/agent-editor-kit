"""Verify normal model/index/profile/package behavior under managed semantic jobs."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

from run_semantic_decisions_20261025 import metrics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/semantic-control-20261025-r1'
FROZEN = ROOT/'docs/validation/evidence/semantic-decision-20261025-r1/frozen'
PROTOCOL_SHA = '74b6c3c38d15284fd9a7814083378f82170cf516161898907bbf901fe997026b'
LIGHT = 'C:/Python313/python.exe'


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def inventory(root, project):
    return dict(metadata={n:sha(root/n) for n in ('project.json','rights-ledger.json')},
        assets={a['id']:dict(uri=a['uri'], sha256=sha(root/a['uri'])) for a in project['assets']})


def semantic_payloads(root, project):
    assets = {a['id']:a for a in project['assets']}
    def read(ident): return json.loads((root/assets[ident]['uri']).read_bytes())
    reg = project['extensions']['local_semantic']
    return dict(indexes={r['index_id']:read(r['asset_id']) for r in reg['indexes']},
        profiles={r['calibration_id']:read(r['asset_id']) for r in reg['calibrations']})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--phase', choices=('setup','index','calibrate','before','roundtrip','after','skill','legacy'), required=True)
    parser.add_argument('--device', choices=('cuda','cpu'), default='cuda')
    args = parser.parse_args(); assert args.run.replace('-','').isalnum()
    installed = args.installed.resolve(strict=True)
    work = (ROOT/'workspace'/('semantic-control-20261025-'+args.run)).resolve()
    assert work.is_relative_to((ROOT/'workspace').resolve())
    source, external, restored, second = (work/n for n in ('source','external','restored','second'))
    phase = args.phase+'-'+args.device
    evidence = BASE/args.run/phase; evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    assert sha(FROZEN/'protocol.json') == PROTOCOL_SHA
    protocol = json.loads((FROZEN/'protocol.json').read_bytes())
    for name, key in [('calibration.json','calibration_sha256'),('heldout-labels.json','heldout_sha256'),
                      ('regression-labels.json','regression_sha256')]:
        assert sha(FROZEN/name) == protocol[key]
    prefix = [LIGHT,'-I','-S','-B','-u','-X','utf8',str(installed/'run.py')]
    if args.phase == 'skill':
        config = json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
        assert Path(config['installed_directory']).resolve() == installed
        prefix = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
            'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
    code_before = {p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
    calls = []
    def cli(*arguments, expected_success=True):
        argv = [*prefix,*map(str,arguments)]; started = time.monotonic()
        process = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=1200,
            creationflags=subprocess.CREATE_NO_WINDOW)
        number = len(calls)+1; stdout=evidence/f'{number:02}.stdout.json'; stderr=evidence/f'{number:02}.stderr.txt'
        stdout.write_bytes(process.stdout); stderr.write_bytes(process.stderr)
        value = json.loads(process.stdout.decode('utf-8-sig'))
        calls.append(dict(argv=argv, exit_code=process.returncode, elapsed_seconds=time.monotonic()-started,
            stdout_sha256=sha(stdout), stderr_sha256=sha(stderr), status=value.get('status'), ok=value.get('ok')))
        save(evidence/'calls.json', calls)
        print(json.dumps(dict(call=number, command=value.get('command'), exit_code=process.returncode,
            status=value.get('status')), ensure_ascii=False), flush=True)
        assert bool(process.returncode == 0 and value['ok']) == expected_success, value
        return value
    result = dict(status='running', phase=args.phase, device=args.device, run=args.run,
        started_at_utc=datetime.now(timezone.utc).isoformat(), installed=str(installed),
        protocol_sha256=PROTOCOL_SHA, native_windows=True, virtualization=False,
        registered_skill=args.phase == 'skill', human_review=False, new_renders=0)
    try:
        options = ['--index-id','images-v1','--kind','image','--calibration-id','accept-'+args.device,
            '--device',args.device,'--limit','3']
        if args.phase == 'setup':
            work.mkdir(parents=True, exist_ok=False); external.mkdir()
            cli('version'); cli('project','init',source,'--name','Portable calibrated retrieval')
            for asset in protocol['assets']:
                assert sha(ROOT/asset['path']) == asset['sha256']
                cli('media','ingest','--project',source,'--input',ROOT/asset['path'],'--asset-id',asset['asset_id'],
                    '--license-spdx',asset['license_spdx'],'--creator',asset['creator'],
                    '--evidence',ROOT/'docs/assets/semantic-decision-20261025-r1/SOURCE.json',
                    '--source-url','local://frozen-semantic-source/'+asset['asset_id'],
                    '--verification-status','verified')
            # Author one explicitly allowed external source BEFORE any index or
            # profile exists. No adapter pin, index, vector or cutoff is edited.
            project = json.loads((source/'project.json').read_bytes())
            first = protocol['assets'][0]; asset = next(a for a in project['assets'] if a['id'] == first['asset_id'])
            path = external/'explicit-external-source.png'; shutil.copyfile(ROOT/first['path'], path)
            original_uri = asset['uri']; asset['uri'] = str(path)
            asset.setdefault('extensions', {})['external_authorized'] = True
            project.setdefault('provenance', {}).setdefault('change_log', []).append(dict(
                command='fixture.author-external-source-before-index', asset_id=asset['id'],
                before=original_uri, after=str(path), explicit_external_authorized=True))
            save(source/'project.json', project)
            save(evidence/'external-source-authorship.json', dict(asset_id=asset['id'], sha256=sha(path),
                before=original_uri, after=str(path), semantic_index_or_calibration_existed=False))
            cli('validate','--project',source)
            runtime = json.loads((ROOT/'local/agent-ffmpeg/semantic-runtime.json').read_bytes())
            cli('semantic','adapter-register','--project',source,'--adapter-id','siglip2',
                '--python-executable',runtime['python_executable'],'--model-path',runtime['model_path'],
                '--evidence',runtime['evidence'],'--creator',runtime['creator'],
                '--license-spdx',runtime['license_spdx'],'--verification-status',runtime['verification_status'])
            query_rows=[]; labels=[]
            for name in ('heldout','regression'):
                query_rows += json.loads((FROZEN/(name+'-queries.json')).read_bytes())['queries']
                labels += json.loads((FROZEN/(name+'-labels.json')).read_bytes())['queries']
            assert len(query_rows) == len({r['id'] for r in query_rows}) == 80
            save(work/'queries.json', dict(queries=query_rows)); save(work/'labels.json', dict(queries=labels))
            result.update(new_model_forwards=0, external_source_authored_before_index=True)
        elif args.phase == 'index':
            response=cli('semantic','index','--project',source,'--index-id','images-v1','--adapter-id','siglip2',
                '--all-visual-assets','--device',args.device,'--batch-size','8')
            result['inference'] = response['data']['inference']
        elif args.phase == 'calibrate':
            response=cli('semantic','calibrate','--project',source,'--index-id','images-v1',
                '--calibration-id','accept-'+args.device,'--kind','image','--input',FROZEN/'calibration.json',
                '--device',args.device,'--false-accept-rate',protocol['false_accept_rate'],
                '--minimum-coverage',protocol['minimum_calibration_correct_positive_coverage'])
            result.update(fit=response['data']['profile']['fit'], inference=response['data']['profile']['inference'])
        elif args.phase == 'roundtrip':
            project = json.loads((source/'project.json').read_bytes()); before=inventory(source, project)
            old_payloads=semantic_payloads(source, project); archive=work/'retrieval.aevpkg.zip'
            exported=cli('convert','export','--project',source,'--target-format','package','--output',archive)
            cli('convert','import','--input',archive,'--output',restored); cli('validate','--project',restored)
            imported=json.loads((restored/'project.json').read_bytes()); new_payloads=semantic_payloads(restored, imported)
            for ident, old in old_payloads['indexes'].items():
                new=new_payloads['indexes'][ident]
                for field in ('adapter_sha256','vectors','sampling','preprocessing'):
                    if field in old: assert old[field] == new[field], field
                assert old['fingerprint'] != new['fingerprint']
                assert [r['sample_seconds'] for r in old['rows']] == [r['sample_seconds'] for r in new['rows']]
            for ident, old in old_payloads['profiles'].items():
                new=new_payloads['profiles'][ident]
                for field in ('adapter_sha256','dataset_sha256','fit','observations','device','device_index','inference'):
                    assert old[field] == new[field], field
            assert project['extensions']['local_semantic']['adapters'] == imported['extensions']['local_semantic']['adapters']
            assert inventory(source, project) == before
            # A second package must no longer derive metadata: all paths are now
            # relative, so each registered semantic asset is byte-identical.
            second_archive=work/'second.aevpkg.zip'
            cli('convert','export','--project',restored,'--target-format','package','--output',second_archive)
            cli('convert','import','--input',second_archive,'--output',second); cli('validate','--project',second)
            repeated=json.loads((second/'project.json').read_bytes())
            assert repeated['extensions']['local_semantic'] == imported['extensions']['local_semantic']
            for asset in imported['assets']:
                assert sha(restored/asset['uri']) == sha(second/asset['uri'])
            for old, new in ((source,work/'source-offline'),(external,work/'external-offline')):
                assert old.resolve().is_relative_to(work) and new.resolve().is_relative_to(work) and not new.exists()
                old.rename(new)
            assert not source.exists() and not external.exists()
            save(evidence/'source-before.json', before); save(evidence/'old-semantic-payloads.json',old_payloads)
            save(evidence/'new-semantic-payloads.json',new_payloads)
            result.update(new_model_forwards=0, source_and_external_renamed_out_of_original_paths=True,
                source_metadata_and_asset_bytes_unchanged=True, adapter_pins_unchanged=True,
                vectors_samples_fit_observations_datasets_device_unchanged=True,
                second_roundtrip_semantic_assets_byte_identical=True,
                package_sha256=sha(archive), second_package_sha256=sha(second_archive),
                conversion_semantic_data=exported['data']['report_data']['semantic_data'])
        elif args.phase in ('before','after','skill'):
            project_root = source if args.phase == 'before' else second if args.phase == 'skill' else restored
            project=json.loads((project_root/'project.json').read_bytes()); before=inventory(project_root,project)
            response=cli('semantic','search','--project',project_root,'--queries-file',work/'queries.json',*options)
            quality=metrics(response, json.loads((work/'labels.json').read_bytes()))
            result.update(quality=quality, inference=response['data']['inference'], query_count=80)
            save(evidence/'actual-decisions.json', response)
            if args.phase != 'before':
                prior=json.loads((BASE/args.run/('before-'+args.device)/'actual-decisions.json').read_bytes())
                comparisons=[]
                for old,new in zip(prior['data']['results'],response['data']['results'], strict=True):
                    assert old['query'] == new['query'] and old['decision'] == new['decision']
                    assert [h['asset_id'] for h in old['hits']] == [h['asset_id'] for h in new['hits']]
                    errors=[abs(a['score']-b['score']) for a,b in zip(old['hits'],new['hits'],strict=True)]
                    assert all(e <= 1e-6 for e in errors)
                    comparisons.append(dict(id=new['query']['id'],decision_identical=True,
                        ordered_asset_ids_identical=True, maximum_score_error=max(errors,default=0)))
                save(evidence/'before-after-comparison.json', comparisons)
                result.update(all_80_decisions_and_ordered_hits_identical=True,
                    maximum_score_error=max(r['maximum_score_error'] for r in comparisons),
                    original_source_and_external_paths_unavailable=not source.exists() and not external.exists())
                assert result['original_source_and_external_paths_unavailable']
            assert inventory(project_root,project) == before
            result['project_rights_and_assets_unchanged'] = True
        else:
            legacy=ROOT/'docs/assets/semantic-decision-20261025-r1/demo-installed-r1/retrieval-project.aevpkg.zip'
            before=sha(legacy); destination=work/'legacy-rejected'
            response=cli('convert','import','--input',legacy,'--output',destination,expected_success=False)
            assert not destination.exists() and not list(work.glob('.aek-package-*')) and sha(legacy) == before
            result.update(new_model_forwards=0, legacy_0_1_10_package_rejected_before_publication=True,
                legacy_bytes_unchanged=True, error=response.get('errors'))
        assert code_before == {p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
        result.update(status='completed-with-explicit-quality-limits', calls=len(calls), source_bytes_unchanged=True,
            frozen_product_files=code_before, finished_at_utc=datetime.now(timezone.utc).isoformat())
    except BaseException as exc:
        result.update(status='failed', error=repr(exc)); save(evidence/'verification.json',result); raise
    save(evidence/'verification.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('quality','inference','frozen_product_files')},
        ensure_ascii=False), flush=True)


if __name__ == '__main__': main()
