param(
    [switch]$SkipFrontend
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root 'venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    throw "가상환경 Python을 찾을 수 없습니다: $python"
}

Write-Host '[1/4] Backend compileall'
Push-Location (Join-Path $root 'backend')
& $python -m compileall app

Write-Host '[2/4] Backend unittest'
& $python -m unittest discover -s tests -v
Pop-Location

if (-not $SkipFrontend) {
    Write-Host '[3/4] Frontend build'
    Push-Location (Join-Path $root 'frontend')
    npm run build

    Write-Host '[4/4] Frontend typecheck'
    npx tsc --noEmit
    Pop-Location
}

Write-Host '검증 완료'
