"""Isolated native HDemucs inference. No checkpoint or package downloads."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

PROTOCOL = 'agent-video-hdemucs-separation-v1'


def install_network_guard(events: list[str]) -> None:
    import socket
    socket.has_ipv6 = False
    def audit(event: str, args: tuple) -> None:
        if event in {'socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr','socket.sendto','urllib.Request','http.client.connect'}:
            events.append(event)
            raise RuntimeError('SEPARATION_NETWORK_DISABLED: '+event)
    sys.addaudithook(audit)


def main() -> int:
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    response = {'protocol':PROTOCOL,'status':'failed','network':'disabled','blocked_network_events':[]}
    started = time.monotonic()
    try:
        if request.get('protocol') != PROTOCOL or request.get('network') != 'disabled':
            raise ValueError('Invalid offline separation request')
        install_network_guard(response['blocked_network_events'])
        runtime = Path(request['runtime_root'])
        for key,name in {'TEMP':'temp','TMP':'temp','TMPDIR':'temp','HF_HOME':'hf','TORCH_HOME':'torch','XDG_CACHE_HOME':'cache'}.items():
            path=runtime/name;path.mkdir(parents=True,exist_ok=True);os.environ[key]=str(path)
        os.environ.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','DO_NOT_TRACK':'1','CUBLAS_WORKSPACE_CONFIG':':4096:8'})
        sys.dont_write_bytecode = True
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from ai_ad_editor.local_separation import verify_adapter
        from ai_ad_editor.separation_dsp import separate_pcm
        from ai_ad_editor.utils import sha256_file
        adapter = request['adapter']
        if not verify_adapter(adapter)['ok']:
            raise ValueError('SEPARATION_INTEGRITY_FAILED')
        source = Path(request['input'])
        if source.stat().st_size != request['samples']*8 or 'sha256:'+sha256_file(source) != request['input_sha256']:
            raise ValueError('SEPARATION_INPUT_HASH_MISMATCH')
        import numpy as np
        import torch
        import torchaudio
        options = adapter['settings']; device = options['device']
        torch.set_num_threads(options['threads']);torch.manual_seed(0)
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False
        if device == 'cuda':
            if not torch.cuda.is_available():raise RuntimeError('SEPARATION_CUDA_UNAVAILABLE')
            torch.cuda.reset_peak_memory_stats()
        # Construct the installed open architecture directly; bundle.get_model
        # would download a checkpoint and is deliberately never used.
        model = torchaudio.models.hdemucs_high(sources=['drums','bass','other','vocals'])
        state = torch.load(adapter['model_path'],map_location='cpu',weights_only=True)
        if not isinstance(state,dict) or not state or any(not isinstance(k,str) or not torch.is_tensor(v) for k,v in state.items()):
            raise ValueError('SEPARATION_STATE_DICT_INVALID')
        model.load_state_dict(state,strict=True);del state
        model.eval().to(device)
        def infer(chunk):
            with torch.inference_mode():
                output = model(torch.from_numpy(chunk).unsqueeze(0).to(device))
            if tuple(output.shape) != (1,4,2,chunk.shape[1]) or not torch.isfinite(output).all():
                raise ValueError('SEPARATION_MODEL_OUTPUT_INVALID')
            return output[0,3].float().cpu().numpy()
        paths = {k:Path(v) for k,v in request['outputs'].items()}
        if set(paths) != {'vocals','accompaniment'} or len({source.resolve(),*[p.resolve() for p in paths.values()]}) != 3 or any(p.exists() for p in paths.values()):
            raise ValueError('SEPARATION_OUTPUT_PATH_INVALID')
        metrics = separate_pcm(source,paths['vocals'],paths['accompaniment'],window=round(options['segment_seconds']*44100),overlap=options['overlap'],infer=infer)
        if response['blocked_network_events']:raise RuntimeError('SEPARATION_NETWORK_ATTEMPT_REJECTED')
        response.update({'status':'succeeded','input_sha256':request['input_sha256'],'source_sha256':request['source_sha256'],'samples':request['samples'],'adapter_sha256':adapter['sha256'],'outputs':{k:{'sha256':'sha256:'+sha256_file(p),'bytes':p.stat().st_size} for k,p in paths.items()},'metrics':metrics,'device':torch.cuda.get_device_name(0) if device=='cuda' else 'cpu','peak_cuda_bytes':torch.cuda.max_memory_allocated(0) if device=='cuda' else None,'versions':{'python':sys.version.split()[0],'numpy':np.__version__,'torch':torch.__version__,'torchaudio':torchaudio.__version__},'module_paths':{'torch':str(torch.__file__),'torchaudio':str(torchaudio.__file__)}})
    except Exception as exc:
        response.update({'error_type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()[-4000:]})
    response['elapsed_seconds'] = round(time.monotonic()-started,3)
    Path(request['response']).write_text(json.dumps(response,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return 0 if response['status']=='succeeded' else 1


if __name__ == '__main__':raise SystemExit(main())
