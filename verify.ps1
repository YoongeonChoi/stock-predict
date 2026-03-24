param(
    [switch]$SkipFrontend,
    [switch]$LiveApiSmoke
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root 'venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    throw "가상환경 Python을 찾을 수 없습니다: $python"
}

Write-Host '[verify] Backend compileall'
Push-Location (Join-Path $root 'backend')
& $python -m compileall app
if ($LASTEXITCODE -ne 0) {
    throw 'Backend compileall failed.'
}

Write-Host '[verify] Backend unittest'
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) {
    throw 'Backend unittest failed.'
}

if ($LiveApiSmoke) {
    Write-Host '[verify] Backend live API smoke'
    & $python scripts/live_api_smoke.py
    if ($LASTEXITCODE -ne 0) {
        throw 'Backend live API smoke failed.'
    }
}
Pop-Location

if (-not $SkipFrontend) {
    Write-Host '[verify] Frontend build'
    Push-Location (Join-Path $root 'frontend')
    npm run build
    if ($LASTEXITCODE -ne 0) {
        throw 'Frontend build failed.'
    }

    Write-Host '[verify] Frontend typecheck'
    npx tsc --noEmit
    if ($LASTEXITCODE -ne 0) {
        throw 'Frontend typecheck failed.'
    }
    Pop-Location
}

Write-Host '검증 완료'
