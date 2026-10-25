"""Run remaining native evidence phases sequentially; never overlap model workers."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    phases=(('before','cuda'),('before','cpu'),('upgrade',None),('after','cuda'),('after','cpu'),('roundtrip',None),('skill','cuda'))
    for phase,device in phases:
        argv=[sys.executable,'-E','-B','-u','-X','utf8',str(ROOT/'scripts/run_semantic_upgrade_case_20261025.py'),'--phase',phase]
        if device:argv+=['--device',device]
        result=subprocess.run(argv,cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:raise SystemExit(result.returncode)


if __name__=='__main__':main()
