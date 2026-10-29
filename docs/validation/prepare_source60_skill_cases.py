"""Prepare real PowerShell candidate cases; no registration or model execution here."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def write(name,text):
    p=ROOT/'docs/validation'/name
    if p.exists():assert p.read_text(encoding='utf-8')==text;return
    compile(text,str(p),'exec');p.write_text(text,encoding='utf-8')

def main():
    text=(ROOT/'docs/validation/run_installed60_loop_case.py').read_text(encoding='utf-8')
    text=text.replace("parser.add_argument('--installed',type=Path,required=True);a=parser.parse_args()", "parser.add_argument('--installed',type=Path,required=True);parser.add_argument('--skill',type=Path,required=True);a=parser.parse_args()")
    needle="    installed=a.installed.resolve()"
    text=text.replace(needle,needle+"\n    skill=a.skill.resolve()\n    assert skill.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())\n    stage=load(skill.parents[1]/'STAGING.json')\n    assert stage['status']=='unregistered-candidate' and stage['cli_version']=='0.1.60'\n    assert stage['candidate_files']=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}")
    text=text.replace("'music-loop60-installed-case-'","'music-loop60-staged-case-'")
    text=text.replace("('installed-actual-case-'+a.run)","('staged-actual-case-'+a.run)")
    text=text.replace("argv=[PYTHON,'-I','-S','-B','-u','-X','utf8',str(installed/'run.py'),*map(str,args)]", "argv=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(skill/'scripts/run.ps1'),*map(str,args)]")
    text=text.replace("source_only=False,source_fallback=False,installed=str(installed),", "source_only=False,source_fallback=False,actual_PowerShell_entry=True,candidate_registered=False,skill=str(skill),installed=str(installed),")
    write('run_staged60_loop_case.py',text)
    text=(ROOT/'docs/validation/run_source60_gpu_case.py').read_text(encoding='utf-8')
    text=text.replace("parser.add_argument('--installed', type=Path, help=", "parser.add_argument('--skill',type=Path,required=True)\n    parser.add_argument('--installed', type=Path,required=True, help=")
    text=text.replace("mode = 'installed60' if installed else 'source60'", "mode = 'staged60'\n    skill=args.skill.resolve()\n    assert skill.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())\n    stage=load(skill.parents[1]/'STAGING.json')\n    assert stage['candidate_files']=={p.relative_to(skill).as_posix():sha(p) for p in skill.rglob('*') if p.is_file()}\n    case=load(BASE/'staged-actual-case-r1/verification.json')\n    assert case['status']=='passed' and case['actual_PowerShell_entry']")
    start=text.index('    prefix = ');end=text.index('    calls = ',start)
    text=text[:start]+"    prefix = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(skill/'scripts/run.ps1')]\n"+text[end:]
    text=text.replace("actual_CUDA_model=True,", "actual_CUDA_model=True,actual_PowerShell_entry=True,candidate_registered=False,skill=str(skill),")
    write('run_staged60_gpu_case.py',text)
    print('Prepared actual PowerShell loop and CUDA candidate runners; not executed.')

if __name__=='__main__':main()
