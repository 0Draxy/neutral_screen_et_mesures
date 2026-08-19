$ErrorActionPreference = "Stop"
$devRoot="C:\dev_EA_MT5"
$target=Join-Path $devRoot "MT5_AutoLab_v0.15_LOCAL"
$source=$PSScriptRoot
$cal=Join-Path $devRoot "chatgpt_upload_ui.json"
$parent=Get-Content (Join-Path $source "PARENT_LOOP_V014.json") -Raw | ConvertFrom-Json
$rootLoop=Join-Path $devRoot "AUTOLOOP_V014_TO_V015_ID.txt"
$bridgeDir=Join-Path $devRoot "_AUTOLOOP_BRIDGE"
$bridge=Join-Path $bridgeDir "AUTOLOOP_UPLOAD.ps1"
$v014Uploader=Join-Path $devRoot "MT5_AutoLab_v0.14_LOCAL\AUTOLOOP_UPLOAD.ps1"

if(-not (Test-Path $cal)){throw "Calibration absente : $cal"}
if(Test-Path $rootLoop){
  $actual=(Get-Content $rootLoop -Raw).Trim().ToLowerInvariant()
  if($actual -ne ([string]$parent.parent_loop_id).ToLowerInvariant()){throw "Loop ID parent incoherent"}
}

New-Item -ItemType Directory -Force -Path $bridgeDir | Out-Null
if(Test-Path $v014Uploader){Copy-Item $v014Uploader $bridge -Force}
elseif(-not (Test-Path $bridge)){throw "Pont uploader v0.14 introuvable"}

$sf=[IO.Path]::GetFullPath($source).TrimEnd('\')
$tf=[IO.Path]::GetFullPath($target).TrimEnd('\')
if($sf -ne $tf){
  if(Test-Path $target){Remove-Item $target -Recurse -Force}
  Copy-Item $source $target -Recurse -Force
}

$configDir=Join-Path $devRoot "config"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
Copy-Item (Join-Path $target "autolab_v015_local_config.json") (Join-Path $configDir "autolab_v015_local_config.json") -Force

Write-Host "============================================================"
Write-Host " MT5 AUTOLAB v0.15 LOCAL"
Write-Host "============================================================"
Write-Host "Loop ID : $($parent.parent_loop_id)"
Write-Host "Resultat v0.15 -> ChatGPT -> STOP"
& py.exe -3 (Join-Path $target "autolab_v015_local.py")
exit $LASTEXITCODE
