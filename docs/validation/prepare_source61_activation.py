"""Prepare transactional activation61 requiring installed403 and three real PS cases."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/validation'

def main():
    text=(DOC/'activate_source60_skill.py').read_text(encoding='utf-8')
    for a,b in [('CLI60','CLI61'),('cli60','cli61'),('source60','source61'),('installed60','installed61'),
        ('staged60','staged61'),('skill60','skill61'),('music60','music61'),('0.1.60','0.1.61'),
        ('v0.1.0-alpha.4-local.58','v0.1.0-alpha.4-local.59'),
        ('music-loop-20261029-r1','lipsync-timeout-20261029-r1')]:text=text.replace(a,b)
    text=text.replace("BASE/'targeted-r1/verification.json'","BASE/'source61-loop-r1/verification.json'")
    text=text.replace("('contracts',400)","('contracts',403)")
    marker="    missing = [name for name,path in gates.items() if not path.is_file()]\n"
    assert marker in text
    text=text.replace(marker,"    for mode in ['source61','installed61','staged61']:\n"
        +"        gates[mode+'_lipsync']=BASE/(mode+'-lipsync-cuda-r1/verification.json')\n"+marker)
    marker="    candidate = reports['candidate']\n"
    assert marker in text
    text=text.replace(marker,"    for mode in ['source61','installed61','staged61']:\n"
        +"        r=reports[mode+'_lipsync']\n"
        +"        assert r['cli_version']=='0.1.61' and r['actual_MuseTalk_CUDA'] and r['frames']==133\n"
        +"        assert r['complete_package_rendered_RGBA_PCM_equal'] and r['owned_process_cleanup_passed']\n"
        +"        assert r['model_execution']['CPU_fallback'] is False and r['model_execution']['calls']['unet']==67\n"
        +"        if mode!='source61':assert r['complete_source_installed_master_and_render_equal']\n"
        +"    r=reports['staged61_lipsync'];assert r['actual_PowerShell_entry'] and r['candidate_files_unchanged']\n"
        +"    assert r['candidate_files']==reports['candidate']['candidate_files']==reports['staged_gpu']['candidate_files']\n"+marker)
    p=DOC/'activate_source61_skill.py';compile(text,str(p),'exec')
    if p.exists():assert p.read_text(encoding='utf-8')==text
    else:p.write_text(text,encoding='utf-8',newline='\n')
    print('Prepared strict403 activation61 with real DF3/loop/MuseTalk PS gates and rollback; not activated.',flush=True)

if __name__=='__main__':main()
