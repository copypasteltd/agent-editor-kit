param(
    [string]$SkillsDirectory = $(if ($env:CODEX_HOME) {
        Join-Path $env:CODEX_HOME 'skills'
    } else {
        Join-Path $env:USERPROFILE '.codex\skills'
    }),
    [string]$ReceiptPath = ''
)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$manifestPath = Join-Path $projectRoot 'agent-ffmpeg-local-install-manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
if ($manifest.format -ne 'agent-ffmpeg-local-skills-v2' -or $manifest.registration_mode -ne 'single' -or
    $manifest.skill_count -ne 1 -or @($manifest.skills).Count -ne 1 -or
    $manifest.skills[0].name -ne 'agent-ffmpeg-local-editor') {
    throw 'Expected the reviewed single-entry Skill manifest'
}
$canonicalRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot 'skills')).TrimEnd('\') + '\'
$discoveryRoot = [IO.Path]::GetFullPath($SkillsDirectory).TrimEnd('\')
$entry = $manifest.skills[0]
$canonicalPath = Join-Path $canonicalRoot $entry.name
$canonicalBoundary = $canonicalPath.TrimEnd('\') + '\'
$registrationPath = Join-Path $discoveryRoot $entry.name
$runtimePath = Join-Path $projectRoot $manifest.runtime_config
if (-not (Test-Path -LiteralPath $runtimePath -PathType Leaf)) {
    throw 'Install the matching local release first using install.py --archive <runtime.zip>, or use the repository quickstart.'
}
$runtime = Get-Content -LiteralPath $runtimePath -Raw -Encoding utf8 | ConvertFrom-Json
function Get-Sha256([string]$Path) {
    # Use .NET in both Windows PowerShell 5.1 and PowerShell 7, including
    # native Python subprocesses without Utility's Get-FileHash function.
    $stream = [IO.File]::OpenRead($Path)
    $algorithm = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant()
    } finally {
        $algorithm.Dispose()
        $stream.Dispose()
    }
}
if ($runtime.release -ne $manifest.release -or $runtime.manifest_sha256 -ne $manifest.manifest_sha256) {
    throw 'Local runtime does not match this Skill namespace'
}
$installedReceipt = Get-Content -LiteralPath (Join-Path $runtime.installed_directory 'receipt.json') -Raw -Encoding utf8 | ConvertFrom-Json
if ($installedReceipt.manifest_sha256 -ne $manifest.manifest_sha256 -or
    (Get-Sha256 (Join-Path $runtime.installed_directory 'run.py')) -ne $runtime.launcher_sha256) {
    throw 'Installed runtime receipt or launcher changed; repair the pinned installation first'
}

function Assert-OwnedJunction([string]$Path, [string]$Target) {
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($item -and ($item.LinkType -ne 'Junction' -or
        [IO.Path]::GetFullPath([string]$item.Target).TrimEnd('\') -ne $Target.TrimEnd('\'))) {
        throw "Existing unrelated Skill is preserved: $Path"
    }
    return $item
}

# Validate the entire Skill and every migration target before any mutation.
$names = @{}
foreach ($file in $manifest.files) {
    if ($file.path -match '(^/|\\|:|(^|/)\.\.?(/|$))' -or $names.ContainsKey($file.path)) {
        throw "Invalid Skill inventory path: $($file.path)"
    }
    $names[$file.path] = $true
    $path = [IO.Path]::GetFullPath((Join-Path $projectRoot $file.path))
    if (-not $path.StartsWith($canonicalBoundary, [StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-Item -LiteralPath $path).Length -ne $file.bytes -or
        (Get-Sha256 $path) -ne $file.sha256) {
        throw "Skill inventory differs: $($file.path)"
    }
}
if (-not $names.ContainsKey('skills/agent-ffmpeg-local-editor/SKILL.md') -or
    @((Get-ChildItem -LiteralPath $canonicalPath -Filter SKILL.md -File -Recurse)).Count -ne 1 -or
    (Get-Sha256 (Join-Path $canonicalPath 'SKILL.md')) -ne $entry.skill_md_sha256) {
    throw 'The unified package must contain exactly one reviewed Skill entry'
}
$existingEntry = Assert-OwnedJunction $registrationPath $canonicalPath
$retire = @()
$retiredNames = @{}
foreach ($old in $manifest.retired_skills) {
    if ($old.name -notmatch '^agent-ffmpeg-local-[a-z0-9-]+$' -or $old.name -eq $entry.name -or
        $retiredNames.ContainsKey($old.name)) {
        throw "Invalid retired Skill name: $($old.name)"
    }
    $retiredNames[$old.name] = $true
    $oldCanonical = [IO.Path]::GetFullPath((Join-Path $canonicalRoot $old.name))
    $oldRegistration = [IO.Path]::GetFullPath((Join-Path $discoveryRoot $old.name))
    $item = Assert-OwnedJunction $oldRegistration $oldCanonical
    if ($item) {
        if ((Get-Sha256 (Join-Path $oldCanonical 'SKILL.md')) -ne $old.skill_md_sha256) {
            throw "Retired Skill was edited; preserve it and review migration: $($old.name)"
        }
        $retire += [pscustomobject]@{name=$old.name; path=$oldRegistration; target=$oldCanonical}
    }
}
if ([string]::IsNullOrWhiteSpace($ReceiptPath)) {
    $ReceiptPath = Join-Path $projectRoot ('local/agent-ffmpeg/registrations/' + [Guid]::NewGuid().ToString('N') + '.json')
}
$ReceiptPath = [IO.Path]::GetFullPath($ReceiptPath)
if (Test-Path -LiteralPath $ReceiptPath) { throw "Existing registration receipt is preserved: $ReceiptPath" }
$receiptParent = Split-Path -Parent $ReceiptPath
New-Item -ItemType Directory -Path $receiptParent -Force | Out-Null
New-Item -ItemType Directory -Path $discoveryRoot -Force | Out-Null
$created = $false
$removed = @()
try {
    if (-not $existingEntry) {
        New-Item -ItemType Junction -Path $registrationPath -Target $canonicalPath | Out-Null
        $created = $true
    }
    $null = Assert-OwnedJunction $registrationPath $canonicalPath
    if ((Get-Sha256 (Join-Path $registrationPath 'SKILL.md')) -ne $entry.skill_md_sha256) {
        throw 'Registered Skill is unreadable or changed'
    }
    foreach ($old in $retire) {
        $null = Assert-OwnedJunction $old.path $old.target
        # Windows Directory.Delete without recursion unlinks this verified
        # junction only. No traversal or deletion of canonical Skill contents.
        [IO.Directory]::Delete($old.path)
        $removed += $old
    }
    $receipt = [ordered]@{
        status='registered'; registration_mode='single'; registered_at_utc=[DateTime]::UtcNow.ToString('o')
        skill_count=1; module_count=$manifest.module_count; release=$runtime.release
        namespace_manifest_sha256=(Get-Sha256 $manifestPath)
        name=$entry.name; canonical_directory=$canonicalPath; registration_directory=$registrationPath
        discovery_directory=$discoveryRoot; runtime_directory=$runtime.installed_directory
        created_entry=$created; retired_junction_count=@($removed).Count; retired_junctions=@($removed)
        original_specialist_sources_preserved=$true
    }
    $json = ($receipt | ConvertTo-Json -Depth 20) + "`n"
    $stream = [IO.File]::Open($ReceiptPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    try {
        $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json)
        $stream.Write($bytes, 0, $bytes.Length)
    } finally { $stream.Dispose() }
} catch {
    foreach ($old in $removed) {
        if (-not (Get-Item -LiteralPath $old.path -Force -ErrorAction SilentlyContinue)) {
            New-Item -ItemType Junction -Path $old.path -Target $old.target | Out-Null
        }
    }
    if ($created) {
        $null = Assert-OwnedJunction $registrationPath $canonicalPath
        [IO.Directory]::Delete($registrationPath)
    }
    throw
}
Write-Output "Registered 1 Skill with $($manifest.module_count) internal modules: `$agent-ffmpeg-local-editor"
Write-Output "Retired this project's specialist junctions: $(@($removed).Count)"
Write-Output "Installed release: $($runtime.installed_directory)"
Write-Output "Registration receipt: $ReceiptPath"
