"""Pinned, offline ACE-Step 1.5 music adapters and explicit generation requests."""
import math
from pathlib import Path

from .artifact_locks import artifact_entry
from .errors import AppError, argument_error
from .local_vace import _tensor_keys as tensor_file
from .lipsync_plan import digest
from .policy import resolve_local_path
from .utils import assert_id, now_iso

ENGINE = 'acestep15-native-cuda-v1'
PROTOCOL = 'agent-native-music-generation-v1'
FORMAT = 'agent-neural-music-v1'
RATE = 48000
MODEL_SHA256 = {
    'diffusion_model.safetensors': '3f6e0797fad420a39bd33979eb6e840e30989e34a3794e843d23b60ec6e422d7',
    'text_encoder.safetensors': 'fd4590c82153b8ddb67e15a2e7aaa8afa8b83a858c8a9b82a4831063156aa7a7',
    'language_model.safetensors': 'ed63e9247d1f55f3ace04fa11e95b085fc82d459c82c5626f0b2e37b91ebd710',
    'vae.safetensors': '6de92e3a862acd287e08b024ac90f0783a8635451b728721a33ff03565bcb2bb',
}
LANGUAGES = set('ar az bg bn ca cs da de el en es fa fi fr he hi hr ht hu id is it ja ko la lt ms ne nl no pa pl pt ro ru sa sk sr sv sw ta te th tl tr uk ur vi yue zh unknown'.split())
KEYS = {root + ' ' + quality for root in 'C C# Db D D# Eb E F F# Gb G G# Ab A A# Bb B'.split() for quality in ('major', 'minor')}
IMPLEMENTATIONS = tuple(name + '.py' for name in (
    'local_music_generation', 'music_generation_model', 'music_generation_worker',
    'music_generation_pipeline', 'music_generation_cli', 'native_process_job',
    'job_workspaces', 'artifact_locks', 'cuda_admission', 'rvm_worker', 'utils', 'local_vace'))


def error(suffix, message, **details):
    return AppError('MUSIC_GENERATION_' + suffix, message, exit_code=6, diagnostics=details or None)


def finite(value, name, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise argument_error(f'{name}须为有限{low}..{high}')
    return float(value)


def prepare_request(value):
    allowed = {'format', 'prompt', 'lyrics', 'instrumental', 'duration_seconds', 'bpm',
               'language', 'keyscale', 'timesignature', 'seed', 'steps', 'generate_audio_codes'}
    if not isinstance(value, dict) or set(value) - allowed or value.get('format') != FORMAT:
        raise argument_error('要求agent-neural-music-v1请求；未知字段拒绝')
    prompt = value.get('prompt')
    lyrics = value.get('lyrics', '')
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 4000 or '\x00' in prompt:
        raise argument_error('prompt须为1..4000字符，不含NUL')
    if not isinstance(lyrics, str) or len(lyrics) > 12000 or '\x00' in lyrics:
        raise argument_error('lyrics须为至多12000字符，不含NUL')
    instrumental = value.get('instrumental')
    if type(instrumental) is not bool or (instrumental and lyrics.strip()) or (not instrumental and not lyrics.strip()):
        raise argument_error('须明确instrumental；纯音乐歌词为空，演唱须提供歌词')
    duration = finite(value.get('duration_seconds'), 'duration_seconds', 10, 600)
    # ACE 1.5 has 25 latent frames/s. Preserve its native output, without
    # padding, looping, or silently changing the declared generation duration.
    latent_frames = round(duration * 25)
    if abs(duration * 25 - latent_frames) > 1e-7:
        raise argument_error('duration_seconds须为0.04秒整数倍，以保留原生生成采样时钟')
    bpm = value.get('bpm', 120)
    seed = value.get('seed', 0)
    steps = value.get('steps', 8)
    if type(bpm) is not int or not 10 <= bpm <= 300 or type(seed) is not int or not 0 <= seed < 2**63:
        raise argument_error('bpm须为10..300整数，seed须为0..2^63-1整数')
    if type(steps) is not int or not 1 <= steps <= 32:
        raise argument_error('steps须为1..32整数；Turbo默认8步')
    language = value.get('language', 'unknown' if instrumental else None)
    keyscale = value.get('keyscale', 'C major')
    signature = value.get('timesignature', 4)
    codes = value.get('generate_audio_codes', True)
    if not isinstance(language, str) or language not in LANGUAGES or not isinstance(keyscale, str) or keyscale not in KEYS or type(signature) is not int or signature not in (2, 3, 4, 6) or type(codes) is not bool:
        raise argument_error('语言、调性、拍号或generate_audio_codes无效')
    return dict(format=FORMAT, prompt=prompt, lyrics=lyrics, instrumental=instrumental,
                duration_seconds=latent_frames / 25, bpm=bpm, language=language,
                keyscale=keyscale, timesignature=signature, seed=seed, steps=steps,
                generate_audio_codes=codes)


def settings(*, threads=4):
    if type(threads) is not int or not 1 <= threads <= 32:
        raise argument_error('threads须为1..32整数')
    return dict(threads=threads, device='cuda:0', precision='bfloat16', sample_rate=RATE,
                channels=2, sampler='euler', scheduler='simple', cfg=1.0, shift=3.0, flow_multiplier=1.0,
                cpu_weight_offload=True, cpu_neural_inference=False)


def _ordinary(path):
    if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
        raise error('FILES', '模型与运行时代码不能使用联接或符号链接', path=str(path))
    return path


def model_files(folder):
    folder = _ordinary(Path(folder))
    if not folder.is_dir():
        raise error('MODEL', '找不到完整ACE-Step1.5模型目录')
    result = []
    for name in sorted(MODEL_SHA256):
        path = _ordinary(folder / name)
        if not path.is_file():
            raise error('MODEL', '缺少固定ACE-Step1.5组件', file=name)
        try:
            tensor_file(path)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise error('MODEL', '神经音乐组件须为完整无重叠的BF16/F16/F32 safetensors',
                        file=name, cause=str(exc)) from exc
        result.append(path)
    return result


def runtime_files(folder):
    """Bounded source/resource inventory; never traverse shared model folders."""
    folder = _ordinary(Path(folder))
    required = ('comfy/sd.py', 'comfy/sample.py', 'comfy/text_encoders/ace15.py',
                'comfy_extras/nodes_ace.py', 'comfy_extras/nodes_audio.py', 'folder_paths.py', 'LICENSE')
    if any(not (folder / name).is_file() for name in required):
        raise error('RUNTIME', '要求已有原生ComfyUI ACE1.5核心及许可文件')
    result = [_ordinary(p) for p in folder.iterdir() if p.is_file() and (p.suffix == '.py' or p.name == 'LICENSE')]
    stack = [folder / name for name in ('comfy', 'comfy_api', 'comfy_execution', 'comfy_extras',
                                      'app', 'api_server', 'middleware', 'utils') if (folder / name).is_dir()]
    total = sum(p.stat().st_size for p in result)
    if len(result) > 8192 or total > 256 * 1024**2:
        raise error('RUNTIME', '运行时代码资源超过8192文件或256MiB预算')
    while stack:
        directory = _ordinary(stack.pop())
        for path in directory.iterdir():
            _ordinary(path)
            if path.is_dir():
                if path.name not in {'__pycache__', '.git'}:
                    stack.append(path)
            elif path.is_file() and path.suffix not in {'.pyc', '.pyo'}:
                result.append(path)
                total += path.stat().st_size
                if len(result) > 8192 or total > 256 * 1024**2:
                    raise error('RUNTIME', '运行时代码资源超过8192文件或256MiB预算')
    return sorted(set(result))


def tree_digest(base, artifacts, role):
    base = Path(base)
    return digest(dict(files=sorted((Path(a['path']).relative_to(base).as_posix(), a['bytes'], a['sha256'])
                                     for a in artifacts if a['role'] == role)))


def prepare_adapter(root, *, adapter_id, model_path, runtime_root, executable, evidence,
                    creator, license_spdx, license_url, permitted_uses, verification_status, threads=4):
    assert_id(adapter_id, 'adapter-id')
    if verification_status not in {'verified', 'unverified', 'restricted'}:
        raise argument_error('verification-status无效')
    model = resolve_local_path(root, model_path, field='model-path')
    runtime = resolve_local_path(root, runtime_root, field='runtime-root')
    python = resolve_local_path(root, executable, field='executable')
    proof = resolve_local_path(root, evidence, field='evidence')
    if python.suffix.lower() != '.exe' or not python.is_file() or not proof.is_file() or proof.stat().st_size > 2 * 1024**2:
        raise error('FILES', '要求原生Python.exe和至多2MiB的本地来源/许可证据')
    artifacts = [artifact_entry(p, 'model') for p in model_files(model)]
    if any(a['sha256'] != 'sha256:' + MODEL_SHA256[Path(a['path']).name] for a in artifacts):
        raise error('MODEL', '模型完整SHA256与固定公开ACE-Step1.5组件不符')
    runtime_paths = runtime_files(runtime)
    empty_files = [p.relative_to(runtime).as_posix() for p in runtime_paths if p.stat().st_size == 0]
    artifacts += [artifact_entry(p, 'runtime') for p in runtime_paths if p.stat().st_size]
    artifacts += [artifact_entry(python, 'python'), artifact_entry(proof, 'evidence')]
    artifacts += [artifact_entry(Path(__file__).with_name(name), 'implementation') for name in IMPLEMENTATIONS]
    stamp = now_iso()
    record = dict(adapter_id=adapter_id, kind='music-generation', engine=ENGINE, protocol=PROTOCOL,
                  output_contract='native-48000-stereo-float32-music-v1', model_path=str(model),
                  model_sha256=tree_digest(model, artifacts, 'model'), runtime_root=str(runtime),
                  runtime_sha256=digest(dict(files=tree_digest(runtime, artifacts, 'runtime'), empty_files=empty_files)),
                  runtime_empty_files=empty_files, executable=str(python),
                  executable_sha256=next(a['sha256'] for a in artifacts if a['role'] == 'python'),
                  rights_ref='music_adapter_' + adapter_id, settings=settings(threads=threads),
                  artifacts=artifacts, network='disabled', registered_at=stamp,
                  verification_status=verification_status)
    record['sha256'] = digest(record)
    rights = dict(asset_id=record['rights_ref'], kind='model-adapter', sha256=record['sha256'],
                  source_url='local://music-adapter/' + adapter_id, source_version=ENGINE,
                  retrieved_at=stamp, creator=creator, license_spdx=license_spdx, license_url=license_url,
                  attribution='', permitted_uses=list(dict.fromkeys(permitted_uses)), permitted_channels=[],
                  restrictions=[], derived_from=[], evidence=str(proof), verification_status=verification_status,
                  verified_by='explicit-local-registration' if verification_status == 'verified' else '',
                  takedown_status='clear', notes='Model, runtime and generated-output rights remain separate.')
    return record, rights


def verify_adapter(record):
    try:
        if (record.get('engine') != ENGINE or record.get('protocol') != PROTOCOL
                or record.get('kind') != 'music-generation' or record.get('network') != 'disabled'
                or record.get('output_contract') != 'native-48000-stereo-float32-music-v1'
                or record['sha256'] != digest(record)
                or record['settings'] != settings(threads=record['settings']['threads'])):
            raise ValueError('Adapter protocol, settings or digest changed')
        artifacts = record['artifacts']
        runtime_paths = runtime_files(record['runtime_root'])
        empty_files = [p.relative_to(Path(record['runtime_root'])).as_posix() for p in runtime_paths if p.stat().st_size == 0]
        if empty_files != record['runtime_empty_files']:
            raise ValueError('Runtime empty package files changed')
        expected = {(str(p.resolve()), role) for role, paths in (
            ('model', model_files(record['model_path'])), ('runtime', [p for p in runtime_paths if p.stat().st_size]),
            ('implementation', [Path(__file__).with_name(name) for name in IMPLEMENTATIONS]),
            ('python', [Path(record['executable'])])) for p in paths}
        actual = {(a['path'], a['role']) for a in artifacts}
        if len(actual) != len(artifacts) or not expected <= actual or len(actual - expected) != 1 or next(iter(actual - expected))[1] != 'evidence':
            raise ValueError('Adapter artifact inventory changed')
        if (record['model_sha256'] != tree_digest(record['model_path'], artifacts, 'model')
                or record['runtime_sha256'] != digest(dict(files=tree_digest(record['runtime_root'], artifacts, 'runtime'), empty_files=empty_files))):
            raise ValueError('Model/runtime identity changed')
        if record['rights_ref'] != 'music_adapter_' + record['adapter_id']:
            raise ValueError('Adapter rights reference changed')
        for item in artifacts:
            if artifact_entry(Path(item['path']), item['role']) != item:
                raise ValueError('Adapter artifact bytes changed: ' + item['path'])
            if item['role'] == 'model' and item['sha256'] != 'sha256:' + MODEL_SHA256[Path(item['path']).name]:
                raise ValueError('Unsupported model component')
        if record['executable_sha256'] != next(a['sha256'] for a in artifacts if a['role'] == 'python'):
            raise ValueError('Python identity changed')
    except (AppError, OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
        return dict(ok=False, engine=ENGINE, findings=[dict(code='MUSIC_GENERATION_ADAPTER_CHANGED', message=str(exc))])
    return dict(ok=True, engine=ENGINE, network='disabled', findings=[])


def recipe(request, adapter, *, samples, pcm_sha256, wav_sha256):
    value = dict(protocol=PROTOCOL, engine=ENGINE, request=prepare_request(request),
                 model_sha256=adapter['model_sha256'], runtime_sha256=adapter['runtime_sha256'],
                 sample_rate=RATE, channels=2, samples=samples, PCM_sha256=pcm_sha256, output_sha256=wav_sha256)
    value['sha256'] = digest(value)
    return value


def validate_recipe(value, *, asset=None):
    try:
        expected = {'protocol', 'engine', 'request', 'model_sha256', 'runtime_sha256', 'sample_rate',
                    'channels', 'samples', 'PCM_sha256', 'output_sha256', 'sha256'}
        if not isinstance(value, dict) or set(value) != expected or value['protocol'] != PROTOCOL or value['engine'] != ENGINE or value['sha256'] != digest(value):
            raise ValueError('Recipe protocol or hash changed')
        request = prepare_request(value['request'])
        if request != value['request'] or value['sample_rate'] != RATE or value['channels'] != 2 or type(value['samples']) is not int or value['samples'] != round(request['duration_seconds'] * RATE):
            raise ValueError('Recipe native sample clock changed')
        import re
        for name in ('model_sha256', 'runtime_sha256', 'PCM_sha256', 'output_sha256'):
            if not isinstance(value[name], str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', value[name]):
                raise ValueError('Recipe digest invalid')
        if asset and (asset['kind'] != 'audio' or asset['sha256'] != value['output_sha256']):
            raise ValueError('Recipe output does not match its asset')
    except (AppError, ValueError, TypeError, KeyError) as exc:
        raise error('RECIPE', '神经音乐配方、输出或原生时钟无效', cause=str(exc)) from exc
    return value
