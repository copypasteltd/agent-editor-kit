"""Publish only terminal CLI61 checks and real CUDA/replay results."""
import hashlib,json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
NOTE='docs/validation/CLI61原生交付核验_2026-10-29.md'

def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    counts={}
    for name,count in [('control',19),('selection',57),('semantic',104)]:
        d=load(BASE/('source61-'+name+'-r1')/'verification.json')
        assert d['status']=='passed' and d['tests']==count and d['frozen_equal']
        assert d['failures']==d['errors']==d['skipped']==0
        assert all(sha(ROOT/p)==h for p,h in d['file_hashes'].items());counts[name]=count
    loop=load(BASE/'actual-case-r1/verification.json');gpu=load(BASE/'source61-gpu-r1/verification.json')
    lip=load(BASE/'source61-lipsync-cuda-r1/verification.json')
    gate=load(BASE/'build-gate-check-r2/verification.json')
    assert all(d['status']=='passed' for d in [loop,gpu,lip,gate])
    assert loop['complete_repaired_PCM_bytes']==2557440 and loop['complete_package_recipe_repair_PCM_equal']
    assert loop['complete_repaired_PCM_sha256']=='5ef874d97415455650ed207bed5e8239a9628b440f41c17ef1ca037058f41ac1'
    assert gpu['actual_CUDA_model'] and gpu['complete_PCM_replay_equal'] and gpu['complete_PCM_bytes']==1124160
    assert gpu['complete_PCM_sha256']=='83354f670149b119a676c978e21a5a08b3e5a936bbcc1f33dd836cf42ddb2d12'
    assert lip['actual_MuseTalk_CUDA'] and lip['frames']==133 and lip['model_execution']['calls']['unet']==67
    assert lip['complete_package_rendered_RGBA_PCM_equal'] and lip['owned_process_cleanup_passed']
    assert lip['model_execution']['CPU_fallback'] is False
    old=load(ROOT/'docs/validation/evidence/music-loop-20261029-r1/installation-candidate-r1/verification.json')
    assert all(sha(p)==h for p,h in old['registered_skill_file_hashes'].items())
    full=BASE/'source61-contracts-r1/verification.json'
    full_status=load(full)['status'] if full.exists() else 'not-terminal'
    out=BASE/'delivery-publication-r1';out.mkdir(exist_ok=False)
    link=' [Evidence]('+NOTE+')'
    texts={
        'README.md':[
            '控制19／选材57／语义104分别通过，零失败／错误／跳过，应用和测试冻结一致。',
            '真实循环修复及工程包重做通过，完整2557440字节PCM与CLI60参考相同；真实DF3 CUDA完整1124160字节PCM工程重放通过，受控噪声MSE改善12.25446dB。',
            '真实MuseTalk CUDA：133帧、67次UNet前向，无CPU回退；原alpha与区域外像素、选定PCM、关联可编辑音画、子进程回收及完整成片RGBA／PCM工程重放通过；不计自然口型或听审。',
            '缺少完整403及真实案例证据时实际拒绝构建，95正式文件不变、未创建候选。r1检查脚本Windows路径比较失败保留，r2修正后通过。'],
        'README.zh-TW.md':[
            '控制19／選材57／語義104分別通過，零失敗／錯誤／跳過，應用和測試凍結一致。',
            '真實循環修復及專案封裝重做通過，完整2557440位元組PCM與CLI60參考相同；真實DF3 CUDA完整1124160位元組PCM專案重播通過，受控噪聲MSE改善12.25446dB。',
            '真實MuseTalk CUDA：133影格、67次UNet前向，無CPU回退；原alpha與區域外像素、選定PCM、關聯可編輯音畫、子行程回收及完整成片RGBA／PCM專案重播通過；不計自然口型或聽審。',
            '缺少完整403及真實案例證據時實際拒絕建置，95正式檔案不變、未建立候選。r1檢查腳本Windows路徑比較失敗保留，r2修正後通過。'],
        'README.en.md':[
            'Control19/selection57/semantic104 passed separately,zero failures/errors/skips,app and tests frozen.',
            'Actual loop recipe/package replay passed;complete2557440-byte PCM matches CLI60 reference.Actual DF3 CUDA replay passed with complete1124160-byte PCM and12.25446dB controlled-noise MSE improvement.',
            'Actual MuseTalk CUDA:133 frames,67 UNet forwards,no CPU fallback.Original alpha/outside pixels,selected PCM,linked editable tracks,owned-child cleanup and complete encoded RGBA/PCM package replay passed.No natural lip-sync or listening acceptance.',
            'Build actually rejected missing403/real-case evidence;95 registered files unchanged,no candidate created.Windows path comparison failed in audit r1,preserved;corrected r2 passed.']}
    for name,rows in texts.items():
        p=ROOT/name;s=p.read_text(encoding='utf-8')
        prior=subprocess.check_output([GIT,'--no-optional-locks','show','00b724855d4d76c58d55697a1170589b1d73da56:'+name],cwd=ROOT).decode('utf-8')
        priorrows=[l for l in prior.splitlines() if re.match(r'^\| R\d+ \|',l)]
        assert len(priorrows)==477 and all(l in s for l in priorrows)
        lines=s.splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('| R477 |'))
        for j,row in enumerate(rows):lines.insert(i+1+j,f'| R{478+j} | CLI61 native delivery | '+row+link+' |')
        s='\n'.join(lines)+'\n';ids=re.findall(r'^\| (R\d+) \|',s,re.M)
        assert len(ids)==len(set(ids))==481
        p.write_text(s,encoding='utf-8',newline='\n')
    doc='''# CLI61 原生交付核验

本轮继续交付 CLI0.1.61 源码的任务级超时修复，未改动媒体／GPU算法，也未使用 Docker、WSL、容器、新模型下载或新全局依赖。正式注册仍 CLI59／local57／r57；旧 CLI60／local58 的安装400项失败记录保留，不能作为新安装验收。

## 已完成

控制19、选材57、语义104分别通过，零失败／错误／跳过，283应用模块及测试前后哈希一致。上轮口型31、隔离入口31、循环配乐37的收据保持独立，不叠加宣称新功能数量。

真实C76循环修复：641760帧源音频，2400帧交叠后639360帧周期，原始主体PCM保留；三次连续重复、可编辑工程导出／导入／配方重做全部比较完整PCM。2557440字节PCM SHA256为 `5ef874d97415455650ed207bed5e8239a9628b440f41c17ef1ca037058f41ac1`，与CLI60参考相同。[参考音频](../assets/music-loop60-installed-20261029-r1/actual.wav)与本轮输出PCM逐字节相同；本轮实际产物路径见收据。

真实DF3 CUDA：4次前向、无CPU回退，完整1124160字节PCM及工程重放通过；受控噪声MSE改善12.25446dB。这是固定人工加噪检查，不是自然声音或听审验收。

真实MuseTalk CUDA：133帧、67次UNet前向、1次模型加载，无CPU回退；CUDA峰值分配2802346496字节。逐帧核对源alpha与区域外像素、全部选定Float32 PCM及明确尾部静音；生成可编辑关联音画轨，并渲染、导出工程、导入并重渲染，完整RGBA／PCM相同。三条自有子进程正常退出、stdout关闭且无清理警告。素材为既有虚构肖像和合成语音；没有真人参考、连续人眼播放、听审或自然口型质量验收。本轮没有把这一重验计为新模型功能。

## 构建门禁

`build_source61_delivery.py`的新候选目标是 `local/agent-ffmpeg/v0.1.0-alpha.4-local.59/`。只有源码37／31／57／104／403／19组、真实循环案例、实际DF3 CUDA及实际MuseTalk CUDA全部通过并符合冻结条件，才能构建；实际缺证测试已拒绝构建，95正式文件未变，未创建候选。r1检查脚本错误地以POSIX路径字符串比较Windows原生路径，审计失败原样保留；构建本身已拒绝。r2规范化比较后检查通过，未削弱门禁。

源码手动验证入口：

```powershell
& C:/Python313/python.exe -E -B -u -X utf8 E:/dev/sandbox/AI广告剪辑/scripts/run_source_editor.py version
```

这是显式源码入口，正式 `$agent-ffmpeg-local-editor` 仍指向已安装CLI59，不回落源码。新安装版的31／19／57／104／403等分组、实际模型与循环案例、统一Skill入口和最终工具包必须另行验收，不能用本页源码收据代替。

## 证据

- [19项控制](evidence/lipsync-timeout-20261029-r1/source61-control-r1/verification.json)
- [57项选材](evidence/lipsync-timeout-20261029-r1/source61-selection-r1/verification.json)
- [104项语义](evidence/lipsync-timeout-20261029-r1/source61-semantic-r1/verification.json)
- [真实循环及配方重做](evidence/lipsync-timeout-20261029-r1/actual-case-r1/verification.json)
- [真实DF3 CUDA及完整PCM重放](evidence/lipsync-timeout-20261029-r1/source61-gpu-r1/verification.json)
- [真实MuseTalk CUDA及完整成片重放](evidence/lipsync-timeout-20261029-r1/source61-lipsync-cuda-r1/verification.json)
- [缺证构建拒绝r2](evidence/lipsync-timeout-20261029-r1/build-gate-check-r2/verification.json)
- [r1路径比较失败](evidence/lipsync-timeout-20261029-r1/build-gate-check-r1/verification.json)

完整403项仅按其单独终态判断，不据中间日志计通过。完整产品38项关闭条件保持原文，当前不宣称完整剪映等价。
'''
    doc+='\n发布本页时，完整403项收据状态：`'+full_status+'`。\n'
    doc+='\n本次口型工程的素材、模型及生成视频权利账本仍为 `internal`／`unverified`；本轮只提交验证记录，不把新口型视频发布为可商用公开演示，也不提升权利状态。完整本地成片位于 `E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/native-worker-source61-lipsync-r1/project/renders/movie.mp4`。\n'
    (ROOT/NOTE).write_text(doc,encoding='utf-8',newline='\n')
    report=dict(status='passed',terminal_groups=counts,actual_loop=True,actual_DF3_CUDA=True,
        actual_MuseTalk_CUDA=True,MuseTalk_frames=133,UNet_forwards=67,
        full403_status_at_publication=full_status,formal_skill_unchanged=95,README_rows=481,
        previous477_rows_preserved=True,source_cli='0.1.61',candidate_cli='0.1.60',formal_cli='0.1.59',
        file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in [ROOT/n for n in texts]+[ROOT/NOTE]})
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='file_hashes'}),flush=True)

if __name__=='__main__':main()
