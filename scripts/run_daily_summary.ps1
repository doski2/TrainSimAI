param(
  [string]$RepoPath = $(Split-Path -Parent $MyInvocation.MyCommand.Path)
)
$repo = Resolve-Path (Join-Path $RepoPath '..')
Push-Location $repo
try {
  python scripts/generate_daily_summary.py
} finally {
  Pop-Location
}

