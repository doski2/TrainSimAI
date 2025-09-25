<#
Normalize EOL to LF for Python files and perform git renormalize.
Usage: run in repository root from PowerShell
#>
Get-ChildItem -Recurse -Include *.py | ForEach-Object {
    $path = $_.FullName
    $content = Get-Content -Raw -Encoding UTF8 $path
    $new = $content -replace "`r`n", "`n"
    if ($new -ne $content) {
        Write-Output "Normalizing: $path"
        [System.IO.File]::WriteAllText($path, $new, [System.Text.Encoding]::UTF8)
    }
}

git add --renormalize .
Write-Output "Run: git commit -m 'chore: normalize EOL to LF' -a  (if changes present) and then push"
