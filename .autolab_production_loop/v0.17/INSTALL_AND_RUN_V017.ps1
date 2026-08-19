$ErrorActionPreference="Stop"
$devRoot="C:\dev_EA_MT5"
$target=Join-Path $devRoot "MT5_AutoLab_v0.17_LOCAL"
$source=$PSScriptRoot
$cal=Join-Path $devRoot "chatgpt_upload_ui.json"
if(-not (Test-Path $cal)){throw "Calibration absente : $cal"}

$sourceFull=[IO.Path]::GetFullPath($source).TrimEnd('\')
$targetFull=[IO.Path]::GetFullPath($target).TrimEnd('\')
if($sourceFull -ne $targetFull){
    if(Test-Path $target){Remove-Item $target -Recurse -Force}
    Copy-Item $source $target -Recurse -Force
}

# Reassemble the verified Python source chunks.
$parts=Get-ChildItem (Join-Path $target "src\autolab_v017_local.part*.txt") | Sort-Object Name
if($parts.Count -lt 1){throw "Chunks source v0.17 absents"}
$joined=""
foreach($part in $parts){$joined += [IO.File]::ReadAllText($part.FullName)}
$main17=Join-Path $target "autolab_v017_local.py"
$utf8=New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($main17,$joined,$utf8)

& py.exe -3 -m py_compile $main17
if($LASTEXITCODE -ne 0){throw "Syntaxe autolab_v017_local.py invalide apres assemblage"}

# Reuse the already validated infrastructure engine from v0.16.
$parentEngine=Join-Path $devRoot "MT5_AutoLab_v0.16_LOCAL\autolab_engine_v016.py"
if(-not (Test-Path $parentEngine)){throw "Moteur parent v0.16 absent : $parentEngine"}

$expected="83af75cb9af647b1451015ea2e6f8ca4b5dcb3fb45d42a487e0fdc5d6b95a7eb"
$actual=(Get-FileHash $parentEngine -Algorithm SHA256).Hash.ToLowerInvariant()
if($actual -ne $expected){throw "SHA256 moteur parent v0.16 incorrect"}

# Generate v0.17 engine directly in PowerShell.
# Do NOT use py.exe -c here: Windows argument parsing can strip Python quotes.
$engine17=Join-Path $target "autolab_engine_v017.py"
$engineText=[IO.File]::ReadAllText($parentEngine)
$engineText=$engineText.Replace("v0.16","v0.17").Replace("V016","V017").Replace("v016","v017")
[IO.File]::WriteAllText($engine17,$engineText,$utf8)

if(-not (Test-Path $engine17)){throw "Generation moteur v0.17 echouee"}
& py.exe -3 -m py_compile $engine17
if($LASTEXITCODE -ne 0){throw "Syntaxe autolab_engine_v017.py invalide"}

$configDir=Join-Path $devRoot "config"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
Copy-Item (Join-Path $target "autolab_v017_local_config.json") (Join-Path $configDir "autolab_v017_local_config.json") -Force

Write-Host "============================================================"
Write-Host " MT5 AUTOLAB v0.17 LOCAL - AUTOLOOP FINAL ROUND"
Write-Host "============================================================"
Write-Host "Moteur parent v0.16 SHA256 verifie."
Write-Host "Moteur v0.17 genere sans py.exe -c et syntaxe verifiee."
Write-Host "Holdout 2025-2026 FERME"
Write-Host "Apres resultat v0.17 : STOP"

& py.exe -3 (Join-Path $target "autolab_v017_local.py")
exit $LASTEXITCODE
