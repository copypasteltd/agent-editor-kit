"""Record the rejected candidates and the precise scope of installed particle checks."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/procedural-particles-20261027-r1'

def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

def main():
    out=BASE/'development-attempts-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    failures=[
        ('source-particles-r1','Test fixture read error instead of the actual errors envelope; fixture repaired.'),
        ('source-integration-r1','Product OTIO native-background omission repaired; queue test was separately corrected to request its MKV container.'),
        ('installed-file-before-fix-r1','Three real custom/signal-file reads failed with str.open; bounded Path-based JSON reader added.'),
        ('case-r1','Actual registered Skill custom-file apply reproduced the same reader failure before any scene render.'),
        ('case-r2','Case runner used a cwd-relative output outside the project; the existing output containment guard rejected it. Runner/docs now use project-contained absolute output paths.')]
    records=[]
    for name,reason in failures:
        p=BASE/name/'verification.json';value=load(p);assert value['status']=='failed'
        records.append({'attempt':name,'status':'failed','record_sha256':sha(p),'reason':reason})
    groups=[]
    for name,count in [('installed-particles-r2',19),('installed-particle-gpu-r3',1),('installed-integration-r2',5),('installed-legacy-r2',192)]:
        p=BASE/name/'verification.json';value=load(p)
        assert value['status']=='passed' and value['tests']==count
        assert value['failures']==value['errors']==value['skipped']==0 and value['test_frozen_equal'] and value['frozen_equal']
        groups.append({'attempt':name,'tests':count,'record_sha256':sha(p)})
    prior=load(BASE/'installed-native-regression-r1/verification.json');assert prior['status']=='passed' and prior['tests']==427
    change=load(BASE/'loader-final-r1/verification.json')
    assert change['byte_identical_product_files']==231 and change['changed_product_files']==['procedural_cli.py','utils.py']
    activation_failure=BASE/'activation-final-r2/activation.stderr.txt'
    assert 'Skill inventory changed' in activation_failure.read_text('utf8')
    records.append({'attempt':'activation-final-r2','status':'rejected-before-configuration',
        'record_sha256':sha(activation_failure),'reason':'Activation was started before the preceding inventory refresh completed; the integrity guard rejected the stale inventory. Sequential activation-final-r3 succeeded.'})
    case=load(BASE/'case-r3/verification.json');assert case['status']=='passed'
    install=load(BASE/'installation-final-r2/verification.json')
    case_calls=load(BASE/'case-r3/calls.json')
    render_seconds={name:next(c['seconds'] for c in case_calls if c['id']==name) for name in ('render','render-restored')}
    r=load(BASE/'installed-particle-gpu-r3/receipts.json')['test_procedural_particles']['RECEIPTS'][0]
    assert r['operations']['particles']==23 and r['worker_closed']
    report={'status':'recorded','at_utc':datetime.now(timezone.utc).isoformat(),'final_product_files':233,
        'rejected_attempts':records,'final_installed_groups':groups,'earlier_native_regression_tests':427,
        'earlier_native_regression_installation':'final-r1','changed_product_files':change['changed_product_files'],
        'byte_identical_product_files':231,'pixel_and_GPU_kernels_byte_identical':True,
        'final_legacy_regression_rerun':True,'final_installed_input_file_and_idempotency_tests':True,
        'particle_gpu_comparisons':23,'particle_cpu_max_error':r['particle_cpu_max_error'],
        'C45_render_wall_seconds':render_seconds,'C45_matched_CPU_timing':False,
        'retained_rejected_bundle':'local/agent-ffmpeg/v0.1.0-alpha.4-local.33/candidate-r1/bundle.zip',
        'source_fallback':False,'goal_complete':False}
    save(out/'verification.json',report)
    text='''# 可编辑粒子：实际安装版核验（2026-10-27）

本轮实现 G06 中的二维可编辑粒子源，CLI0.1.35 / alpha.4-local.33。
使用原生 Windows、现有 Python/FFmpeg 和原生 OpenCL；没有调用 Docker、WSL、虚拟环境或远端服务。
外层仍为一个 `$agent-ffmpeg-local-editor`，内部17模块；实际调用已校验离线安装版。
完整剪映等价、全部特效和38项原关闭条件没有因此关闭。

## 实际通过的范围

| 验收 | 实际执行及边界 | 原始记录 |
|---|---|---|
| 最终离线安装 | 233个产品Python文件与源码逐字节一致、76项能力声明、Schema一致；没有源码回退。 | [安装](evidence/procedural-particles-20261027-r1/installation-final-r2/verification.json) |
| 粒子及文件接口 | 19项：独立时钟、seed、随机访问、解析运动/透明度/顺序、边角、资源准入、取消、源范围、事务/锁定、JSON文件和同路径内容变更幂等冲突。 | [19项](evidence/procedural-particles-20261027-r1/installed-particles-r2/verification.json) |
| 真实GPU | 1项测试执行23次粒子栅格化：6配方×3帧及5形状，预乘颜色和alpha对照独立CPU实现；实际RTX/OpenCL设备和生命周期在收据中。 | [测试](evidence/procedural-particles-20261027-r1/installed-particle-gpu-r3/verification.json)、[设备与数值](evidence/procedural-particles-20261027-r1/installed-particle-gpu-r3/receipts.json) |
| 真实编码与编辑 | 5项：24帧CPU/GPU编码最大1个10-bit码值差；192000个双声道浮点样本为零；包/本地OTIO全部帧一致、预览命中/seed失效、实际队列、分割/嵌套倒放。 | [集成](evidence/procedural-particles-20261027-r1/installed-integration-r2/verification.json)、[实际调用](evidence/procedural-particles-20261027-r1/installed-integration-r2/receipts.json) |
| 旧流程回归 | 最终安装版192项，零失败、零跳过。 | [最终192项](evidence/procedural-particles-20261027-r1/installed-legacy-r2/verification.json) |
| 既有原生链路 | 首候选final-r1上427项通过；后续只改文件读取与通用幂等指纹，231个文件（含全部像素/GPU内核）相同。最终19/1/5/192另跑；427并非最终包重跑数。 | [原始427项](evidence/procedural-particles-20261027-r1/installed-native-regression-r1/verification.json)、[字节对应](evidence/procedural-particles-20261027-r1/loader-final-r1/verification.json) |
| 实际注册Skill案例 | 48帧、12FPS、960×360、4秒六宫格，288次粒子GPU调度；可编辑包迁移后48帧RGB全相同；解码AAC数值为静音，未宣称PCM母版/延迟一致。 | [C45执行](evidence/procedural-particles-20261027-r1/case-r2/verification.json)、[全部命令](evidence/procedural-particles-20261027-r1/case-r2/calls.json) |
| 独立Skill套件 | r36的76 Skill文件、单入口/17模块；独立目录解包/登记、vfx查询/说明、既有工程只读计划；不会改变真实发现目录。 | [kit验收](evidence/procedural-particles-20261027-r1/kit-r1/verification.json) |
| 文档及交付 | 三语63功能/21服务/17模块/76能力、C45与参数表；保留241条历史R行和38项原关闭条件。 | [最终审计](evidence/procedural-particles-20261027-r1/final-delivery-r1/verification.json) |

最大实际GPU预乘颜色/alpha误差：`GPU_ERROR`（阈值3e-6）。该数值限于本轮设备与小画幅案例；不代表所有显卡均已验收。
GPU只处理本功能的覆盖、光晕和有序透明合成；hash/运动/分块、颜色转换及编码沿各自CPU/原生编码路径执行。

## 原输入、实际输出及复现

[完整使用流程与逐字段单位](../product/PROCEDURAL_PARTICLES.md) · [C45完整案例](../product/CASES.md#c45-procedural-particles) · [离线安装信息](../releases/CLI_0.1.35_LOCAL.md)。

![原始纯色背景，添加编号标签](../assets/procedural-particles-20261027-r2/before.png)

![实际安装版GPU输出抽帧，添加编号标签](../assets/procedural-particles-20261027-r2/contact.png)

![实际输出的带标签GIF](../assets/procedural-particles-20261027-r2/particle-grid.gif)

[实际MP4](../assets/procedural-particles-20261027-r2/particle-grid.mp4) · [可编辑工程包](../assets/procedural-particles-20261027-r2/editable-particle-grid.aevpkg.zip) · [六套完整配方](../assets/procedural-particles-20261027-r2/recipes.json) · [来源/授权](../assets/procedural-particles-20261027-r2/SOURCE.txt) · [媒体摘要与GIF时钟](../assets/procedural-particles-20261027-r2/media-manifest.json)。

脚本 `scripts/run_particle_case_20261027.py` 通过C盘发现目录的统一Skill调用E盘离线安装版，真实生成、导出、重导入和逐帧解码。
原始MP4没有后贴编号；PNG/GIF解码实际MP4后加英文标签。GIF时长受格式粒度影响，与4秒MP4分别记录。
生成像素/标签为CC0-1.0，原创数值配方与代码MIT；没有第三方素材、模型、音乐或字体文件再分发。
抽帧静态检查见[目检记录](evidence/procedural-particles-20261027-r1/static-review-r1.json)；没有完成真人连续播放/听音或自然素材主观质量验收。

## 失败记录与修复

初始单元测试使用了错误的错误信封字段；初始集成同时暴露产品OTIO未保留背景色和队列夹具未指定MKV。
三个文件读取测试及实际注册Skill均复现了str.open错误，首安装候选因此未被接纳为最终交付。
随后增加1MiB有界UTF-8 JSON读取与结构化错误，并将config/source-signals内容加入幂等指纹；同路径内容变化会拒绝旧键。
所有红记录和首候选本地ZIP保留，未用成功结果覆盖。
[失败目录及最终对应](evidence/procedural-particles-20261027-r1/development-attempts-r1/verification.json)。

## 保留边界

这是二维独立粒子源，尚无3D、碰撞、深度遮挡、流体、发射器参数关键帧、AI语义特效或完整复合效果包。
支持普通片段TRS/opacity关键帧、遮罩、剪辑时钟及原生合成；旧FFmpeg图明确拒绝该生成源，不能静默省略。
本地OTIO往返保留Agent元数据；第三方OTIO播放器不保证可执行。嵌套/多序列完整图使用工程包。
CPU/GPU缓存预算是工作缓冲与准入边界，不是进程RSS或全局空闲显存预留；跨厂商/高分辨率自然样例仍待验收。

最终应用ZIP SHA256：`ARCHIVE_SHA`；安装manifest：`MANIFEST_SHA`。
'''
    text=text.replace('GPU_ERROR',str(r['particle_cpu_max_error'])).replace('ARCHIVE_SHA',install['archive_sha256']).replace('MANIFEST_SHA',install['manifest_sha256'])
    text=text.replace('/case-r2/','/case-r3/').replace('/procedural-particles-20261027-r2/','/procedural-particles-20261027-r3/')
    text+='\nC45实际注册入口墙钟：原始GPU渲染 '+str(round(render_seconds['render'],3))+' 秒，迁移后渲染 '+str(round(render_seconds['render-restored'],3))+' 秒；包含启动、进程通信、合成与编码。未做本案例同源CPU计时，不宣称GPU加速比或实时性能。\n'
    text+='\n后续演示还复现了工程外相对输出路径被拒绝；脚本和使用说明已改为工程内绝对路径。另一次激活在前一清单刷新完成前启动，被完整性检查拒绝；顺序重跑activation-final-r3通过，原stderr保留。\n'
    (ROOT/'docs/validation/可编辑粒子实测_2026-10-27.md').write_text(text,encoding='utf8',newline='\n')
    print(json.dumps({'status':'recorded','groups':groups,'rejected_attempts':len(records)},ensure_ascii=False))

if __name__=='__main__':main()
