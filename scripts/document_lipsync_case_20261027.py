"""Publish C51 receipts, provenance, media index and trilingual case details."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
public=ROOT/'docs/assets/native-lipsync-20261027-r1'
def load(p):return json.loads(p.read_bytes())
def sha(p):
    with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def write(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
main=load(BASE/'case-r1/verification.json');moving=load(BASE/'video-and-cancel-r1/verification.json')
assert main['status']==moving['status']=='passed'
assert all(v['ok'] for v in main['checks']+moving['checks'])
manifest=public/'media-manifest.json';assert not manifest.exists()
write(manifest,dict(status='actual-installed-CUDA-case',cli_version='0.1.41',native_windows=True,virtualization=False,
    source_fallback=False,synthetic_protocol_worker=False,real_person_reference=False,
    master_frames=133,master_fps=25,master_duration_seconds=5.32,preview_frames=160,preview_fps=30,
    GIF_frames=133,GIF_duration_ms=5320,moving_frames=30,moving_fps=25,
    files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()],
    evidence=['../../validation/evidence/native-lipsync-20261027-r1/case-r1/verification.json','../../validation/evidence/native-lipsync-20261027-r1/video-and-cancel-r1/verification.json'],
    editable_package_scope='Initial portrait + full synthetic speech + neural output + linked clips + recipe. Moving-video companion is supplied separately.',
    natural_quality_accepted=False,continuous_human_playback=False,human_listening=False))
review=BASE/'static-portrait-review.json';assert not review.exists()
write(review,dict(status='reviewed',at_utc=datetime.now(timezone.utc).isoformat(),reviewer='Codex visual inspection of actual local images',
    files={n:sha(public/n) for n in ('frame-first.png','frame-middle.png','frame-last.png')},
    observations=['Visible open/closed mouth variation in sampled frames.','Face patch is softer than source, especially lower cheeks/mouth.','Hair, shirt, background and frame boundaries appear stable in sampled comparisons.'],
    scope='Three still comparisons only; complete pixel/PCM invariants are separately machine-checked.',
    continuous_human_playback=False,human_listening=False,perceptual_sync_accepted=False,natural_quality_accepted=False))
case_path=ROOT/'docs/product/CASES.md';text=case_path.read_text('utf8');assert 'id="c51-native-lip-sync"' not in text
text+='''
<a id="c51-native-lip-sync"></a>

## C51 · 本地神经口型 / 本機神經口型 / Native neural lip sync

实际注册的 CLI0.1.41/单入口 Skill，在 RTX3060 上执行 MuseTalk1.5、Whisper-tiny、SD VAE 与 BiSeNet。原图为本机 Wan2.1 VACE1.3B 生成的虚构成年人物，语音为 CUDA Kokoro 合成普通话，无真人参考。生成 **512×512、133帧/25FPS/5.32秒** RGBA母版；完整126795个原始Float32 PCM标量保留，仅尾部增加885个静音样本（36.875ms）。全部透明度、人脸框外及alpha0隐藏RGB保留。视频/音频为可独立编辑的关联片段，配方可更改种子或素材重跑。

本機實測亦包含30影格/1.2秒移動來源和人臉框關鍵影格。逐影格透明度及框外RGB完全保留。真正CUDA推理開始輸出影格後觸發取消：三個自有子程序全數退出、工程中繼資料回滾，無半成品資產或工作目錄，診斷保留。

Actual installed CUDA inference, not a synthetic worker. Full package reimport preserves every master byte and rerunnable recipe; complete rendered RGBA and decoded PCM match. The neural master/GIF use25FPS (133frames/5320ms). The ordinary project export uses its default30FPS (160frames/5.333333s), recorded separately. The editable package contains the initial portrait/speech result; moving-video source, key plan and result are separate companion files.

![All actual master frames, source versus neural output](../assets/native-lipsync-20261027-r1/comparison.gif)

[Playable speech MP4](../assets/native-lipsync-20261027-r1/spoken.mp4) · [Editable initial project + lossless master](../assets/native-lipsync-20261027-r1/editable-lipsync.aevpkg.zip) · [Original generated portrait](../assets/native-lipsync-20261027-r1/portrait-base.png) · [Diagnostic RGBA input](../assets/native-lipsync-20261027-r1/portrait.png) · [Complete synthetic speech](../assets/native-lipsync-20261027-r1/speech.wav) · [First](../assets/native-lipsync-20261027-r1/frame-first.png) · [Middle](../assets/native-lipsync-20261027-r1/frame-middle.png) · [Last](../assets/native-lipsync-20261027-r1/frame-last.png)

[Moving input](../assets/native-lipsync-20261027-r1/moving-source.mov) · [Moving box keys](../assets/native-lipsync-20261027-r1/moving-boxes.json) · [Moving output MP4](../assets/native-lipsync-20261027-r1/moving-spoken.mp4) · [Source/provenance](../assets/native-lipsync-20261027-r1/SOURCE.txt) · [All media hashes](../assets/native-lipsync-20261027-r1/media-manifest.json) · [Workflow and dependencies](LIP_SYNC.md) · [Detailed evidence](../validation/本地神经口型实测_2026-10-27.md).

First/middle/last stills visibly vary the mouth; generated lower-face detail is softer than the source. No continuous human playback, listening, naturalness, perceptual synchronization, identity/occlusion, full-body performance, HDR inference or complete digital-human/product acceptance is claimed. Source, voice, model and generated-asset rights remain separate. The model's trained face raster is256×256; explicit boxes require shot review.
'''
case_path.write_text(text,encoding='utf8',newline='\n')
evidence=ROOT/'docs/validation/本地神经口型实测_2026-10-27.md';assert not evidence.exists()
evidence.write_text('''# 本地神经口型实测 · 2026-10-27

CLI0.1.41 / alpha.4-local.39 / r42，原生Windows、RTX3060。本批未调用Docker/WSL/虚拟化、未创建虚拟环境、未安装全局依赖、没有源码回落。应用与模型Python分别固定；模型推理不联网。

[28项安装版检查](evidence/native-lipsync-20261027-r1/installed-lipsync-r1/verification.json) · [28项源码检查](evidence/native-lipsync-20261027-r1/source-lipsync-r3/verification.json) · [177项既有服务源码兼容](evidence/native-lipsync-20261027-r1/source-service-compat-r1/verification.json) · [离线安装/248文件同字节](evidence/native-lipsync-20261027-r1/installation-final-r1/verification.json).

两组28项是同一套测试在不同执行上下文运行，不累计成56个独立测试。177项为既有服务的源码兼容检查；此前993项HDR安装回归保留为独立历史记录。本批所有上述最终运行均零失败、错误、跳过，执行前后产品和测试文件哈希一致。数值、配方、部分管道读取、保护像素、真实FFmpeg流、事务回滚与取消/超时均覆盖。协议夹具仅测试传输，不作为模型可用证据。

实际模型案例：[固定图像与完整语音](evidence/native-lipsync-20261027-r1/case-r1/verification.json)、[移动视频与真实取消](evidence/native-lipsync-20261027-r1/video-and-cancel-r1/verification.json)、[独立CUDA探针](evidence/native-lipsync-20261027-r1/model-probe-r2/verification.json)。无伪推理worker。实际Whisper音频特征、MuseTalk UNet、VAE编码/解码、BiSeNet语义解析均留forward计数。主案例133帧，UNet67批，峰值Torch分配2802346496字节；GPU准入是瞬时采样，不保证峰值或资源独占。

虚构人物由本机VACE1.3B独立生成，无真人参考：[人物生成回执](evidence/native-lipsync-20261027-r1/portrait-source-r2/verification.json)。语音来自CUDA Kokoro zf_001：[语音回执](evidence/native-lipsync-20261027-r1/voice-probe-r1/verification.json)。口型母版512×512、25FPS、133帧、5.32秒，保留126795个24kHz单声道原始PCM标量；仅尾部885个样本补零。所有alpha、框外RGB与alpha0隐藏RGB逐帧全量核验。工程包保留母版/来源/配方；重新导入后完整渲染音画相同。30FPS项目MP4为160帧，25FPS母版GIF为133帧/5320ms，各自时钟独立记录。

移动视频30帧/25FPS，三个显式框关键帧，逐帧验证alpha及框外RGB。真实取消仅在神经worker输出非零帧进度后触发，CLI返回CANCELLED/8；自有decoder/worker/encoder三个进程均回收，项目元数据回滚，无半成品或受管工作目录，错误诊断保留。38秒是该次取消调用完整耗时，包含预检；不等于触发标记后的取消延迟。初始注册和源/模型哈希准入不计入pipeline timeout。

失败尝试继续留档：源码r1局部变量遮蔽哈希函数、r2测试未排除保留诊断而误判，最终r3修正；CUDA探针r1遇旧VAE注意力参数名，采用显式严格映射后r2通过；人物生成首轮保留了窗口上下文参数冲突，改为显式temporal-context none成功。主案例首轮展示脚本把30FPS导出按25FPS母版重塑而失败，[原报告](evidence/native-lipsync-20261027-r1/case-r1/verification.first-attempt.json)保留；续执行仅从已核验母版补齐GIF，未重新伪造推理或覆盖失败记录。MonaLisa下载失败未作为案例输入。

[来源与模型获取](evidence/native-lipsync-20261027-r1/acquisition-metadata.json) · [文件哈希](evidence/native-lipsync-20261027-r1/acquisition-files.json) · [weights_only转safetensors/逐张量回读](evidence/native-lipsync-20261027-r1/weight-conversion.json) · [三张实际静帧检查](evidence/native-lipsync-20261027-r1/static-portrait-review.json) · [r42独立工具包核验](evidence/native-lipsync-20261027-r1/kit-r1/verification.json).

生成下半脸较原图柔和，三张静帧只能确认抽查时刻的嘴形变化，不能代替连续播放、听审或感知同步。256×256训练脸部、显式框、8bit SDR、源身体动作、无CPU回退等边界见[使用手册](../product/LIP_SYNC.md)。完整身体/表演、多人物/遮挡、自动追踪、HDR模型及自然质量仍须建设，38条原始目标关闭条件全部保留。

[案例与全部MP4/GIF/原图/语音/可编辑包](../product/CASES.md#c51-native-lip-sync) · [本地安装包](../releases/CLI_0.1.41_LOCAL.md).
''',encoding='utf8',newline='\n')
print(json.dumps(dict(status='written',case='C51',master_frames=133,moving_frames=30,real_cancel=True,media_files=len(load(manifest)['files']))))
