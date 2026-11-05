"""Insert into the round runner only after the frozen r1 suite terminates."""


def music(args, freeze):
    out = proof('native-music', args.run)
    candidate = load(BASE / ('candidate-' + args.candidate_run) / 'verification.json')
    stage_report = load(BASE / ('skill-entry-' + args.stage_run) / 'verification.json')
    for mode in ('source-all', 'installed-all'):
        report = load(BASE / (mode + '-' + args.tests_run) / 'verification.json')
        assert report['status'] == 'passed' and report['file_hashes'] == freeze['file_hashes']
    installed = Path(candidate['installed'])
    sys.path.insert(0, str(installed / 'site'))
    import ai_ad_editor
    from ai_ad_editor.media import ffmpeg_path
    from ai_ad_editor.runtime import configure_local_runtime
    assert Path(ai_ad_editor.__file__).resolve() == installed / 'site/ai_ad_editor/__init__.py'
    assert ai_ad_editor.VERSION == VERSION
    configure_local_runtime()
    expected = {p.name: sha(p) for p in SOURCE.glob('*.py')}
    assert candidate['application_files'] == expected
    assert expected == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    home = Path(stage_report['home'])
    skill_files = {row['path']: row['sha256'] for row in stage_report['files']}
    assert all(sha(home / name) == pin for name, pin in skill_files.items())
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
              home / 'skills/agent-ffmpeg-local-editor/scripts/run.ps1']
    interface_path = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/native-interface-r6/verification.json'
    interface = load(interface_path)
    assert interface['status'] == 'passed'
    readers = [load(path) for path in (ROOT / 'docs/validation/evidence/music-loading-20261030-r1').glob('native-reader-*/verification.json')]
    reader = next(value for value in readers if value.get('status') == 'passed'
        and value.get('actual_BF16_tensor_values_equal') is True
        and value.get('model_helper_sha256') == sha(SOURCE / 'music_generation_model.py')
        and Path(value['executable']).resolve() == Path(interface['executable']).resolve())
    notices = ROOT / 'docs/validation/evidence/acestep15-admission-20261029-r1/notices-r2/verification.json'
    assert load(notices)['status'] == 'passed'
    work = LOCAL / ('music-' + args.run)
    work.mkdir()
    project = work / 'project'
    try:
        call(out, 'version', [*prefix, 'version'], cli=True)
        call(out, 'init', [*prefix, 'project', 'init', project], cli=True)
        adapter = call(out, 'register', [*prefix, 'music', 'generator-adapter', 'register',
            '--project', project, '--adapter-id', 'ace15', '--model-path',
            ROOT / 'product/.runtime/models/acestep15-20261029', '--runtime-root', interface['runtime_root'],
            '--executable', interface['executable'], '--evidence', notices,
            '--creator', 'ACE-Step / Comfy-Org; existing native ComfyUI core',
            '--license-spdx', 'Apache-2.0 AND GPL-3.0-only', '--license-url',
            notices.parent / 'Apache-2.0.txt', '--threads', '4'], cli=True)['data']
        request = work / 'request.json'
        save(request, dict(format='agent-neural-music-v1',
            prompt='Intimate acoustic piano instrumental, gentle melodic phrases, warm upright bass, soft brushed drums, elegant quiet evening atmosphere, original chamber jazz, clean studio recording.',
            lyrics='', instrumental=True, duration_seconds=10, bpm=90, language='unknown',
            keyscale='D minor', timesignature=4, seed=20261030, steps=8, generate_audio_codes=True))
        inspected = call(out, 'inspect', [*prefix, 'music', 'inspect-generation', '--input', request], cli=True)['data']
        assert inspected['samples'] == 480000
        before = {name: sha(project / name) for name in ('project.json', 'rights-ledger.json')}
        call(out, 'dry-run', [*prefix, 'music', 'generate', '--project', project, '--adapter-id', 'ace15',
            '--input', request, '--new-asset-id', 'piano66', '--apply', '--track-id', 'track_audio_1', '--dry-run'], cli=True)
        assert all(sha(project / name) == pin for name, pin in before.items())
        result = call(out, 'generate', [*prefix, 'music', 'generate', '--project', project, '--adapter-id', 'ace15',
            '--input', request, '--new-asset-id', 'piano66', '--apply', '--track-id', 'track_audio_1',
            '--timeout-seconds', '3600'], timeout=4800, cli=True)['data']
        run, model = result['generation'], result['generation']['worker']['model']
        assert model['neural_backend'] == 'cuda' and model['dynamic_vram'] is False
        assert set(model['forwards']) == {'text', 'language_model', 'diffusion', 'vae'}
        assert all(type(value) is int and value > 0 for value in model['forwards'].values())
        assert all(model['forward_output_devices'][name] == ['cuda:0'] for name in model['forwards'])
        assert run['worker']['samples'] == 480000 and run['complete_PCM_roundtrip_verified'] is True
        assert run['cleanup']['worker_exited'] is True and run['cleanup']['owner_job_closed'] is True
        assert result['clip']['asset_id'] == 'piano66'
        audio = project / result['asset']['uri']
        assert result['asset']['sha256'] == 'sha256:' + sha(audio)
        pcm = call(out, 'independent-full-PCM', [ffmpeg_path(), '-nostdin', '-v', 'error', '-i', audio,
            '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
        independent_pcm = 'sha256:' + pcm.decode().strip().split('=', 1)[1].lower()
        assert independent_pcm == run['worker']['output_PCM_sha256']
        saved = load(project / 'project.json')
        assert any(value['id'] == 'piano66' and value['sha256'] == result['asset']['sha256'] for value in saved['assets'])
        def objects(value):
            if isinstance(value, dict):
                yield value
                for child in value.values():
                    yield from objects(child)
            elif isinstance(value, list):
                for child in value:
                    yield from objects(child)
        assert any(value.get('id') == result['clip']['id'] and value.get('asset_id') == 'piano66'
                   for value in objects(saved['sequences']))
        assert result['rights']['verification_status'] == 'unverified' and result['rights']['permitted_uses'] == ['internal']
        assert all(sha(home / name) == pin for name, pin in skill_files.items())
        assert expected == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        unchanged(freeze)
        def pin(path):
            return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))
        save(out / 'verification.json', dict(status='passed', cli_version=VERSION,
            actual_PowerShell_entry=True, actual_CUDA_music=True, source_fallback=False,
            complete_PCM_verified=True, project_placement_verified=True, owned_process_cleanup_verified=True,
            application_files=expected, skill_files=skill_files, master_audio=pin(audio), request_file=pin(request),
            independent_PCM_sha256=independent_pcm, project_manifest=pin(project / 'project.json'),
            actual_generation=run, asset=result['asset'], rights=result['rights'], clip=result['clip'],
            adapter_sha256=adapter['adapter']['sha256'], interface_sha256=sha(interface_path),
            artifacts=dict(project=str(project), wav=str(audio), request=str(request)),
            human_listening=False, natural_quality_accepted=False, generated_audio_publication_approved=False,
            formal_activation=False, full_product_goal_closed=False))
    except BaseException as exc:
        save(out / 'verification.json', dict(status='failed', cli_version=VERSION,
            error=repr(exc), actual_PowerShell_entry=True, formal_activation=False))
        raise
