param(
    [string]$LogDir = 'C:\Users\cease\OneDrive\문서\GitHub\user_tracking_AND_APP\logs'
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$out = Join-Path $LogDir 'appium_smoke.log'
$err = Join-Path $LogDir 'appium_smoke.err.log'
Remove-Item $out, $err -ErrorAction SilentlyContinue

$appiumCmd = (Get-Command appium.cmd -ErrorAction Stop).Source
$proc = Start-Process -FilePath $appiumCmd `
    -ArgumentList '--allow-insecure','uiautomator2:chromedriver_autodownload' `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -PassThru -WindowStyle Hidden

$listening = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 1000
    $tcp = Get-NetTCPConnection -LocalPort 4723 -ErrorAction SilentlyContinue
    if ($tcp) { $listening = $true; break }
    if ($proc.HasExited) { break }
}

if ($listening) {
    Write-Host "[OK] Appium listening on :4723 after ${i}s (pid=$($proc.Id))"
} else {
    Write-Host "[FAIL] :4723 not listening after ${i}s (pid=$($proc.Id), HasExited=$($proc.HasExited))"
}

if (-not $proc.HasExited) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}

Write-Host '----- smoke stdout tail -----'
if (Test-Path $out) { Get-Content $out -Tail 25 } else { Write-Host '<no stdout>' }
Write-Host '----- smoke stderr tail -----'
if (Test-Path $err) { Get-Content $err -Tail 25 } else { Write-Host '<no stderr>' }
