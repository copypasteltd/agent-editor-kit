param(
    [string]$SkillsDirectory = $(if ($env:CODEX_HOME) {
        Join-Path $env:CODEX_HOME 'skills'
    } else {
        Join-Path $env:USERPROFILE '.codex\skills'
    })
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$manifestPath = Join-Path $projectRoot 'agent-ffmpeg-local-install-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$canonicalRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'skills')).TrimEnd('\') + '\'
$discoveryRoot = [IO.Path]::GetFullPath($SkillsDirectory)
$runtimePath = Join-Path $projectRoot $manifest.runtime_config
if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) {
    throw 'Install the matching local release first. The downloaded Agent kit provides install.py --archive <runtime.zip>; repository users can follow the alpha.3 quickstart.'
}
$runtime = Get-Content -LiteralPath $runtimePath -Raw -Encoding utf8 | ConvertFrom-Json
if ($runtime.release -ne $manifest.release -or $runtime.manifest_sha256 -ne $manifest.manifest_sha256) {
    throw 'Local runtime does not match this Skill namespace'
}
# Complete conflict and digest checks before creating any discovery junction.
foreach ($skillEntry in $manifest.skills) {
    if ($skillEntry.name -notmatch '^agent-ffmpeg-local-[a-z0-9-]+$') {
        throw "Invalid local Skill name: $($skillEntry.name)"
    }
    $canonicalPath = [IO.Path]::GetFullPath((Join-Path $canonicalRoot $skillEntry.name))
    if (-not $canonicalPath.StartsWith($canonicalRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Skill target is outside the project: $canonicalPath"
    }
    $skillFile = Join-Path $canonicalPath 'SKILL.md'
    if (-not (Test-Path -LiteralPath $skillFile -PathType Leaf)) {
        throw "SKILL.md missing: $canonicalPath"
    }
    if ((Get-FileHash -LiteralPath $skillFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $skillEntry.skill_md_sha256) {
        throw "Skill digest differs from the reviewed namespace: $($skillEntry.name)"
    }
    $registrationPath = [IO.Path]::GetFullPath((Join-Path $discoveryRoot $skillEntry.name))
    $existing = Get-Item -LiteralPath $registrationPath -Force -ErrorAction SilentlyContinue
    if ($existing) {
        if ($existing.LinkType -ne 'Junction' -or [IO.Path]::GetFullPath([string]$existing.Target).TrimEnd('\') -ne $canonicalPath.TrimEnd('\')) {
            throw "Existing unrelated Skill is preserved: $registrationPath"
        }
    }
    $skillEntry.canonical_directory = $canonicalPath
    $skillEntry.registration_directory = $registrationPath
}
New-Item -ItemType Directory -Path $discoveryRoot -Force | Out-Null
foreach ($skillEntry in $manifest.skills) {
    if (-not (Get-Item -LiteralPath $skillEntry.registration_directory -Force -ErrorAction SilentlyContinue)) {
        New-Item -ItemType Junction -Path $skillEntry.registration_directory -Target $skillEntry.canonical_directory | Out-Null
    }
    $discoveredFile = Join-Path $skillEntry.registration_directory 'SKILL.md'
    if ((Get-FileHash -LiteralPath $discoveredFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $skillEntry.skill_md_sha256) {
        throw "Registered Skill is unreadable or changed: $($skillEntry.name)"
    }
    $skillEntry.registration_verified = $true
}
$manifest.status = 'registered'
$manifest.project_directory = $projectRoot
$manifest.codex_skills_directory = $discoveryRoot
$manifest | Add-Member -NotePropertyName registered_at_utc -NotePropertyValue ([DateTime]::UtcNow.ToString('o')) -Force
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 100) + "`n", [Text.UTF8Encoding]::new($false))
Write-Output "Registered $($manifest.skill_count) agent-ffmpeg-local Skills."
Write-Output "Installed release: $($runtime.installed_directory)"
Write-Output "Codex discovery: $discoveryRoot"
