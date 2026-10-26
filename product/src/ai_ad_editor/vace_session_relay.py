"""Short-lived native pipeline relay; never loads Torch or model weights."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import threading


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ai_ad_editor.model_session import PROTOCOL, CHUNK_BYTES, read_config, connect, send_json, receive_json
    from ai_ad_editor.rvm_worker import install_network_guard
    from ai_ad_editor.utils import atomic_write_json
    install_network_guard([])
    path = Path(sys.argv[1]); request = json.loads(path.read_bytes()); session = request['model_session']
    config = read_config(session['project_root'], session['session_id'])
    errors = []
    with connect(config) as connection:
        send_json(connection, dict(protocol=PROTOCOL, command='execute', request=request))
        accepted = receive_json(connection)
        if accepted.get('ok') is not True: raise ValueError(str(accepted))
        def upload():
            try:
                while True:
                    chunk = sys.stdin.buffer.read(CHUNK_BYTES); connection.send_bytes(chunk)
                    if not chunk: break
            except (OSError, EOFError) as exc: errors.append(str(exc))
        sender = threading.Thread(target=upload, daemon=True); sender.start()
        while True:
            chunk = connection.recv_bytes(CHUNK_BYTES)
            if not chunk: break
            sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush(); sender.join(timeout=10)
        if sender.is_alive() or errors: raise ValueError('MODEL_SESSION_INPUT_STREAM_INCOMPLETE: ' + str(errors))
        response = receive_json(connection)
        if response.get('ok') is not True: raise ValueError(str(response))
        atomic_write_json(Path(request['response']), response['response'])
        return 0 if response['response'].get('status') == 'succeeded' else 1


if __name__ == '__main__': raise SystemExit(main())
