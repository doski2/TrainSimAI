param(
  [string]$OutDir = "./artifacts/incident-$(Get-Date -Format yyyyMMdd-HHmmss)"
)

# Create output dir
if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

Write-Host "Collecting artifacts to $OutDir"

# Copy known data artifacts
$files = @(
  "data/control_status.json",
  "data/rd_ack.json",
  "data/rd_send.log"
)
foreach ($f in $files) {
  if (Test-Path $f) { Copy-Item $f -Destination $OutDir -Force; Write-Host "Copied $f" } else { Write-Host "Missing: $f" }
}

# Copy logs if they exist
if (Test-Path "logs") { Copy-Item "logs\*" -Destination $OutDir -Recurse -Force; Write-Host "Copied logs/" }

# Git info
try {
  $git_sha = git rev-parse --short HEAD 2>$null
  if ($LASTEXITCODE -eq 0) { $git_sha | Out-File -FilePath (Join-Path $OutDir "git-rev.txt") }
} catch { }

# Env
Get-ChildItem env: | Out-File -FilePath (Join-Path $OutDir "env.txt")

# System info
Get-Process | Sort-Object -Property Id | Select-Object -First 20 | Out-File -FilePath (Join-Path $OutDir "processes.txt")

# Zip
$zip = "$OutDir.zip"
if (Test-Path $zip) { Remove-Item $zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($OutDir, $zip)
Write-Host "Created $zip"

Write-Host "Done. Artifacts in: $zip"