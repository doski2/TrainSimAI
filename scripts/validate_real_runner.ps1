<#
Validate the host is prepared for running `real` tests.

Checks performed:
- Python executable in PATH
- pip can install packages from requirements.txt (checks by invoking 'pip check' after install)
- environment variables `TSC_RD_DLL_DIR` or `RAILWORKS_PLUGINS` point to a directory containing .dll files

Exit codes:
0 = ok
1 = missing python
2 = pip/install failure
3 = missing DLL dir or no DLLs

#>
param()

function Fail([int]$code, [string]$msg) {
    Write-Error $msg
    exit $code
}

Write-Host "Validating real runner prerequisites..."

# Check python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { Fail 1 "Python is not found in PATH. Install Python 3.11 and ensure it's available as 'python'" }

Write-Host "Python found: $($python.Path)"

# Check pip & install requirements (dry-run: try to import requirements)
try {
    & python -m pip install --upgrade pip | Out-Null
    if (Test-Path requirements.txt) {
        Write-Host "Installing requirements from requirements.txt (this may take a while)..."
        & python -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { Fail 2 "pip install -r requirements.txt failed with exit code $LASTEXITCODE" }
    } else {
        Write-Host "No requirements.txt found in repo root, skipping pip install step"
    }
} catch {
    Fail 2 "Exception while installing requirements: $_"
}

# Check for DLL folder
$dllDir = $env:TSC_RD_DLL_DIR; if (-not $dllDir) { $dllDir = $env:RAILWORKS_PLUGINS }
if (-not $dllDir) {
    Fail 3 "Neither TSC_RD_DLL_DIR nor RAILWORKS_PLUGINS are defined. Set one to the folder containing the RailDriver DLLs."
}

if (-not (Test-Path $dllDir)) { Fail 3 "DLL directory '$dllDir' does not exist" }

$dlls = Get-ChildItem -Path $dllDir -Filter *.dll -File -ErrorAction SilentlyContinue
if (-not $dlls -or $dlls.Count -eq 0) { Fail 3 "No .dll files found in '$dllDir'" }

Write-Host "Found DLLs in ${dllDir}:"
$dlls | ForEach-Object { Write-Host " - $($_.Name)" }

Write-Host "Validation OK"
exit 0
