"""Write motion acceptance facts from completed logs and actual media bytes."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/motion-pack-20261025-r1'
PUBLIC=ROOT/'docs/assets/motion-pack-20261025-r1'


def load(name):return json.loads((BASE/name).read_bytes())
def link(name,label='证据'):return '['+label+'](evidence/motion-pack-20261025-r1/'+name+')'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    install=load('installation-r2/verification.json');assert install['status']=='installed-and-byte-verified'
    for phase in ('setup-continue-r1','render-r1','reuse-r1','skill-r2','kit-r2'):
        assert load(phase+'/verification.json')['status']=='passed',phase
    source=PUBLIC/'SOURCE.txt'
    source.write_text('Self-authored vector card and motion recipes by agent editor kit contributors, MIT.\n'
        'Illustration/recipes reproduction: scripts/run_motion_pack_case_20261025.py\n'
        'Font rasterized in examples: bundled Noto Sans SC variable, SIL Open Font License; '
        'the separate font/license/source remain in the installed material catalog.\n'
        'No client or third-party photograph, private footage, GUI screenshot or generated voice is included.\n',encoding='utf8',newline='\n')
    files=[]
    for path in sorted(PUBLIC.iterdir()):
        if not path.is_file() or path.name=='media-manifest.json':continue
        row=dict(path=path.relative_to(ROOT).as_posix(),bytes=path.stat().st_size,sha256=sha(path))
        if path.suffix in ('.png','.gif'):
            with Image.open(path) as image:
                row.update(width=image.width,height=image.height,frames=getattr(image,'n_frames',1))
                if path.suffix=='.gif':
                    duration=0
                    for n in range(image.n_frames):image.seek(n);duration+=image.info.get('duration',0)
                    row['duration_ms']=duration;assert image.n_frames==40 and duration==4000
        if path.suffix=='.mp4':
            facts=load('render-r1/'+path.stem+'-public-decoded.json')
            assert facts['sha256']==row['sha256'] and facts['frame_count']==120 and facts['frame_rate']=='30/1'
            row.update(width=facts['width'],height=facts['height'],frames=facts['frame_count'],fps=facts['frame_rate'],duration=facts['duration'])
        files.append(row)
    manifest=dict(format='agent-editor-motion-preview-v1',cli_version='0.1.16',source_sha256=sha(PUBLIC/'original.png'),
        source_license='MIT; rasterized OFL font',native_windows=True,virtualization=False,gui_screenshot=False,
        automatic_full_decode=True,static_contact_sheet_inspected=True,continuous_playback=False,human_listening=False,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),files=files)
    (PUBLIC/'media-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    text='''# 可复用运镜包实测（2026-10-25）

CLI **0.1.16 / alpha.4-local.14 / r16 kit** 最终候选 r2 已固定安装，唯一入口 `$agent-ffmpeg-local-editor`，17 内部模块。新增两个产品模块：纯声明配方验证/编译与 CLI。六套参数路径、已有动画完整作者曲线捕获、明确冲突/替换、普通可编辑关键帧、快照/事务/幂等和预算/取消已实现。

这是 G04 的子项交付；自然素材运镜美学、主体跟随组合和 CPU 旋转性能仍开放。全部 G01–G38 原关闭条件保持，完整目标继续进行。

[完整使用流程与六套参数](../product/MOTION_PACKS.md) · [实施前契约](../specs/可复用运镜包契约_20261025.md) · [案例 C25](../product/CASES.md#c25-motion-packs)

## 固定安装和范围

'''
    text+=f"ZIP `{install['archive_bytes']}` bytes，SHA-256 `{install['archive_sha256']}`；manifest `{install['manifest_sha256']}`。208 个产品 Python 文件与源码逐字节一致。"+link('installation-r2/verification.json')+'。\n\n'
    text+='| 范围 | 方法通过/总数 | 证据 |\n|---|---:|---|\n'
    for run,count in (('development-r3',22),('native-development-r3',5),('installed-contracts-r2',22),('installed-native-r2',5),('installed-cli-r2',122)):
        value=load('tests/'+run+'/verification.json')
        assert value['status']=='passed' and value['result']==dict(methods=count,skipped=0,failures=0,errors=0,success=True)
        text+=f'| {run} | {count}/{count}，0 skip | '+link('tests/'+run+'/verification.json')+' |\n'
    text+='''
这些是分别执行的范围，不相加为累计通过数或完成率；历史完整大套件没有重跑。22 项契约覆盖非法 JSON/重复键、参数/点数/有理时间、属性别名冲突、完整作者曲线/Bezier、窗口偏移、源速度字段保持、锁定、dry-run、幂等、取消/预算及模拟写后回滚。最终两项还验证捕获/查询明确拒绝工程幂等键、不写任何工程文件，以及缩放负增量/最终范围。纯数值曲线比较不是画面验证；下列五项才执行真实原生图像链路。

## 独立原生像素

1. 160×90 / 24fps 的红色参考点绕行：实际像素质心与独立解析椭圆逐帧比较，容差 2.1 像素。
2. S 路径在 1 秒拆为两段 presentation-window：拆前/拆后全部原生 RGBA 字节相同。
3. 父序列非线性速度 .5→1.5 并倒放：独立积分反演求子作者时间，逐帧质心符合原轨迹，未把父播放进度误当源/作者时间。
4. 捕获弧形运动后换为两倍画幅和两倍时长：相同归一化时刻的质心一致，容差 1.5 像素。
5. 六套路径分别原生完整解码，48 帧均有可见参考点，输出序列摘要彼此不同。

'''
    text+=link('tests/installed-native-r2/tests.log','最终安装版原始日志')+'；开发版与安装版五项分别执行。\n\n'
    text+='''## 实际案例、速度与有限采样

使用本仓库自制 FIELD NOTES 图卡和已有 OFL 字体，不使用用户私有母图发布新案例。原图与六套 JSON/MP4/GIF/中点静帧均保留；编译的参数、内容 SHA、原始包 SHA 和完整 recipe 留在工程 provenance，运镜结果是普通 keyframes。

'''
    rendered=load('render-r1/verification.json');calls=load('render-r1/calls.json')
    text+='| 实际渲染 | CLI 墙钟秒 | 输出 |\n|---|---:|---|\n'
    for call in calls:
        if call['name'] in ('original','orbit_focus','arc_push','bezier_sweep','whip_settle','breathe_float','detail_scan','native-nvenc'):
            text+=f"| {call['name']} | {call['elapsed_seconds']:.3f} | 4 秒 / 120 帧；"+link('render-r1/'+call['name']+'-decoded.json')+' |\n'
    text+='\n'+link('render-r1/verification.json','完整渲染事实')+' · [原输入与全部媒体摘要](../assets/motion-pack-20261025-r1/media-manifest.json)。\n\n'
    text+=f"六套公开 MP4 均 640×360 / 30fps / 4 秒 / 120 帧、无声；GIF 为 480×270 / 10fps / 40 帧 / 4 秒。实际完整解码后制作联系表并目检。曲线是 65 点折线：绕行默认半径在 640×360 的独立中点采样误差最大 `{rendered['orbit_midpoint_sample_error_pixels_at_640x360']:.9f}` 像素；这只描述该默认路径，不推广为所有参数/分辨率误差保证。\n\n"
    text+='''变换合成仍在 CPU，NVENC 只用于实际产品硬件编码和六条公开预览编码。带旋转的 detail_scan 四秒样例约 65 秒；其他样例约 4–9 秒。墙钟包含 CLI 启动/检查，与本轮 CLI 回归有并行负载，不是独占基准或 GPU/CPU 加速比；这一性能问题保留在 G32。未做连续播放、人类美学验收、自然素材或主体跟随验收。

## 捕获、原工程不可用与真实注册 Skill

从弧形推进捕获完整作者曲线，写成绝对值无参数包，再应用到新序列。dry-run 不改变 project.json；移走捕获 JSON 后渲染，全部 120 帧与原弧形输出相同。导出/导入包的完整 project.json 和资产字节相同；移走原工程及六个外部配方后，再在导入工程渲染，120 帧仍相同。外部公开配方核验后恢复原位；原工程保留在案例独有的不可用目录，未移动共享安装。

'''
    reuse=load('reuse-r1/verification.json')
    text+=f"可编辑包 `{reuse['package_bytes']}` bytes，SHA-256 `{reuse['package_sha256']}`；本地 `workspace/motion-pack-20261025-installed-r1/editable-motion.aevpkg.zip`。"+link('reuse-r1/verification.json')+'。\n\n'
    text+='真实 C 盘发现联接仍指向 E 盘单一 Skill，启动最终固定 0.1.16 r2 安装版；再次执行目录、dry-run、正式 apply、无损 render 和 validate，120 帧与 r1 基准相同。'+link('skill-r2/verification.json','最终真实 Skill 证据')+'。未启动模型或虚拟化环境。\n\n'
    kit=load('kit-r2/verification.json')
    text+=f"r16 kit 在独立中文/空格目录展开配置并登记，{kit['process_calls']} 次进程调用通过，{kit['skill_files']} 个 Skill 文件/1 入口/17 模块；真实发现目录没有更改。"+link('kit-r2/verification.json')+'。r1 候选/r15 kit 和其首次通过记录保留；六条公开预览来自 r1 的实际默认包，r2 默认包字节和渲染实现不变，最终五项原生及实际 Skill 重新执行，未伪造新媒体。\n\n'
    text+='''## 保留的失败和边界

首轮 20 项契约中 6 项失败：新测试夹具漏掉工程必须的 source_in_tick/source_out_tick，产品正确拒绝 PROJECT_INVALID。补齐夹具后同范围 20/20。第一轮原生 discovery 又包含导入的七个 CLI 方法，12/12 原日志保留；修正测试导入方式后，真实原生范围独立为 5/5，不把重复方法加进新计数。

'''
    text+=link('tests/development-r1/verification.json','首轮夹具失败')+' · '+link('tests/native-development-r1/verification.json','旧重复 discovery')+'。\n\n'
    text+='首次案例脚本向 sequence.canvas 传了不支持的 background，组合命令原子拒绝 SEQUENCE_CANVAS_INVALID；脚本改用已支持的 width/height 后继续，原失败响应保留：'+link('setup-r1/compose-gallery.stdout','原始响应')+' · '+link('setup-continue-r1/verification.json','继续后结果')+'。产品未通过放宽 canvas 契约绕过失败。\n\n'
    text+='''已有动画默认冲突，--replace 会替换整条所涉属性轨；局部范围之外使用新端点值，不承诺局部无损拼接。捕获完整作者曲线，不把被裁切隐藏的作者时段丢掉，也不猜测参数来源。时间舍入碰撞、锁定轨道、跟踪绑定及被跟踪源明确拒绝。creator/license 是声明，不是自动授权核验。脚本/配方不执行表达式，外部媒体/模型不下载。

19 个语义实现模块及模型推理未改变，因此本轮没有重复 CPU/CUDA 80 查询或新增模型质量结论；原错误、此前真实证据和所有 G01–G38 原关闭条件保留。公开 alpha.3 旧标签/附件不覆盖；本轮是本地加载和 main 代码更新，非新公开 Release。
'''
    (ROOT/'docs/validation/可复用运镜包实测_2026-10-25.md').write_text(text,encoding='utf8',newline='\n')
    name=ROOT/'docs/product/CASES.md';text=name.read_text('utf8')
    if 'id="c25-motion-packs"' in text:
        print(json.dumps(dict(status='written',media_files=len(files),public_mp4=6,public_gif=6,source_preserved=True)))
        return
    text+='''
<a id="c25-motion-packs"></a>

## C25：可复用参数运镜、完整作者曲线与实际预览

自制 FIELD NOTES 图卡 → 六套版本化 JSON → 明确参数 → 普通可编辑关键帧 → 真实无损渲染/MP4/GIF → 动画捕获/新序列复用 → 工程包迁移 → 注册 Skill 再现。

[完整参数/命令和逐项 MP4/GIF/JSON](MOTION_PACKS.md) · [原图](../assets/motion-pack-20261025-r1/original.png) · [来源](../assets/motion-pack-20261025-r1/SOURCE.txt) · [媒体摘要/帧率/时长](../assets/motion-pack-20261025-r1/media-manifest.json) · [全部实测、失败及性能边界](../validation/可复用运镜包实测_2026-10-25.md)。

![实际弧形推进 / 无声](../assets/motion-pack-20261025-r1/arc_push.gif)

六条 MP4 各为 4 秒/30fps/120 帧；六条 GIF 各 4 秒/10fps/40 帧。原生裁切前后字节相同，非线性嵌套倒放的独立几何 oracle 通过；换时长/画幅可复用。捕获外部包和原工程不可用后，导入工程及真实注册 Skill 的 120 帧分别与原结果相同。

本地编辑包 `workspace/motion-pack-20261025-installed-r1/editable-motion.aevpkg.zip`，项目在同目录 `导入工程/`。已做程序完整解码与联系表静帧目检，未做连续播放/人工美学验收。65 点空间折线、CPU 变换、约 65 秒的四秒旋转样例和跟踪组合边界明确保留；这是 G04 子项，不是完整目标验收。
'''
    name.write_text(text,encoding='utf8',newline='\n')
    print(json.dumps(dict(status='written',media_files=len(files),public_mp4=6,public_gif=6,source_preserved=True)))


if __name__=='__main__':main()
