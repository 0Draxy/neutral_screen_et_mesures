$ErrorActionPreference="Stop"
$devRoot="C:\dev_EA_MT5"
$candidates=@(
  (Join-Path $devRoot "MT5_AutoLab_v0.23.1_METAL_EXECUTION"),
  (Join-Path $devRoot "AUTOLAB_CONTINUOUS_LOOP_v1\MT5_AutoLab_v0.23.1_LOOPTEST")
)
$target=$null
foreach($p in $candidates){
  if(Test-Path (Join-Path $p "autolab_v0231.py")){$target=$p;break}
}
if(-not $target){throw "Stage 0001 v0.23.1 introuvable"}

$main=Join-Path $target "autolab_v0231.py"
$engine=Join-Path $target "autolab_engine_v0231.py"
$candidate=Join-Path $target "FROZEN_METAL_COMPRESSION_V022.mq5"
$protocol=Join-Path $target "EXECUTION_PROTOCOL_FROZEN_V0231.json"

$expectedCandidate="42f05f911e6364464a1518b1d295774720091469f62baa9079289a4d9553117f"
$expectedProtocol="0b28f969f4d2e03f81d45273241a07732e3312c5736f30714aee043c7f9e8e8c"

function Sha([string]$p){(Get-FileHash $p -Algorithm SHA256).Hash.ToLowerInvariant()}
if((Sha $candidate) -ne $expectedCandidate){throw "Candidate SHA mismatch avant hotfix"}
if((Sha $protocol) -ne $expectedProtocol){throw "Protocol SHA mismatch avant hotfix"}

$txt=Get-Content $main -Raw -Encoding UTF8
$before=$txt

# Bug 1: accidental double suffix created by stage-0001 text replacement.
$txt=$txt.Replace(
  "import autolab_engine_v02311 as b",
  "import autolab_engine_v0231 as b"
)

# Bug 2: frozen candidate remains v0.23 byte-for-byte and therefore writes V023 CSV names.
$txt=$txt.Replace(
  'for pre in ("AUTOLAB_V0231_SIGNALS_","AUTOLAB_V0231_TRADES_"):',
  'for pre in ("AUTOLAB_V023_SIGNALS_","AUTOLAB_V023_TRADES_"):'
)
$txt=$txt.Replace(
  'p=COMMON/(f"AUTOLAB_V0231_{k}_{sym}.csv")',
  'p=COMMON/(f"AUTOLAB_V023_{k}_{sym}.csv")'
)

# Identify the current automatic return as stage 0002.
$txt=$txt.Replace(
  "AUTOLAB CONTINUOUS V1 STAGE 0001 / v0.23.1 LOOPTEST",
  "AUTOLAB CONTINUOUS V1 STAGE 0002 / v0.23.1 LOOPTEST HOTFIX"
)

if($txt -eq $before){throw "Aucune correction stage 0002 appliquee"}
if($txt -match "autolab_engine_v02311"){throw "Import double suffix encore present"}
if($txt -notmatch 'AUTOLAB_V023_SIGNALS_'){throw "Prefix signaux V023 non corrige"}
if($txt -notmatch 'AUTOLAB_V023_TRADES_'){throw "Prefix trades V023 non corrige"}

Copy-Item $main ($main+".bak_stage0002") -Force
Set-Content -Path $main -Value $txt -Encoding UTF8

# Scientific freeze must remain untouched.
if((Sha $candidate) -ne $expectedCandidate){throw "Candidate modifie par hotfix"}
if((Sha $protocol) -ne $expectedProtocol){throw "Protocol modifie par hotfix"}

& py.exe -3 -m py_compile $engine
if($LASTEXITCODE -ne 0){throw "Engine Python invalide"}
& py.exe -3 -m py_compile $main
if($LASTEXITCODE -ne 0){throw "Main Python invalide"}

Write-Host "============================================================"
Write-Host " AUTOLAB CONTINUOUS V1 - STAGE 0002"
Write-Host "============================================================"
Write-Host "Hotfix technique uniquement:"
Write-Host "- import engine corrige"
Write-Host "- CSV Common V023 alignes avec candidat gele"
Write-Host "- broker GOLD/SILVER conserve"
Write-Host "- candidate/protocol SHA inchanges"
Write-Host "- looptest reprend automatiquement"

& py.exe -3 $main
exit $LASTEXITCODE
