# 实际跨机器CPU基线媒体

原始视频由FFmpeg testsrc2生成，320×180／30fps／2秒；独立音频由440Hz sine生成，48kHz双声道Float32 WAV／每声道96000样本。没有客户照片、人物、第三方音乐或模型输出。

primary.mp4为本机正式CLI0.1.63实际输出；second-host.mp4为第二台原生Windows经未改r58统一Skill实际导入同一工程包后渲染的输出。两者包含t3-kodak-gold-200，global，strength=0.65。原MP4未重新编码；完整60帧RGBA与完整解码PCM摘要一致。

comparison.gif由build_preview.py读取两份实际输出，以10fps并排展示并添加说明；comparison.png是同批首帧。GIF不包含音频，不能代替完整播放或听审；未给出自然质量、GPU、干净主机或CLI66验收结论。AAC完整解码每声道96256样本，包含尾部256样本，详见metadata.json。

重建GIF须传入本机实际ffmpeg.exe及可选已有Pillow目录；在新的输出目录操作，避免覆盖摘要记录。系统字体仅用于输出说明，没有分发字体文件。

[完整实际流程与证据](../../product/CROSS_MACHINE63_BASELINE.md) · [媒体摘要及元数据](metadata.json)
