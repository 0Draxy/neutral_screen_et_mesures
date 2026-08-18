$ErrorActionPreference = "Stop"

$devRoot = "C:\dev_EA_MT5"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runtime = Join-Path $devRoot "_LOOPTEST_RUNTIME"
$runId = (Get-Content (Join-Path $runtime "run_id.txt") -Raw).Trim()
$log = Join-Path $runtime "V3.log"
$errorFile = Join-Path $runtime "ERROR_V3.txt"

function Log([string]$s) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $s"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

try {
    Log "[V3 1/5] Debut pseudo-routine"
    Start-Sleep -Seconds 2

    if($runId -ne "dee2052124c64d93a7f245ec58b48c8b") {
        throw "RUN_ID inattendu. Attendu=dee2052124c64d93a7f245ec58b48c8b Recu=$runId"
    }

    $out = Join-Path $here "V3_RETOUR_CONTENT"
    $zip = Join-Path $here "AUTOLAB_LOOPTEST_V3_RETOUR.zip"

    if(Test-Path $out){ Remove-Item $out -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $out | Out-Null

    Log "[V3 2/5] Generation faux resultats"
    @"
AUTOLAB LOOPTEST - V3 RETOUR
============================
RUN_ID=$runId
VERSION=V3
STATUS=V3_OK
PSEUDO_SCORE=303
PREVIOUS_SCORE=202
CHAIN_STATUS=COMPLETE
NEXT_EXPECTED=CLEANUP
"@ | Set-Content (Join-Path $out "RESULTAT_V3.txt") -Encoding UTF8

    [ordered]@{
        run_id = $runId
        version = "V3"
        status = "V3_OK"
        pseudo_score = 303
        previous_score = 202
        chain_status = "COMPLETE"
        next_expected = "CLEANUP"
    } | ConvertTo-Json | Set-Content (Join-Path $out "manifest.json") -Encoding UTF8

    Copy-Item $log (Join-Path $out "V3.log") -Force

    Log "[V3 3/5] Creation V3_RETOUR.zip"
    if(Test-Path $zip){ Remove-Item $zip -Force }
    Compress-Archive -Path (Join-Path $out "*") -DestinationPath $zip -Force

    if(-not (Test-Path $zip)){ throw "V3_RETOUR.zip non cree." }

    Log "[V3 4/5] Upload automatique vers ChatGPT"
    $uploader = Join-Path $devRoot "_LOOPTEST_BRIDGE\UPLOAD_TO_CHATGPT.ps1"
    & powershell -NoProfile -ExecutionPolicy Bypass -File $uploader `
        -FilePath $zip `
        -Message "AUTOLAB LOOPTEST : V3_RETOUR automatique. Valide la chaine complete puis nettoie GitHub."

    if($LASTEXITCODE -ne 0){ throw "Uploader V3 code=$LASTEXITCODE" }

    Log "[V3 5/5] V3 terminee OK"
    exit 0
}
catch {
    $_.Exception.ToString() | Set-Content $errorFile -Encoding UTF8
    Write-Host ""
    Write-Host "ERREUR V3 : $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Diagnostic : $errorFile"
    exit 1
}
