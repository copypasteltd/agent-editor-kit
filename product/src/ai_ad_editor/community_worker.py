"""Pinned native CPU/CUDA worker, launched only after pack verification."""
from pathlib import Path
import json
import ctypes
import os
import subprocess
import sys
import time
import wave

PROTOCOL = 'agent-community-cpu-v1'


def main():
    request = json.loads(Path(sys.argv[1]).read_text('utf-8'))
    assert request['protocol'] == PROTOCOL
    root = Path(request['pack']).resolve(strict=True)
    sys.path[:0] = [str(root / 'site'), request['base_site']]
    # These local engines have no download path. Also reject Python network
    # connections so optional code cannot silently acquire missing inputs.
    def offline(event, args):
        if event in {'socket.connect', 'socket.getaddrinfo', 'socket.bind'}:
            raise RuntimeError('Network disabled in community model worker')
    sys.addaudithook(offline)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                      OMP_NUM_THREADS='2', CT2_USE_EXPERIMENTAL_PACKED_GEMM='0')
    dll = os.add_dll_directory(str(root / 'bin')) if (root / 'bin').is_dir() else None
    task, payload = request['task'], request['payload']
    provider = payload.get('device', 'cpu')
    external_dll = None
    preload = []
    if provider == 'cuda':
        directory = payload.get('cuda_library_directory')
        if directory:
            external_dll = os.add_dll_directory(directory)
            os.environ['PATH'] = directory + os.pathsep + os.environ.get('PATH', '')
        os.environ['PATH'] = str(root / 'bin') + os.pathsep + os.environ.get('PATH', '')
        # CT2 uses its own dynamic loader; preload explicit CUDA libraries so
        # Windows resolves them without editing the system PATH.
        if task == 'translate' and directory:
            preload = [ctypes.WinDLL(str(Path(directory) / name)) for name in ('cublasLt64_12.dll', 'cublas64_12.dll')]
    started = time.perf_counter()
    if task == 'voice':
        import numpy as np
        import sherpa_onnx
        os.chdir(root / 'models/kokoro')
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model='model.onnx' if provider == 'cuda' else 'model.int8.onnx', voices='voices.bin', tokens='tokens.txt',
                    lexicon='lexicon-zh.txt,lexicon-us-en.txt,lexicon-gb-en.txt'),
                num_threads=payload['threads'], provider=provider, debug=provider == 'cuda'),
            rule_fsts='date-zh.fst,number-zh.fst,phone-zh.fst', max_num_sentences=1)
        assert config.validate()
        engine = sherpa_onnx.OfflineTts(config)
        loaded = time.perf_counter()
        if 'segments' in payload:
            from ai_ad_editor.dubbing import synthesize_segments
            data = synthesize_segments(engine, payload)
            provider_loaded = bool(ctypes.windll.kernel32.GetModuleHandleW('onnxruntime_providers_cuda.dll')) if provider == 'cuda' else False
            if provider == 'cuda' and not provider_loaded:
                raise RuntimeError('CUDA provider DLL did not load; refusing a CPU result labelled CUDA')
            data.update(engine_version=sherpa_onnx.__version__, requested_provider=provider,
                speaker_count=engine.num_speakers, initialization_seconds=loaded-started,
                generation_seconds=time.perf_counter()-loaded, cuda_provider_dll_loaded=provider_loaded,
                compute_type='float32' if provider == 'cuda' else 'int8_model')
        else:
            data = single_voice(engine, payload, provider, sherpa_onnx, np, loaded, started)
    elif task == 'translate':
        data = translate(root, payload, provider)
    else:
        raise ValueError('Unknown task')
    result = dict(protocol=PROTOCOL, ok=True, task=task, provider=provider,
                  elapsed_seconds=time.perf_counter() - started, network='disabled', **data)
    response = Path(request['response'])
    with response.open('x', encoding='utf-8') as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'ok': True, 'task': task, 'elapsed_seconds': result['elapsed_seconds']}), flush=True)
    if dll:
        dll.close()
    if external_dll:
        external_dll.close()


def single_voice(engine, payload, provider, sherpa_onnx, np, loaded, started):
        audio = engine.generate(payload['text'], sid=payload['speaker_id'], speed=payload['speed'])
        generation_seconds = time.perf_counter() - loaded
        provider_loaded = bool(ctypes.windll.kernel32.GetModuleHandleW('onnxruntime_providers_cuda.dll')) if provider == 'cuda' else False
        if provider == 'cuda' and not provider_loaded:
            raise RuntimeError('CUDA provider DLL did not load; refusing a CPU result labelled CUDA')
        samples = np.asarray(audio.samples, dtype=np.float32)
        assert samples.size and np.isfinite(samples).all()
        pcm = (np.clip(samples, -1, 1) * 32767).round().astype('<i2')
        output = Path(payload['output'])
        # Exclusive output creation is preserved even after model startup.
        with output.open('xb') as handle:
            with wave.open(handle, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(audio.sample_rate)
                wav.writeframes(pcm.tobytes())
        data = dict(engine_version=sherpa_onnx.__version__, voice_id=payload['voice_id'], requested_provider=provider,
                    speaker_id=payload['speaker_id'], speaker_count=engine.num_speakers,
                    output=str(output), sample_rate=audio.sample_rate, channels=1,
                    samples=int(samples.size), duration_seconds=float(samples.size / audio.sample_rate),
                    peak=float(np.abs(samples).max()), rms=float(np.sqrt(np.mean(samples ** 2))), speed=payload['speed'],
                    initialization_seconds=loaded-started, generation_seconds=generation_seconds,
                    cuda_provider_dll_loaded=provider_loaded, compute_type='float32' if provider == 'cuda' else 'int8_model')
        return data


def translate(root, payload, provider):
        import sentencepiece as spm
        from opencc import OpenCC
        pair = payload['pair']
        assert pair in {'zh-en', 'en-zh'}
        os.chdir(root / 'models' / pair)
        source = spm.SentencePieceProcessor(model_file='source.spm')
        target = spm.SentencePieceProcessor(model_file='target.spm')
        texts = payload['texts']
        if pair == 'zh-en':
            texts = [OpenCC('t2s').convert(t) for t in texts]
        batch = [source.encode(t, out_type=str) for t in texts]
        if pair == 'en-zh':
            batch = [['>>cmn_Hans<<', *tokens] for tokens in batch]
        # Refuse truncation; callers split long text deliberately.
        assert all(0 < len(tokens) <= 512 for tokens in batch), 'Input exceeds 512 model tokens'
        if provider == 'cuda':
            import ctranslate2
            if ctranslate2.get_cuda_device_count() <= payload['device_index']:
                raise RuntimeError('Requested CUDA device is unavailable')
            translator = ctranslate2.Translator('.', device='cuda', device_index=payload['device_index'],
                                                 compute_type='int8_float16', inter_threads=1)
            results = translator.translate_batch(batch, beam_size=payload['beam_size'], max_batch_size=8,
                                                  max_input_length=512, max_decoding_length=1024,
                                                  length_penalty=1, return_scores=True)
            hypotheses = [r.hypotheses[0] for r in results]
            scores = [r.scores[0] for r in results]
            actual_compute = translator.compute_type
        else:
            argv = [str(root / 'bin/ct2-translator.exe'), '--model', '.', '--device', 'cpu',
                '--compute_type', 'int8', '--intra_threads', str(payload['threads']), '--inter_threads', '1',
                '--beam_size', str(payload['beam_size']), '--batch_size', '8', '--max_input_length', '512',
                '--max_decoding_length', '1024', '--length_penalty', '1', '--with_score']
            completed = subprocess.run(argv, input=('\n'.join(' '.join(t) for t in batch) + '\n').encode('utf8'),
                                   capture_output=True, timeout=1500, creationflags=subprocess.CREATE_NO_WINDOW)
            if completed.returncode:
                raise RuntimeError('Native Ruy translation failed: ' + completed.stderr.decode('utf8', errors='replace')[-3000:])
            rows = [line.split(' ||| ', 1) for line in completed.stdout.decode('utf8').splitlines()]
            assert len(rows) == len(texts) and all(len(row) == 2 for row in rows), 'Native translation count/format mismatch'
            hypotheses = [row[1].split() for row in rows]
            scores = [float(row[0]) for row in rows]
            actual_compute = 'int8'
        assert all(0 < len(tokens) < 1024 for tokens in hypotheses), 'Decoder limit reached; output refused'
        translations = [target.decode(tokens) for tokens in hypotheses]
        assert len(translations) == len(texts) and all(t.strip() for t in translations)
        if pair == 'en-zh':
            conversion = 's2twp' if payload['target_language'] == 'zh-Hant' else 't2s'
            translations = [OpenCC(conversion).convert(t) for t in translations]
        data = dict(engine_version='4.8.3', backend='CUDA' if provider == 'cuda' else 'Ruy', native_executable=provider != 'cuda', pair=pair,
                    output=translations, input_token_counts=[len(t) for t in batch],
                    scores=scores, compute_type=actual_compute,
                    target_language=payload['target_language'], beam_size=payload['beam_size'])
        return data


if __name__ == '__main__':
    main()
