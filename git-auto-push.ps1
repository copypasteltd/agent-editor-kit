[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $repoRoot

$branch = (git branch --show-current).Trim()
if ($branch -ne "main") {
    throw "Auto-push is only allowed on the main branch; current branch is '$branch'."
}

$expectedRemote = "git@github.com:copypasteltd/agent-editor-kit.git"
$remote = (git remote get-url origin 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $remote -or $remote.Trim() -cne $expectedRemote) {
    throw "Auto-push requires origin to be '$expectedRemote'."
}
$pushRemotes = @(git remote get-url --push --all origin 2>$null)
if ($LASTEXITCODE -ne 0 -or $pushRemotes.Count -ne 1 -or $pushRemotes[0].Trim() -cne $expectedRemote) {
    throw "Auto-push requires exactly one push destination: '$expectedRemote'."
}

$arguments = @("push", "origin", "main")
if ($Force) { $arguments += "--force" }
if ($DryRun) { $arguments += "--dry-run" }
& git @arguments
if ($LASTEXITCODE -ne 0) {
    throw "git push failed with exit code $LASTEXITCODE."
}

