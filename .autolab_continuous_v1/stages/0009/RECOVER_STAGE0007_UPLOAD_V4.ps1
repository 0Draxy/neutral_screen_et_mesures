$ErrorActionPreference="Stop"
$B="C:\dev_EA_MT5";$here=$PSScriptRoot
$guard=Join-Path $B "AUTOLAB_CONTINUOUS_GUARD_v2_1"
$target=Join-Path $guard "AUTOLOOP_UPLOAD_ROBUST.ps1"
$core=Join-Path $guard "AUTOLOOP_UPLOAD_CORE_V2.ps1"
$new=Join-Path $here "AUTOLOOP_UPLOAD_ROBUST_V4.ps1"
$log=Join-Path $B "logs\AUTOLAB_STAGE0009_RECOVERY.log"
$marker=Join-Path $B "autolab\continuous_stage_0009\UPLOAD_CONFIRMED.txt"
$z1=Join-Path $B "reports\AUTOLAB_A_ENVOYER_CHATGPT_STAGE0007_DISCOVERY.zip"
$z2=Join-Path $B "archive\autolab_handoffs\AUTOLAB_A_ENVOYER_CHATGPT_STAGE0007_DISCOVERY.zip"
function L([string]$s){$x="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $s";Write-Host $x;Add-Content $log $x -Encoding UTF8}
if(Test-Path $z1){$zip=$z1}elseif(Test-Path $z2){$zip=$z2}else{throw "ZIP STAGE0007 introuvable"}
if(-not(Test-Path $guard)){throw "Guard v2.1 absent"}
if(-not(Test-Path $core)){throw "Core uploader v2 absent"}
Copy-Item $new $target -Force
L "Uploader v4 installe dans Guard. ZIP 0007 conserve."
$msg="AUTOLAB CONTINUOUS V1 STAGE 0007 RESULT RECUPERE PAR STAGE 0009 : analyse le ZIP discovery. Si aucune vraie decision utilisateur n est necessaire, publie automatiquement STAGE 0010 dans .autolab_continuous_v1/stages/0010 avec MANIFEST.json puis READY.txt en dernier. La validation Stage0006 reste verrouillee sauf si un candidat discovery a ete fige par STAGE0007; aucun live."
for($n=1;$n -le 20;$n++){
 L "Upload v4 tentative $n"
 & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $target -FilePath $zip -Message $msg -MarkerPath $marker
 $rc=$LASTEXITCODE
 if($rc -eq 0 -and (Test-Path $marker)){L "UPLOAD CONFIRME";exit 0}
 L "Non confirme rc=$rc; retry dans 20 s"
 Start-Sleep -Seconds 20
}
L "20 tentatives sans confirmation. Sortie technique pour permettre recovery stage suivant."
exit 43
