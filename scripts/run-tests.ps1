param([string]$Mode = 'not-real')

function Run-NotReal {
    Write-Host 'Running tests excluding "real" (default)'
    # Use the Python runner to ensure helper and pytest run in the same process
    python .\scripts\run_pytests.py --mode not-real
}

function Run-Real {
    Write-Host 'Running tests marked "real" - ensure RailDriver DLL and env vars are configured'
    python -m pytest -q -m real
}

function Run-All {
    Write-Host 'Running all tests (may include hardware-dependent tests)'
    python -m pytest -q
}

switch ($Mode) {
    'all' { Run-All }
    'real' { Run-Real }
    default { Run-NotReal }
}
