<#
  RustDesk unattended install for Windows (FOD Guard central PC, office PC, etc.)

  Run in an *elevated* PowerShell:
    Set-ExecutionPolicy -Scope Process Bypass -Force
    .\install-rustdesk-windows.ps1 -Password 'Choose-A-Strong-One'

  Optional, if you run your own relay server (see self-host/):
    .\install-rustdesk-windows.ps1 -Password '...' -IdServer 'farm.example.in' -Key 'PUBLIC_KEY'

  What it does: downloads the latest 64-bit RustDesk from the official GitHub
  releases, installs it silently as a Windows service (starts with Windows,
  works on the login screen), sets a permanent password, optionally points it
  at your own server, and prints the RustDesk ID you connect to.
#>
param(
  [Parameter(Mandatory = $true)][string]$Password,
  [string]$IdServer = '',
  [string]$Key = ''
)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if (-not ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)) {
  throw 'Run this script from an elevated (Run as administrator) PowerShell.'
}
if ($Password.Length -lt 8) { throw 'Use a password of at least 8 characters.' }

$exe = 'C:\Program Files\RustDesk\rustdesk.exe'

if (-not (Test-Path $exe)) {
  Write-Host 'Looking up latest RustDesk release...'
  $rel = Invoke-RestMethod 'https://api.github.com/repos/rustdesk/rustdesk/releases/latest' `
           -Headers @{ 'User-Agent' = 'rustdesk-setup' }
  $asset = $rel.assets | Where-Object { $_.name -match '^rustdesk-.*-x86_64\.exe$' } | Select-Object -First 1
  if (-not $asset) { throw "No x86_64 .exe found in release $($rel.tag_name)" }

  $tmp = Join-Path $env:TEMP $asset.name
  Write-Host "Downloading $($asset.name) ($($rel.tag_name))..."
  Invoke-WebRequest $asset.browser_download_url -OutFile $tmp -UseBasicParsing

  Write-Host 'Installing silently...'
  Start-Process $tmp -ArgumentList '--silent-install' -Wait
  for ($i = 0; $i -lt 30 -and -not (Test-Path $exe); $i++) { Start-Sleep 2 }
  if (-not (Test-Path $exe)) { throw 'Install did not finish - run the downloaded exe manually.' }
  Start-Sleep 5
} else {
  Write-Host 'RustDesk already installed - configuring only.'
}

# Optional: own ID/relay server. The service reads its config from the
# LocalService profile; the tray app from the current user's profile.
if ($IdServer) {
  Stop-Service RustDesk -ErrorAction SilentlyContinue
  $toml = @"
rendezvous_server = '${IdServer}:21116'
nat_type = 1
serial = 0

[options]
custom-rendezvous-server = '$IdServer'
relay-server = '$IdServer'
key = '$Key'
"@
  $dirs = @(
    'C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config',
    (Join-Path $env:APPDATA 'RustDesk\config')
  )
  foreach ($d in $dirs) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
    Set-Content -Path (Join-Path $d 'RustDesk2.toml') -Value $toml -Encoding UTF8
  }
  Start-Service RustDesk
  Start-Sleep 3
}

& $exe --password $Password | Out-Null
Start-Sleep 2
$id = (& $exe --get-id | Out-String).Trim()

Write-Host ''
Write-Host '======================================='
Write-Host " RustDesk ID : $id"
Write-Host ' Password   : (the one you passed in)'
if ($IdServer) { Write-Host " ID server  : $IdServer" }
Write-Host '======================================='
Write-Host 'Connect from the RustDesk app on your phone/laptop using this ID.'
