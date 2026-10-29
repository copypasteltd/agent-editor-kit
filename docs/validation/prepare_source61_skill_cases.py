"""Prepare real PowerShell loop/DF3/MuseTalk candidate checks without registration."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/validation'

def write(name,text):
    p=DOC/name;compile(text,str(p),'exec')
    if p.exists():assert p.read_text(encoding='utf-8')==text,name
    else:p.write_text(text,encoding='utf-8',newline='\n')

def main():
    text=(DOC/'prepare_source60_skill_cases.py').read_text(encoding='utf-8')
    for a,b in [('source60','source61'),('installed60','installed61'),('staged60','staged61'),
        ('loop60','loop61'),('0.1.60','0.1.61'),('installed400','installed403')]:text=text.replace(a,b)
    # Execute this generator in its own namespace; it only writes derived scripts.
    exec(compile(text,str(DOC/'prepare_source60_skill_cases.py')+'[CLI61-derived]','exec'),
         {'__file__':str(DOC/'prepare_source60_skill_cases.py'),'__name__':'__main__'})
    text=(DOC/'run_installed61_lipsync_case.py').read_text(encoding='utf-8')
    text=text.replace("parser.add_argument('--run', required=True)","parser.add_argument('--run', required=True)\n    parser.add_argument('--skill',type=Path,required=True)")
    text=text.replace("mode='installed61' if installed else 'source61'", "mode='staged61'\n    skill=args.skill.resolve()\n    stage=load(skill.parents[1]/'STAGING.json')\n    assert stage['status']=='unregistered-candidate' and stage['cli_version']=='0.1.61'\n    assert Path(stage['installed']).resolve()==installed\n    assert stage['candidate_files']=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}")
    text=text.replace("BASE/(mode+'-bootstrap-'+args.gate_run)","BASE/('installed61-bootstrap-'+args.gate_run)")
    start=text.index('    prefix = ');end=text.index('    sys.path.insert',start)
    text=text[:start]+"    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(skill/'scripts/run.ps1')]\n"+text[end:]
    needle="        assert all(sha(p) == h for p,h in protected_pins.items())\n"
    assert needle in text
    text=text.replace(needle,needle+"        assert stage['candidate_files']=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}\n")
    text=text.replace("actual_MuseTalk_CUDA=True,", "actual_MuseTalk_CUDA=True,actual_PowerShell_entry=True,candidate_registered=False,candidate_files_unchanged=True,candidate_files=stage['candidate_files'],")
    write('run_staged61_lipsync_case.py',text)
    print('Prepared CLI61 PowerShell MuseTalk comparison; no execution or registration.',flush=True)

if __name__=='__main__':main()
