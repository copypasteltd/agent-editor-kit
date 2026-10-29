"""Verify real Windows process lifetime handles used by the delivery controller."""
import importlib.util,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
script=ROOT/'docs/validation/run_source62_delivery_pipeline.py'
spec=importlib.util.spec_from_file_location('delivery62',script);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
out=ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1/process-observer-check-r1';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
child=subprocess.Popen([sys.executable,'-I','-B','-c','import sys;sys.stdin.buffer.read(1)'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
handle=None
try:
 handle=module.OwnedProcess(child.pid);assert handle.running()
 stdout,stderr=child.communicate(input=b'x',timeout=30);assert child.returncode==0 and not stdout and not stderr
 assert not handle.running();handle.close();assert handle.handle is None
 try:module.OwnedProcess(0xfffffffe)
 except OSError:invalid_rejected=True
 else:raise AssertionError('Nonexistent process was accepted')
 report=dict(status='passed',actual_Windows_process=True,live_handle_observed=True,terminal_handle_observed=True,missing_process_rejected=True,handle_closed=True,child_returncode=child.returncode,formal_activation=False)
 (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report))
finally:
 if handle:handle.close()
 if child.poll() is None:child.kill();child.wait(timeout=30)
