param(
    [switch]$SkipFrontend,
    [switch]$LiveApiSmoke
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root 'venv\Scripts\python.exe'
$verify = Join-Path $root 'verify.py'

if (-not (Test-Path $python)) {
    throw "가상환경 Python을 찾을 수 없습니다: $python"
}

if (-not (Test-Path $verify)) {
    throw "검증 런처를 찾을 수 없습니다: $verify"
}

$arguments = @($verify)
if ($SkipFrontend) {
    $arguments += '--skip-frontend'
}
if ($LiveApiSmoke) {
    $arguments += '--live-api-smoke'
}

& $python @arguments
exit $LASTEXITCODE
