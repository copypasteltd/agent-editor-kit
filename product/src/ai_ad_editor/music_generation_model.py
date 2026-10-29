"""Headless native ACE 1.5 execution; the worker owns every imported model."""
import gc
from importlib.metadata import version
import sys
import time
from pathlib import Path


def generate(adapter, request, work, *, phase, check):
    runtime = Path(adapter['runtime_root'])
    model_root = Path(adapter['model_path'])
    sys.path.insert(0, str(runtime))
    (work / 'comfy/models').mkdir(parents=True, exist_ok=True)
    sys.argv = ['agent-music-worker', '--base-directory', str(work / 'comfy'),
                '--models-directory', str(work / 'comfy/models'), '--offline',
                '--use-pytorch-cross-attention', '--disable-pinned-memory']
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

    if not torch.cuda.is_available() or management.get_torch_device().type != 'cuda':
        raise ValueError('ACE15_REQUIRES_ACTUAL_CUDA_NO_CPU_FALLBACK')
    torch.set_num_threads(adapter['settings']['threads'])
    torch.cuda.set_device(0)
    torch.cuda.reset_peak_memory_stats(0)
    counts = {'text': 0, 'language_model': 0, 'diffusion': 0, 'vae': 0}
    devices = {key: set() for key in counts}
    hooks = []
    timings = {}
    started = time.monotonic()

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
    clip = comfy.sd.load_clip(
        [str(model_root / 'text_encoder.safetensors'), str(model_root / 'language_model.safetensors')],
        embedding_directory=[], clip_type=comfy.sd.CLIPType.ACE,
        model_options={'dtype': torch.bfloat16})
    cuda_module(clip.cond_stage_model.qwen3_06b.transformer, 'text')
    cuda_module(getattr(clip.cond_stage_model, clip.cond_stage_model.lm_model).transformer, 'language_model')
    phase('encoding-music-request')
    with torch.inference_mode():
        positive = TextEncodeAceStepAudio15.execute(
            clip, request['prompt'], '[Instrumental]' if request['instrumental'] else request['lyrics'],
            request['seed'], request['bpm'], request['duration_seconds'], str(request['timesignature']),
            request['language'], request['keyscale'], request['generate_audio_codes'],
            2.0, 0.85, 0.9, 0, 0.0)[0]
    timings['text_load_and_encode_seconds'] = time.monotonic() - begin
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
    model = comfy.sd.load_diffusion_model(str(model_root / 'diffusion_model.safetensors'),
                                         model_options={'dtype': torch.bfloat16})
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
    state = comfy.utils.load_torch_file(str(model_root / 'vae.safetensors'), safe_load=True)
    vae = comfy.sd.VAE(sd=state)
    del state
    cuda_module(vae.first_stage_model.decoder, 'vae')
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
    for handle in hooks:
        handle.remove()
    del audio, waveform, vae, result
    release()
    return output, dict(engine=adapter['engine'], neural_backend='cuda', CPU_fallback=False,
        cpu_weight_offload=True, forwards=counts, forward_output_devices={k:sorted(v) for k,v in devices.items()},
        text_admission=text_admission, diffusion_admission=diffusion_admission,
        device=torch.cuda.get_device_name(0), torch=torch.__version__, cuda=torch.version.cuda,
        runtime_packages={name:version(name) for name in ('numpy', 'safetensors', 'torchaudio', 'transformers')},
        peak_allocated_bytes=torch.cuda.max_memory_allocated(0), peak_reserved_bytes=torch.cuda.max_memory_reserved(0),
        timings=timings, elapsed_seconds=time.monotonic() - started,
        sample_rate=48000, channels=2, samples=expected_samples,
        service_started=False, shared_queue_touched=False, natural_quality_accepted=False)
