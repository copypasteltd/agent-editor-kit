Set-Location 'E:/dev/sandbox/AI广告剪辑'
$hdrLauncher = 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
$hdrExample = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/hdr-usage-r1'
& $hdrLauncher convert import --input 'E:/dev/sandbox/AI广告剪辑/docs/assets/native-hdr-20261027-r3/editable-native-hdr.aevpkg.zip' --output $hdrExample
& $hdrLauncher validate --project $hdrExample
& $hdrLauncher preview frame --project $hdrExample --frame 24 --height 360
& $hdrLauncher preview range --project $hdrExample --start-frame 0 --end-frame 48 --height 360
& $hdrLauncher render --project $hdrExample --output "$hdrExample/renders/usage-pq.mkv" --container mkv --video-codec libx264 --crf 0 --pixel-format yuv444p10le --audio-codec pcm_f32le --hardware-encode off --projection-acceleration require --projection-device 0.0
