"""Headless native ACE 1.5 execution; the worker owns every imported model."""
import ast
from contextlib import contextmanager
import gc
from importlib.metadata import version
import sys
import threading
import time
from pathlib import Path


WEIGHT_NAMES = frozenset(('text_encoder.safetensors', 'language_model.safetensors',
                         'diffusion_model.safetensors', 'vae.safetensors'))


def runtime_arguments(runtime, work):
    """Use declared flags only; the worker always installs its network guard."""
    tree = ast.parse((Path(runtime) / 'comfy/cli_args.py').read_bytes())
    flags = {arg.value for node in ast.walk(tree)
             if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
             and node.func.attr == 'add_argument' for arg in node.args
             if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith('--')}
    required = {'--base-directory', '--models-directory', '--use-pytorch-cross-attention',
                '--disable-pinned-memory', '--disable-dynamic-vram'}
    if not required <= flags:
        raise ValueError('ACE15_REQUIRED_RUNTIME_FLAGS_MISSING: ' + ','.join(sorted(required - flags)))
    arguments = ['agent-music-worker', '--base-directory', str(work / 'comfy'),
                 '--models-directory', str(work / 'comfy/models'), '--use-pytorch-cross-attention',
                 '--disable-pinned-memory', '--disable-dynamic-vram']
    if '--offline' in flags:
        arguments.append('--offline')
    return arguments, '--offline' in flags


@contextmanager
def weight_reader(model_root, names, *, read_report):
    """Select pread only for this isolated worker's exact model component set.

    Keep the native Comfy checkpoint loader and its tensor/metadata handling.
    An unsupported reader fails rather than retrying with mmap or pickle.
    """
    import safetensors
    model_root = Path(model_root).resolve(strict=True)
    names = tuple(names)
    if not names or len(set(names)) != len(names) or not set(names) <= WEIGHT_NAMES:
        raise ValueError('ACE15_WEIGHT_COMPONENT_SET_INVALID')
    allowed = {model_root / name for name in names}
    if any(not path.is_file() or path.is_symlink() or getattr(path, 'is_junction', lambda: False)() for path in allowed):
        raise ValueError('ACE15_LOCAL_WEIGHT_FILE_REQUIRED')
    native = safetensors.safe_open
    opened = {}
    lock = threading.Lock()

    def local_open(filename, framework, device='cpu', *, backend='mmap'):
        path = Path(filename).resolve(strict=True)
        if path not in allowed or framework != 'pt' or device != 'cpu' or backend not in {'mmap', 'pread'}:
            raise ValueError('ACE15_WEIGHT_READ_OUTSIDE_COMPONENT')
        pointer = native(str(path), framework=framework, device=device, backend='pread')
        with lock:
            opened[path.name] = opened.get(path.name, 0) + 1
        return pointer

    try:
        safetensors.safe_open = local_open
        yield
        if set(opened) != set(names):
            raise ValueError('ACE15_WEIGHT_READER_NOT_USED_FOR_ALL_COMPONENTS')
    finally:
        safetensors.safe_open = native
    read_report.extend(dict(file=name, backend='pread', opens=opened[name]) for name in sorted(opened))


def validate_weight_reads(value):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('ACE15_COMPLETE_WEIGHT_READ_REPORT_REQUIRED')
    seen = set()
    for item in value:
        if (not isinstance(item, dict) or set(item) != {'file', 'backend', 'opens'}
                or item['file'] not in WEIGHT_NAMES or item['file'] in seen
                or item['backend'] != 'pread' or type(item['opens']) is not int or not 1 <= item['opens'] <= 16):
            raise ValueError('ACE15_WEIGHT_READ_REPORT_INVALID')
        seen.add(item['file'])


def generate(adapter, request, work, *, phase, check):
    started = time.monotonic()
    phase('importing-music-runtime')
    runtime = Path(adapter['runtime_root'])
    model_root = Path(adapter['model_path'])
    sys.path.insert(0, str(runtime))
    (work / 'comfy/models').mkdir(parents=True, exist_ok=True)
    sys.argv, offline_flag = runtime_arguments(runtime, work)
    import comfy.options
    comfy.options.enable_args_parsing()
    import torch
    import comfy.sd
    import comfy.sample
    import comfy.model_management as management
    import comfy.model_sampling
    import comfy.utils
    import folder_paths
    from comfy_extras.nodes_ace import TextEncodeAceStepAudio15, EmptyAceStep15LatentAudio
    from comfy_extras.nodes_audio import VAEDecodeAudio
    from .cuda_admission import admit_cuda, HEADROOM_BYTES

    if comfy.memory_management.aimdo_enabled:
        raise ValueError('ACE15_STATIC_WEIGHT_READER_REQUIRED')
    if not torch.cuda.is_available() or management.get_torch_device().type != 'cuda':
        raise ValueError('ACE15_REQUIRES_ACTUAL_CUDA_NO_CPU_FALLBACK')
    torch.set_num_threads(adapter['settings']['threads'])
    torch.cuda.set_device(0)
    torch.cuda.reset_peak_memory_stats(0)
    counts = {'text': 0, 'language_model': 0, 'diffusion': 0, 'vae': 0}
    devices = {key: set() for key in counts}
    hooks = []
    timings = {'runtime_import_seconds': time.monotonic() - started}
    read_report = []

    def tensors(value):
        if isinstance(value, torch.Tensor):
            yield value
        elif isinstance(value, (tuple, list)):
            for part in value:
                yield from tensors(part)
        elif isinstance(value, dict):
            for part in value.values():
                yield from tensors(part)

    def watch(module, label):
        def observed(unused_module, unused_args, output):
            values = list(tensors(output))
            if not values or any(v.device.type != 'cuda' for v in values):
                raise ValueError('ACE15_NEURAL_OUTPUT_LEFT_CUDA: ' + label)
            counts[label] += 1
            devices[label].update(str(v.device) for v in values)
            check()
        hooks.append(module.register_forward_hook(observed))

    def release():
        management.unload_all_models()
        gc.collect()
        torch.cuda.synchronize(0)
        management.soft_empty_cache()

    def cuda_module(module, label):
        # Instrument the actual neural forward, rather than reporting CUDA
        # solely from device discovery or the final copied output tensor.
        watch(module, label)

    phase('admitting-music-text')
    text_admission = admit_cuda(torch, 6 * 1024**3 + HEADROOM_BYTES, 'music-text')
    phase('loading-music-text')
    begin = time.monotonic()
    with weight_reader(model_root, ('text_encoder.safetensors', 'language_model.safetensors'), read_report=read_report):
        clip = comfy.sd.load_clip(
            [str(model_root / 'text_encoder.safetensors'), str(model_root / 'language_model.safetensors')],
            embedding_directory=[], clip_type=comfy.sd.CLIPType.ACE,
            model_options={'dtype': torch.bfloat16})
    timings['text_checkpoint_load_seconds'] = time.monotonic() - begin
    cuda_module(clip.cond_stage_model.qwen3_06b.transformer, 'text')
    cuda_module(getattr(clip.cond_stage_model, clip.cond_stage_model.lm_model).transformer, 'language_model')
    phase('encoding-music-request')
    encoding_started = time.monotonic()
    with torch.inference_mode():
        positive = TextEncodeAceStepAudio15.execute(
            clip, request['prompt'], '[Instrumental]' if request['instrumental'] else request['lyrics'],
            request['seed'], request['bpm'], request['duration_seconds'], str(request['timesignature']),
            request['language'], request['keyscale'], request['generate_audio_codes'],
            2.0, 0.85, 0.9, 0, 0.0)[0]
    timings['text_load_and_encode_seconds'] = time.monotonic() - begin
    timings['text_encode_seconds_including_device_load'] = time.monotonic() - encoding_started
    if counts['text'] < 1 or request['generate_audio_codes'] and counts['language_model'] < 1:
        raise ValueError('ACE15_TEXT_OR_LANGUAGE_MODEL_FORWARD_NOT_OBSERVED')
    for handle in hooks:
        handle.remove()
    hooks.clear()
    del clip
    phase('releasing-music-text')
    release()

    phase('admitting-music-diffusion')
    diffusion_admission = admit_cuda(torch, 6 * 1024**3 + HEADROOM_BYTES, 'music-diffusion', expected_uuid=text_admission['device_uuid'])
    phase('loading-music-diffusion')
    begin = time.monotonic()
    with weight_reader(model_root, ('diffusion_model.safetensors',), read_report=read_report):
        model = comfy.sd.load_diffusion_model(str(model_root / 'diffusion_model.safetensors'),
                                             model_options={'dtype': torch.bfloat16})
    timings['diffusion_checkpoint_load_seconds'] = time.monotonic() - begin
    if model is None:
        raise ValueError('ACE15_MODEL_TYPE_NOT_RECOGNIZED')
    # Same flow sampling transform as the official ACE 1.5 AuraFlow node:
    # shift=3, multiplier=1. SD3's default multiplier=1000 is inappropriate.
    class MusicSampling(comfy.model_sampling.ModelSamplingDiscreteFlow, comfy.model_sampling.CONST):
        pass
    sampling = MusicSampling(model.model.model_config)
    sampling.set_parameters(shift=adapter['settings']['shift'], multiplier=1.0)
    original = model.get_model_object('model_sampling')
    if hasattr(original, 'noise_scale'):
        sampling.set_noise_scale(original.noise_scale)
    model.add_object_patch('model_sampling', sampling)
    cuda_module(model.model.diffusion_model, 'diffusion')
    sampling_started = time.monotonic()
    with torch.inference_mode():
        latent = EmptyAceStep15LatentAudio.execute(request['duration_seconds'], 1)[0]['samples']
        noise = comfy.sample.prepare_noise(latent, request['seed'])
        negative = [[torch.zeros_like(value), {**metadata}] for value, metadata in positive]

        def callback(step, unused_x0, unused_x, total):
            phase('generating-music', step + 1, total)

        result = comfy.sample.sample(model, noise, request['steps'], 1.0, 'euler', 'simple',
                                     positive, negative, latent, denoise=1.0,
                                     callback=callback, disable_pbar=True, seed=request['seed'])
    timings['diffusion_load_and_generate_seconds'] = time.monotonic() - begin
    timings['diffusion_sample_seconds_including_device_load'] = time.monotonic() - sampling_started
    if counts['diffusion'] < request['steps']:
        raise ValueError('ACE15_DIFFUSION_FORWARDS_NOT_OBSERVED')
    for handle in hooks:
        handle.remove()
    hooks.clear()
    del model, positive, negative, noise, latent
    phase('releasing-music-diffusion')
    release()

    phase('decoding-music-audio')
    begin = time.monotonic()
    with weight_reader(model_root, ('vae.safetensors',), read_report=read_report):
        state = comfy.utils.load_torch_file(str(model_root / 'vae.safetensors'), safe_load=True)
    vae = comfy.sd.VAE(sd=state)
    del state
    timings['vae_checkpoint_load_seconds'] = time.monotonic() - begin
    cuda_module(vae.first_stage_model.decoder, 'vae')
    decoding_started = time.monotonic()
    with torch.inference_mode():
        audio = VAEDecodeAudio.execute(vae, {'samples': result})[0]
    waveform = audio['waveform']
    expected_samples = round(request['duration_seconds'] * 48000)
    if audio['sample_rate'] != 48000 or tuple(waveform.shape) != (1, 2, expected_samples):
        raise ValueError('ACE15_NATIVE_OUTPUT_CLOCK_OR_CHANNELS_CHANGED: ' + str(tuple(waveform.shape)))
    if not torch.isfinite(waveform).all() or counts['vae'] < 1:
        raise ValueError('ACE15_INVALID_OR_UNOBSERVED_NEURAL_AUDIO')
    output = waveform[0].detach().to(device='cpu', dtype=torch.float32).transpose(0, 1).contiguous().numpy()
    timings['vae_load_and_decode_seconds'] = time.monotonic() - begin
    timings['vae_decode_seconds_including_device_load'] = time.monotonic() - decoding_started
    for handle in hooks:
        handle.remove()
    del audio, waveform, vae, result
    release()
    validate_weight_reads(read_report)
    return output, dict(engine=adapter['engine'], neural_backend='cuda', CPU_fallback=False,
        local_weight_reads=read_report, dynamic_vram=False, offline_cli_flag_supported=offline_flag,
        elapsed_includes_runtime_import=True,
        cpu_weight_offload=True, forwards=counts, forward_output_devices={k:sorted(v) for k,v in devices.items()},
        text_admission=text_admission, diffusion_admission=diffusion_admission,
        device=torch.cuda.get_device_name(0), torch=torch.__version__, cuda=torch.version.cuda,
        runtime_packages={name:version(name) for name in ('numpy', 'safetensors', 'torchaudio', 'transformers')},
        peak_allocated_bytes=torch.cuda.max_memory_allocated(0), peak_reserved_bytes=torch.cuda.max_memory_reserved(0),
        timings=timings, elapsed_seconds=time.monotonic() - started,
        sample_rate=48000, channels=2, samples=expected_samples,
        service_started=False, shared_queue_touched=False, natural_quality_accepted=False)
