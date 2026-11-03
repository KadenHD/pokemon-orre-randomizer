param(
    [string]$Iso = (Join-Path $PSScriptRoot '..\build\roundtrip\colosseum-pal-roundtrip.iso'),
    [string]$UserDirectory = (Join-Path $PSScriptRoot '..\build\roundtrip\dolphin-user'),
    [string]$DolphinExecutable = (Join-Path $PSScriptRoot '..\build\dolphin-validation\portable\Dolphin.exe'),
    [string]$Report = '',
    [string[]]$ProtectFile = @(),
    [switch]$Debugger
)

$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$launcher = Join-Path $projectRoot 'scripts\run_dolphin_validation.py'
$python = (Get-Command python.exe -ErrorAction Stop).Source
if (-not $Report) {
    $reportDirectory = Join-Path $projectRoot 'build\dolphin-validation'
    New-Item -ItemType Directory -Path $reportDirectory -Force | Out-Null
    $Report = Join-Path $reportDirectory ('run-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff') + '.json')
}
$arguments = @('-X', 'utf8', $launcher, '--emulator', $DolphinExecutable,
               '--iso', $Iso, '--profile', $UserDirectory, '--report', $Report)
foreach ($protected in $ProtectFile) {
    $arguments += @('--protect-file', $protected)
}
if ($Debugger) {
    $arguments += '--debugger'
}
# The Python monitor launches an argv list without a shell, records the native
# PID/return code, audits originals, and never terminates or restores Dolphin.
# Its own status is distinct from the recorded native return_code in the JSON.
& $python @arguments
exit $LASTEXITCODE
