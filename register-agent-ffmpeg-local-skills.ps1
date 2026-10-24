param(
    [string]$SkillsDirectory = $(if ($env:CODEX_HOME) {
        Join-Path $env:CODEX_HOME 'skills'
    } else {
        Join-Path $env:USERPROFILE '.codex\skills'
    }),
    [string]$ReceiptPath = ''
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'scripts/register_unified_skill.ps1') -SkillsDirectory $SkillsDirectory -ReceiptPath $ReceiptPath
