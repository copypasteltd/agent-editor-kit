"""Document the independently installed native61 candidate and terminal gates."""
import hashlib,json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
NOTE='docs/validation/CLI61独立安装交付_2026-10-29.md'

def load(p):return json.loads(p.read_bytes())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    install=load(BASE/'installation-candidate-r1/verification.json')
    assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.61'
    assert install['source_file_count']==283 and len(install['native_artifacts'])==8
    assert install['exact_product_payload']['payload_files']==1707 and install['exact_product_payload']['payload_byte_exact']
    assert sha(install['archive'])==install['archive_sha256']
    assert all(sha(p)==h for p,h in install['registered_skill_file_hashes'].items())
    installed=Path(install['installed']);groups={}
    for group,count in [('bootstrap',31),('loop',37),('control',19),('selection',57)]:
        d=load(BASE/('installed61-'+group+'-r1/verification.json'))
        assert d['status']=='passed' and d['tests']==count and d['frozen_equal'] and d['source_and_installed_equal']
        assert d['failures']==d['errors']==d['skipped']==0
        assert all(sha(ROOT/p)==h for p,h in d['file_hashes'].items());groups[group]=count
    for name in ['stage-gate-check-r1','activation-gate-check-r1']:
        assert load(BASE/name/'verification.json')['status']=='passed'
    stage=load(BASE/'stage-gate-check-r1/verification.json')
    assert stage['runner_sha256']==sha(ROOT/'docs/validation/stage_source61_skill.py')
    gate=load(BASE/'activation-gate-check-r1/verification.json')
    assert gate['activation_runner_sha256']==sha(ROOT/'docs/validation/activate_source61_skill.py')
    semantic=BASE/'installed61-semantic-r1/verification.json'
    semantic_status=load(semantic)['status'] if semantic.exists() else 'not-terminal'
    full=BASE/'installed61-contracts-r1/verification.json'
    full_status=load(full)['status'] if full.exists() else 'not-terminal'
    out=BASE/'candidate-publication-r1';out.mkdir(exist_ok=False)
    rows={
        'README.md':[
            'CLI61/local59原生ZIP已构建并独立安装；1707载荷／283模块／8项ICC与OCIO资源一致，版本与能力查询通过。',
            '安装31入口／37配乐／19控制／57选材分别通过，零失败／错误／跳过，源码与安装及测试冻结一致。语义104与完整403以独立终态为准，不重复汇总。',
            '缺证时实际请求生成Skill及--apply激活均被拒绝，95个正式文件不变。CLI61激活仍要求完整安装403及实际PowerShell循环／DF3／MuseTalk；正式仍CLI59。'],
        'README.zh-TW.md':[
            'CLI61/local59原生ZIP已建置並獨立安裝；1707載荷／283模組／8項ICC與OCIO資源一致，版本及能力查詢通過。',
            '安裝31入口／37配樂／19控制／57選材分別通過，零失敗／錯誤／跳過，原始碼與安裝及測試凍結一致。語義104及完整403以獨立終態為準，不重複彙總。',
            '缺證時實際要求建立Skill及--apply啟用均遭拒，95個正式檔案不變。CLI61啟用仍要求完整安裝403及實際PowerShell循環／DF3／MuseTalk；正式仍CLI59。'],
        'README.en.md':[
            'CLI61/local59 native ZIP built and independently installed;1707 payload files/283 modules/8 ICC and OCIO resources exact,actual version and capabilities passed.',
            'Installed bootstrap31/loop-score37/control19/selection57 passed separately,zero failures/errors/skips,source/install/test hashes frozen.Semantic104 and full403 require separate terminal results;no duplicate aggregate.',
            'Actual Skill staging and --apply activation requests rejected missing evidence;95 registered files unchanged.Promotion61 still requires installed403 and actual PowerShell loop/DF3/MuseTalk cases.The registered Skill remains59.']}
    for name,values in rows.items():
        p=ROOT/name;s=p.read_text(encoding='utf-8')
        prior=subprocess.check_output([GIT,'--no-optional-locks','show','dce96f8886222fd96d53d3b17be93909b6e57247:'+name],cwd=ROOT).decode('utf-8')
        old=[l for l in prior.splitlines() if re.match(r'^\| R\d+ \|',l)]
        assert len(old)==483 and all(l in s for l in old)
        lines=s.splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('| R483 |'))
        for j,value in enumerate(values):lines.insert(i+1+j,f'| R{484+j} | CLI61 native candidate | '+value+' [Package / usage]('+NOTE+') |')
        s='\n'.join(lines)+'\n';ids=re.findall(r'^\| (R\d+) \|',s,re.M)
        assert len(ids)==len(set(ids))==486
        p.write_text(s,encoding='utf-8',newline='\n')
    doc=f'''# CLI61 / local59 独立原生安装候选

正式注册仍 CLI59／local57／r57。新的 CLI61／local59 已构建、独立安装并核对完整产品载荷；这不等于安装版全部服务或统一Skill已验收。CLI60旧候选失败收据和旧包保留。

| 编号 | 项目 | 实际内容 |
| --- | --- | --- |
| A01 | 本地ZIP | `{Path(install['archive']).as_posix()}` |
| A02 | 字节数 | {install['archive_bytes']} |
| A03 | ZIP SHA256 | `{install['archive_sha256']}` |
| A04 | Manifest SHA256 | `{install['manifest_sha256']}` |
| A05 | 产品wheel SHA256 | `{install['product_wheel_sha256']}` |
| A06 | 已安装目录 | `{installed.as_posix()}` |
| A07 | 载荷核对 | 1707文件；283应用模块与源码相同；8项ICC／OCIO原生资源相同 |

[安装构建收据](evidence/lipsync-timeout-20261029-r1/installation-candidate-r1/verification.json)。使用原生Windows、本地已有Python和依赖，临时／构建文件在E盘；无Docker／WSL、网络下载或全局安装。本机候选验收不等于另一台干净机器或其他GPU已验收。

## 使用逻辑

先明确调用本次安装候选，检查版本及能力：

```powershell
$python = 'C:/Python313/python.exe'
$entry = '{(installed/'run.py').as_posix()}'
& $python -I -S -B -X utf8 $entry version
& $python -I -S -B -X utf8 $entry capabilities
```

版本应为 `0.1.61`。这是独立安装入口，不调用开发源码，也不改变仍绑定CLI59的 `$agent-ffmpeg-local-editor`。按照 [已有基础流程](CLI59独立安装交付_2026-10-29.md)初始化工程、登记本地素材及权利，再选择具体能力。模型权重与GPU原生运行时仍按各服务说明登记，不把产品ZIP当作所有模型权重已包含。

以下工程须已导入音频资产 `music`，且有有效权利记录；先只读预检，再生成新ID，检查／试听后再挂接、渲染及导出可编辑工程包：

```powershell
$project = 'E:/video-work/my-project'
& $python -I -S -B -X utf8 $entry music repair-loop --project $project --asset-id music --crossfade-ms 50 --curve raised-cosine --new-asset-id loop1 --dry-run
& $python -I -S -B -X utf8 $entry music repair-loop --project $project --asset-id music --crossfade-ms 50 --curve raised-cosine --new-asset-id loop1 --apply --track-id track_audio_1
```

交叠会缩短周期，工作PCM明确转为48kHz双声道16bit；CPU DSP不做神经音乐或节拍／乐句结构重写。较低接缝跳变不证明自然听感无缝。完整参数、原始／输出音频、配方和实际C76工程包见 [循环修复手册](../product/MUSIC_LOOP.md)。

## 当前验收与正式切换

源码完整403、31入口、37循环配乐、19控制、57选材、104语义及实际循环、DF3、MuseTalk案例已分别通过。[完整源码收据](CLI61完整源码验收_2026-10-29.md)。安装31／37／19／57分别通过，零失败／错误／跳过；发布本文时安装语义104收据为 `{semantic_status}`，完整403收据为 `{full_status}`。后续结果按各自原始收据，不以运行中日志或文件存在计通过。

`run_source61_install_acceptance.py`按安装31／37／19／57／104、实际DF3 CUDA、循环工程重做、实际MuseTalk CUDA执行；MuseTalk另逐字节对比源码的主文件和成片RGBA／PCM。完整403单独运行，不重复计数。

已实际请求生成未注册Skill和 `--apply` 激活，两者在缺少收据时均拒绝，95个正式文件不变。新统一Skill只保留一个公开入口、17内部模块、93文件；准备脚本尚不代表Skill已生成、注册或通过实际PowerShell验证。完整安装403、源／安装MuseTalk、PowerShell循环／DF3／MuseTalk三类案例都是正式切换条件；实际生成后还须运行Skill静态验证。正式切换前不会将CLI61源码或候选静默绑定到旧入口。

- [安装31](evidence/lipsync-timeout-20261029-r1/installed61-bootstrap-r1/verification.json)
- [安装37](evidence/lipsync-timeout-20261029-r1/installed61-loop-r1/verification.json)
- [安装19](evidence/lipsync-timeout-20261029-r1/installed61-control-r1/verification.json)
- [安装57](evidence/lipsync-timeout-20261029-r1/installed61-selection-r1/verification.json)
- [Skill生成缺证拒绝](evidence/lipsync-timeout-20261029-r1/stage-gate-check-r1/verification.json)
- [实际激活缺证拒绝](evidence/lipsync-timeout-20261029-r1/activation-gate-check-r1/verification.json)

真实口型抽帧存在下半脸柔化，连续播放／听审与自然质量仍待验收；不得以传输相同代替G24质量关闭。所有38项完整产品关闭条件继续有效，不宣称完整剪映等价。
'''
    (ROOT/NOTE).write_text(doc,encoding='utf-8',newline='\n')
    p=ROOT/'docs/product/MUSIC_LOOP.md';s=p.read_text(encoding='utf-8');a=s.index('\n\n')+2;b=s.index('\n\n',a)
    s=s[:a]+'本命令由CLI60引入。当前开发源码CLI61完整403项服务契约及真实案例已通过，CLI61／local59独立候选已安装并核对载荷，安装完整验收与Skill升级另行执行。正式统一Skill仍CLI59／local57／r57，不能通过旧入口调用本命令。CLI60旧候选的400项失败保留。[最新候选位置、摘要和使用流程](../validation/CLI61独立安装交付_2026-10-29.md)。'+s[b:]
    p.write_text(s,encoding='utf-8',newline='\n')
    paths=[ROOT/n for n in rows]+[ROOT/NOTE,p]
    report=dict(status='passed',source_cli='0.1.61',candidate_cli='0.1.61',candidate_local='local59',formal_cli='0.1.59',
        payload_files=1707,app_modules=283,native_resources=8,terminal_installed_groups=groups,
        semantic_status_at_publication=semantic_status,full403_status_at_publication=full_status,
        README_rows=486,previous483_rows_preserved=True,protected_files_unchanged=95,
        actual_stage_and_activation_rejected=True,formal_activation=False,
        file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='file_hashes'}),flush=True)

if __name__=='__main__':main()
