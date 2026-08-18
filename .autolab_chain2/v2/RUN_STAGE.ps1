$ErrorActionPreference = "Stop"

$devRoot = "C:\dev_EA_MT5"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $here "v2_return_content"
$outbox = Join-Path $devRoot "_CHAIN_OUTBOX"
$zip = Join-Path $outbox "AUTOLAB_CHAIN_V2_RETOUR.zip"
$msg = Join-Path $outbox "AUTOLAB_CHAIN_V2_RETOUR.message.txt"

New-Item -ItemType Directory -Force -Path $outbox | Out-Null
if(Test-Path $out){ Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null

@"
AUTOLAB CHAIN TEST - V2 RETOUR
ROUND=2
STATUS=V2_EXECUTED_OK
PREVIOUS_SCORE=11
SCORE=22
NEXT_EXPECTED=V3
INSTALL_ROOT=C:\dev_EA_MT5
Pseudo-analyse V1: OK
"@ | Set-Content -Path (Join-Path $out "V2_RESULT.txt") -Encoding UTF8

@"
{
  "round": 2,
  "status": "V2_EXECUTED_OK",
  "previous_score": 11,
  "score": 22,
  "expected_next": "V3",
  "install_root": "C:\\dev_EA_MT5"
}
"@ | Set-Content -Path (Join-Path $out "manifest.json") -Encoding UTF8

if(Test-Path $zip){ Remove-Item $zip -Force }
Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

"AUTOLAB CHAIN 2 TOURS : V2_RETOUR automatique. Fais la pseudo-analyse et publie V3 sur GitHub." |
  Set-Content -Path $msg -Encoding UTF8

Write-Host "V2_RETOUR depose dans OUTBOX : $zip"
