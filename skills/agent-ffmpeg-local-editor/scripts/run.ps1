$ErrorActionPreference = 'Stop'
# Resolve the Skill junction itself so the same script works through Codex or E:.
$skillDirectory = Split-Path -Parent $PSScriptRoot
$skillItem = Get-Item -LiteralPath $skillDirectory -Force
if ($skillItem.LinkType -eq 'Junction') {
    $skillDirectory = [IO.Path]::GetFullPath([string]$skillItem.Target)
}
$projectDirectory = Split-Path -Parent (Split-Path -Parent $skillDirectory)
$configPath = Join-Path $projectDirectory 'local/agent-ffmpeg/runtime.json'
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    throw "Local release is not installed. Follow the alpha.3 quickstart to install the pinned runtime in $projectDirectory"
}
$runtimeConfig = Get-Content -LiteralPath $configPath -Raw -Encoding utf8 | ConvertFrom-Json
& $runtimeConfig.python '-I' '-S' '-B' '-X' 'utf8' (Join-Path $PSScriptRoot 'run.py') $configPath @args
exit $LASTEXITCODE
