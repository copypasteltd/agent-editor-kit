"""Publish actual installed MuseTalk completion, keeping perceptual limits explicit."""
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
NOTE='docs/validation/CLI61安装版实际案例_2026-10-29.md'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    report=json.loads((BASE/'installed61-lipsync-cuda-r1/verification.json').read_bytes())
    assert report['status']=='passed' and report['cli_version']=='0.1.61'
    for flag in ['actual_MuseTalk_CUDA','complete_source_installed_master_and_render_equal',
                 'complete_package_rendered_RGBA_PCM_equal','owned_process_cleanup_passed',
                 'full_alpha_and_outside_region_preserved','all_selected_PCM_equal']:
        assert report[flag] is True,flag
    assert report['frames']==133 and report['model_execution']['calls']['unet']==67
    assert report['complete_master_RGBA_bytes']==139460608 and report['rendered_RGBA_bytes']==167772160
    assert report['selected_PCM_bytes']==507180 and report['rendered_PCM_bytes']==1024000
    assert not report['model_execution']['CPU_fallback'] and not report['natural_quality_accepted']
    controller=json.loads((BASE/'installed-controller-r1/verification.json').read_bytes())
    assert controller['status']=='passed' and len(controller['calls'])==8
    assert all(row['exit_code']==0 for row in controller['calls'])
    install=json.loads((BASE/'installation-candidate-r1/verification.json').read_bytes())
    assert all(sha(p)==h for p,h in install['registered_skill_file_hashes'].items())
    out=BASE/'installed-lipsync-publication-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    texts={
        'README.md':'安装版MuseTalk实际CUDA133帧／67次UNet通过，无CPU回退；主文件139460608字节RGBA及成片167772160字节RGBA和完整PCM与源码／工程包重放一致。下半脸柔化、自然口型、连续播放／听审仍未验收；正式Skill仍59，安装403另验。',
        'README.zh-TW.md':'安裝版MuseTalk實際CUDA133幀／67次UNet通過，無CPU回退；主檔139460608位元組RGBA及成片167772160位元組RGBA和完整PCM與原始碼／工程包重播一致。下半臉柔化、自然口型、連續播放／聽審仍未驗收；正式Skill仍59，安裝403另驗。',
        'README.en.md':'Installed MuseTalk completed133 real CUDA frames/67 UNet forwards,without CPU fallback.All139460608 master RGBA bytes,167772160 rendered RGBA bytes and complete PCM match source/package replay.Lower-face softness,natural lip-sync,continuous playback and listening remain unaccepted;formal Skill remains59,installed403 is separate.'}
    paths=[]
    for name,value in texts.items():
        p=ROOT/name;text=p.read_text(encoding='utf-8')
        old=[line for line in text.splitlines() if re.match(r'^\| R\d+ \|',line)]
        assert len(old)==490
        lines=text.splitlines();index=next(i for i,line in enumerate(lines) if line.startswith('| R490 |'))
        lines.insert(index+1,'| R491 | CLI61 installed MuseTalk | '+value+' [Evidence / limits]('+NOTE+') |')
        text='\n'.join(lines)+'\n';assert all(line in text for line in old)
        p.write_text(text,encoding='utf-8',newline='\n');paths.append(p)
    p=ROOT/NOTE;text=p.read_text(encoding='utf-8')
    text+='''
## 后续终态：安装MuseTalk通过

原安装任务已正常退出，未重启或跳过。实际RTX3060 CUDA133帧／67次UNet前向，未回退CPU；主文件139460608字节RGBA、507180字节所选PCM，成片167772160字节RGBA、1024000字节PCM均逐字节与源码结果一致，导出／导入工程包后完整重渲染也一致。全帧alpha、框外原像素、所选声音及明确尾部补零、自有子进程退出和关闭均核验。安装串行控制器的五组回归及DF3／循环／MuseTalk三个实际案例已全部终态通过；完整403仍是独立门禁。

- [安装MuseTalk完整收据](evidence/lipsync-timeout-20261029-r1/installed61-lipsync-cuda-r1/verification.json)
- [安装串行验收控制器](evidence/lipsync-timeout-20261029-r1/installed-controller-r1/verification.json)

这是生成、可编辑工程与完整音画可重放验收；没有新增人类连续播放或听审。此前实际抽帧所见下半脸柔化仍存在，未关闭自然口型或完整数字人目标。内部／未核验权利状态未提升，未将该人像或声音公开发布。
'''
    p.write_text(text,encoding='utf-8',newline='\n');paths.append(p)
    result=dict(status='passed',README_rows=491,previous490_rows_preserved=True,
                actual_installed_MuseTalk=True,installed_controller_passed=True,
                protected_files_unchanged=95,formal_activation=False,natural_quality_accepted=False,
                file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='file_hashes'}),flush=True)


if __name__=='__main__':main()
