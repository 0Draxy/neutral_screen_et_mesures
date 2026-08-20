param([string]$CurrentFolder="AUTOLAB_STAGE_0007_DISCOVERY_RESEARCH")
$ErrorActionPreference="Continue"
$B="C:\dev_EA_MT5"
$archive=Join-Path $B "archive\autolab_handoffs"
$log=Join-Path $B "logs\AUTOLAB_CLEANUP_STAGE0007.log"
New-Item -ItemType Directory -Force -Path $archive | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

function L([string]$s){Add-Content -Path $log -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $s" -Encoding UTF8}
function SafeRemove([string]$p){
  if(-not(Test-Path $p)){return}
  try{Remove-Item $p -Recurse -Force -ErrorAction Stop;L "DELETE OK $p"}
  catch{L "DELETE BLOCKED $p :: $($_.Exception.Message)"}
}
function SafeMove([string]$p,[string]$dest){
  if(-not(Test-Path $p)){return}
  try{
    $target=Join-Path $dest (Split-Path $p -Leaf)
    if(Test-Path $target){Remove-Item $target -Force -ErrorAction SilentlyContinue}
    Move-Item $p $target -Force -ErrorAction Stop;L "ARCHIVE OK $p -> $target"
  }catch{L "ARCHIVE BLOCKED $p :: $($_.Exception.Message)"}
}

L "START conservative cleanup"
Get-ChildItem (Join-Path $B "reports") -File -ErrorAction SilentlyContinue |
  Where-Object {$_.Name -match '^AUTOLAB_A_ENVOYER_CHATGPT_' -and $_.Name -notmatch 'STAGE0006|STAGE0007'} |
  ForEach-Object {SafeMove $_.FullName $archive}

$obsoleteTop=@(
  "AUTOLAB_CONTINUOUS_GUARD_v2",
  "AUTOLAB_CONTINUOUS_LOOP_v1",
  "MT5_AutoLab_v0.23_METAL_EXECUTION",
  "MT5_AutoLab_v0.23.1_METAL_EXECUTION",
  "MT5_AutoLab_v0.23.1_LOOPTEST",
  "AUTOLAB_STAGE_0002_HOTFIX",
  "AUTOLAB_STAGE_0003_STRUCTURAL",
  "AUTOLAB_STAGE_0004_CROSS_SECTIONAL",
  "AUTOLAB_STAGE_0005_PAIR_RELATIVE_VALUE"
)
foreach($n in $obsoleteTop){SafeRemove (Join-Path $B $n)}

foreach($p in @(
  "autolab\v0.23",
  "autolab\continuous_stage_0003",
  "autolab\continuous_stage_0004",
  "autolab\continuous_stage_0005",
  "experiments\v0.23",
  "experiments\continuous_stage_0003",
  "experiments\continuous_stage_0004",
  "experiments\continuous_stage_0005"
)){SafeRemove (Join-Path $B $p)}

foreach($dirName in @("reports","logs","config")){
  $d=Join-Path $B $dirName
  if(Test-Path $d){
    Get-ChildItem $d -File -ErrorAction SilentlyContinue |
      Where-Object {$_.Name -match 'STAGE0003|STAGE0004|STAGE0005|V023(?!1)|v023(?!1)'} |
      ForEach-Object {SafeRemove $_.FullName}
  }
}

Get-ChildItem $B -Directory -Filter "__pycache__" -Recurse -ErrorAction SilentlyContinue |
  Where-Object {$_.FullName -notlike "*\archive\*"} | ForEach-Object {SafeRemove $_.FullName}
Get-ChildItem $B -File -Filter "*.pyc" -Recurse -ErrorAction SilentlyContinue |
  Where-Object {$_.FullName -notlike "*\archive\*"} | ForEach-Object {SafeRemove $_.FullName}

$mustKeep=@(
  (Join-Path $B "AUTOLAB_CONTINUOUS_GUARD_v2_1"),
  (Join-Path $B "_AUTOLAB_CONTINUOUS_V2"),
  (Join-Path $B "archive"),
  (Join-Path $B "data\v0.21.1"),
  (Join-Path $B "data\continuous_stage0006_discovery"),
  (Join-Path $B "chatgpt_upload_ui.json"),
  (Join-Path $B "HOLDOUT_2025_2026_CONSUMED.txt")
)
foreach($p in $mustKeep){if(Test-Path $p){L "PRESERVE OK $p"} else {L "PRESERVE ABSENT $p"}}
L "END cleanup"
exit 0
