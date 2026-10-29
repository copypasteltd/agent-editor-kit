"""Attach verified voice documentation to activation; never rewrite tested candidates."""
from pathlib import Path
import hashlib

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation'


def update(path,changes):
    text=path.read_text(encoding='utf-8')
    for old,new in changes:
        assert text.count(old)==1,(path,old)
        text=text.replace(old,new,1)
    compile(text,str(path),'exec');path.write_text(text,encoding='utf-8',newline='\n')


def main():
    update(BASE/'activate_source61_skill.py',[
        ("    gates = {'installation':BASE/'installation-candidate-r1/verification.json',",
         "    gates = {'voice_auditions':ROOT/'docs/validation/evidence/voice-auditions-20261029-r1/r2/verification.json',\n            'installation':BASE/'installation-candidate-r1/verification.json',"),
        ("    assert files==candidate['candidate_files'] and len(files)==93",
         "    assert files==candidate['candidate_files'] and len(files)==93\n    from source61_voice_skill_overlay import prepare\n    contents,registered_files,documentation_overlay=prepare(stage,files,reports['voice_auditions'])"),
        ("            content=(stage/name).read_bytes()","            content=contents[name]"),
        ("        assert files=={p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}",
         "        assert registered_files=={p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}"),
        ("        namespace_sha256=sha(namespace),runtime_sha256=sha(runtime),registered_model_case_pending=True,",
         "        namespace_sha256=sha(namespace),runtime_sha256=sha(runtime),registered_model_case_pending=True,\n        tested_candidate_files=files,registered_files=registered_files,documentation_overlay=documentation_overlay,")])
    for name in ['loop','gpu','lipsync']:
        update(BASE/('run_registered61_'+name+'_case.py'),[
            ("    stage=load(ROOT/'local/agent-ffmpeg/music61-skill-stage-r1/STAGING.json')",
             "    stage=load(ROOT/'local/agent-ffmpeg/music61-skill-stage-r1/STAGING.json')\n    from source61_voice_skill_overlay import validate_registered\n    stage=validate_registered(stage,activation)")])
    # Save a new actual-negative runner; the old r1 evidence remains immutable.
    text=(BASE/'check_source61_activation_gate.py').read_text(encoding='utf-8')
    text=text.replace("assert not (BASE/'staged-actual-case-r1/verification.json').exists()",
                      "assert not (BASE/'staged61-lipsync-cuda-r1/verification.json').exists()")
    text=text.replace("assert not (BASE/'staged61-gpu-r1/verification.json').exists()",'')
    text=text.replace('activation-gate-check-r1','activation-gate-check-r2').replace('skill61-activation-gate-check-r1','skill61-activation-gate-check-r2')
    text=text.replace("'gate-check-r1'","'gate-check-r2'")
    text=text.replace("assert 'installed61_contracts' in response['missing']","assert 'staged61_lipsync' in response['missing']")
    text=text.replace('installed403_still_required=True','installed403_still_required=True,voice103_evidence_required=True')
    text='\n'.join(line.rstrip() for line in text.splitlines())+'\n'
    path=BASE/'check_source61_activation_gate_r2.py';assert not path.exists();compile(text,str(path),'exec');path.write_text(text,encoding='utf-8',newline='\n')
    text=(BASE/'check_source61_registered_delivery_gate.py').read_text(encoding='utf-8').replace('registered-delivery-gate-check-r1','registered-delivery-gate-check-r2')
    text=text.replace('gatecheckr1','gatecheckr2')
    path=BASE/'check_source61_registered_delivery_gate_r2.py';assert not path.exists();compile(text,str(path),'exec');path.write_text(text,encoding='utf-8')
    print('Prepared mandatory103-audition documentation overlay;tested stage/runtime files and old receipts unchanged.')


if __name__=='__main__':main()
