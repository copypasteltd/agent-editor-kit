"""Prepare strict CLI61 Skill staging and installed lip-sync equivalence checks."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DOC=ROOT/'docs/validation'

def write(name,text):
    p=DOC/name;compile(text,str(p),'exec')
    if p.exists():assert p.read_text(encoding='utf-8')==text,name
    else:p.write_text(text,encoding='utf-8',newline='\n')

def main():
    text=(DOC/'stage_source60_skill.py').read_text(encoding='utf-8')
    for old,new in [('CLI60','CLI61'),('source60','source61'),('installed60','installed61'),
        ('music60','music61'),('0.1.60','0.1.61'),('cli0160','cli0161'),
        ('v0.1.0-alpha.4-local.58','v0.1.0-alpha.4-local.59'),
        ('music-loop-20261029-r1','lipsync-timeout-20261029-r1')]:text=text.replace(old,new)
    text=text.replace("BASE/'targeted-r1/verification.json'","BASE/'source61-loop-r1/verification.json'")
    text=text.replace("('contracts',400)","('contracts',403)")
    marker="            paths[mode+'_'+group]=BASE/(mode+'-'+group+'-r1/verification.json')\n"
    assert marker in text
    text=text.replace(marker,marker+"        paths[mode+'_lipsync']=BASE/(mode+'-lipsync-cuda-r1/verification.json')\n")
    marker="    for k in ['source_loop','installed_loop']:\n"
    assert marker in text
    text=text.replace(marker,"    for mode in ['source61','installed61']:\n"
        +"        r=reports[mode+'_lipsync']\n"
        +"        assert r['status']=='passed' and r['cli_version']=='0.1.61' and r['actual_MuseTalk_CUDA']\n"
        +"        assert r['frames']==133 and r['complete_master_RGBA_bytes']==139460608\n"
        +"        assert r['complete_package_rendered_RGBA_PCM_equal'] and r['owned_process_cleanup_passed']\n"
        +"        assert r['model_execution']['CPU_fallback'] is False and r['model_execution']['calls']['unet']==67\n"
        +"        if mode=='installed61':assert r['complete_source_installed_master_and_render_equal']\n"+marker)
    text=text.replace("requires_actual_PowerShell_loop_and_CUDA_before_activation=True", "requires_actual_PowerShell_loop_and_CUDA_before_activation=True,requires_installed403=True,requires_actual_installed_MuseTalk=True")
    write('stage_source61_skill.py',text)
    text=(DOC/'run_source61_lipsync_case.py').read_text(encoding='utf-8')
    text=text.replace("parser.add_argument('--installed', type=Path)","parser.add_argument('--installed', type=Path,required=True)")
    marker="        assert all(sha(p) == h for p,h in protected_pins.items())\n"
    assert marker in text
    text=text.replace(marker,marker+"        reference=ROOT/'local/agent-ffmpeg/native-worker-source61-lipsync-r1'\n"
        +"        source_case=load(BASE/'source61-lipsync-cuda-r1/verification.json')\n"
        +"        assert source_case['status']=='passed' and source_case['actual_MuseTalk_CUDA']\n"
        +"        expected={}\n"
        +"        for name in ['master-rgba','master-pcm','rendered-rgba','rendered-pcm']:\n"
        +"            left,right=reference/(name+'.raw'),work/(name+'.raw')\n"
        +"            assert left.stat().st_size==right.stat().st_size\n"
        +"            expected[name]=sha(left)\n"
        +"            assert expected[name]==sha(right),name\n")
    text=text.replace("actual_MuseTalk_CUDA=True, model_execution=execution,", "actual_MuseTalk_CUDA=True,complete_source_installed_master_and_render_equal=True,source_master_and_render_sha256=expected, model_execution=execution,")
    write('run_installed61_lipsync_case.py',text)
    print('Prepared CLI61 strict single-Skill staging and installed MuseTalk full-byte comparison; not activated.',flush=True)

if __name__=='__main__':main()
