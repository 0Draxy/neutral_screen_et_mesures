$ErrorActionPreference = "Stop"

$devRoot = "C:\dev_EA_MT5"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtime = Join-Path $devRoot "_LOOPTEST_RUNTIME"
$runId = (Get-Content (Join-Path $runtime "run_id.txt") -Raw).Trim()
$log = Join-Path $runtime "V2.log"
$errorFile = Join-Path $runtime "ERROR_V2.txt"

function Log([string]$s) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $s"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

try {
    Log "[V2 1/5] Debut pseudo-routine"
    Start-Sleep -Seconds 2

    $out = Join-Path $here "V2_RETOUR_CONTENT"
    $zip = Join-Path $here "AUTOLAB_LOOPTEST_V2_RETOUR.zip"

    if(Test-Path $out){ Remove-Item $out -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $out | Out-Null

    Log "[V2 2/5] Generation faux resultats"
    @"
AUTOLAB LOOPTEST - V2 RETOUR
============================
RUN_ID=$runId
VERSION=V2
STATUS=V2_OK
PSEUDO_SCORE=202
PREVIOUS_SCORE=101
NEXT_EXPECTED=V3
"@ | Set-Content (Join-Path $out "RESULTAT_V2.txt") -Encoding UTF8

    [ordered]@{
        run_id = $runId
        version = "V2"
        status = "V2_OK"
        pseudo_score = 202
        previous_score = 101
        next_expected = "V3"
    } | ConvertTo-Json | Set-Content (Join-Path $out "manifest.json") -Encoding UTF8

    Copy-Item $log (Join-Path $out "V2.log") -Force

    Log "[V2 3/5] Creation V2_RETOUR.zip"
    if(Test-Path $zip){ Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force
    if(-not (Test-Path $zip)){ throw "V2_RETOUR.zip non cree." }

    Log "[V2 4/5] Upload automatique vers ChatGPT"
    $uploader = Join-Path $devRoot "_LOOPTEST_BRIDGE\UPLOAD_TO_CHATGPT.ps1"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $uploader `
        -FilePath $zip `
        -Message "AUTOLAB LOOPTEST : V2_RETOUR automatique. Pseudo-analyse V2 puis publie V3."

    if($LASTEXITCODE -ne 0){ throw "Uploader V2 code=$LASTEXITCODE" }

    Log "[V2 5/5] V2 terminee OK"
    exit 0
}
catch {
    $_.Exception.ToString() | Set-Content $errorFile -Encoding UTF8
    Write-Host ""
    Write-Host "ERREUR V2 : $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Diagnostic : $errorFile"
    exit 1
}
