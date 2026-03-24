param(
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root 'venv\Scripts\python.exe'
$launcher = Join-Path $root 'start.py'

if (-not (Test-Path $launcher)) {
    throw "런처 파일을 찾을 수 없습니다: $launcher"
}

if (-not (Test-Path $python)) {
    throw "가상환경 Python을 찾을 수 없습니다: $python"
}

$arguments = @($launcher)
if ($Check) {
    $arguments += '--check'
}

& $python @arguments
exit $LASTEXITCODE
