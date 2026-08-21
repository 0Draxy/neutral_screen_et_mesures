param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][string]$Message,
    [Parameter(Mandatory=$true)][string]$MarkerPath
)

$ErrorActionPreference="Stop"

$DevRoot="C:\dev_EA_MT5"
$Guard=Join-Path $DevRoot "AUTOLAB_CONTINUOUS_GUARD_v3_0"
$Attach=Join-Path $Guard "ATTACH_STAGE0007_V18.py"
$Engine=Join-Path $Guard "FILE_UI_ENGINE_POST_ATTACH.ps1"
$Log=Join-Path $DevRoot "logs\AUTOLAB_UPLOAD_STAGE0010.log"

function Log([string]$s){
    $line="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $s"
    Write-Host $line
    Add-Content $Log $line -Encoding UTF8
}
function Fail([int]$code,[string]$message){
    Log "ERREUR rc=$code : $message"
    exit $code
}
function Send-Literal([string]$Text){
    $map=@{
        "+"="{+}"; "^"="{^}"; "%"="{%}"; "~"="{~}"
        "("="{(}"; ")"="{)}"; "{"="{{}"; "}"="{}}"
        "["="{[}"; "]"="{]}"
    }
    $sb=New-Object System.Text.StringBuilder
    foreach($ch in $Text.ToCharArray()){
        $s=[string]$ch
        if($map.ContainsKey($s)){[void]$sb.Append($map[$s])}
        else{[void]$sb.Append($s)}
    }
    [System.Windows.Forms.SendKeys]::SendWait($sb.ToString())
}
function Wait-AttachmentProof($p,[string]$baseName,[int]$seconds=60){
    $deadline=(Get-Date).AddSeconds($seconds)
    while((Get-Date)-lt $deadline){
        try{
            $ctx=Get-FirefoxRootV11 $p
            $all=$ctx.Root.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                [System.Windows.Automation.Condition]::TrueCondition
            )
            for($i=0;$i -lt $all.Count;$i++){
                $name=[string]$all.Item($i).Current.Name
                if($name -like "*$baseName*"){return "UIA_FILENAME"}
            }
        }catch{}
        Start-Sleep -Milliseconds 350
    }
    return $null
}

if(-not(Test-Path $FilePath)){Fail 71 "result ZIP absent"}
if(-not(Test-Path $Attach)){Fail 72 "V18 attach engine absent: $Attach"}
if(-not(Test-Path $Engine)){Fail 72 "post-attach UI engine absent: $Engine"}

. $Engine
Initialize-AutoLabUI

Remove-Item $MarkerPath -Force -ErrorAction SilentlyContinue

Log "[1/7] Attachement avec moteur V17 fige"
& py.exe -3 $Attach --file $FilePath
$rc=$LASTEXITCODE
if($rc -ne 0){Fail $rc "ATTACH_STAGE0007_V18.py echec"}

Start-Sleep 1

$baseName=[IO.Path]::GetFileName($FilePath)
$p=Get-FirefoxWindowV11
if(-not(Activate-FirefoxV11 $p)){Fail 75 "Firefox non activable"}

Log "[2/7] Preuve nom exact piece jointe"
$proof=Wait-AttachmentProof $p $baseName 60
if(-not $proof){Fail 77 "nom exact piece jointe non prouve"}
Log "      attachment=$proof"

$ctx=Get-FirefoxRootV11 $p
$composer=Find-ComposerV11 $ctx.Root $ctx.Rect
if(-not $composer){Fail 78 "compositeur introuvable"}

Log "[3/7] Focus compositeur"
if(-not(Prove-ComposerFocusV11 $p $composer)){Fail 79 "focus compositeur non prouve"}

Start-Sleep 1

$sha=((Get-FileHash $FilePath -Algorithm SHA256).Hash).ToLowerInvariant()
$token="AUTOLAB0010-"+$sha.Substring(0,10)+"-"+(Get-Date -Format "HHmmss")
$fullMessage=$Message+" ["+$token+"]"

Log "[4/7] Saisie message"
[System.Windows.Forms.SendKeys]::SendWait("^a")
Start-Sleep -Milliseconds 100
Send-Literal $fullMessage

Log "[5/7] Attente Envoyer actif"
$ready=Wait-SendReadyV11 $p 180
if(-not $ready){Fail 80 "bouton Envoyer non actif"}

Start-Sleep 1

Log "[6/7] Clic physique UNIQUE Envoyer"
$sendX=[int]($ready.R.Left+$ready.R.Width/2)
$sendY=[int]($ready.R.Top+$ready.R.Height/2)
Log "      SOURIS -> Envoyer ($sendX,$sendY)"
Mouse-ClickV11 $sendX $sendY 0

Log "[7/7] Verification post-envoi"
$deadline=(Get-Date).AddSeconds(40)
$stable=0
while((Get-Date)-lt $deadline){
    Start-Sleep -Milliseconds 500
    $s=Find-SendButtonV11 $p
    if(-not $s -or -not $s.E.Current.IsEnabled){$stable++}else{$stable=0}
    if($stable -ge 3){break}
}

if($stable -lt 3){
    Log "HOLD : envoi possiblement parti; aucun doublon automatique"
    exit 89
}

New-Item -ItemType Directory -Force -Path (Split-Path $MarkerPath -Parent)|Out-Null
@(
    "confirmed_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "file=$FilePath"
    "sha256=$sha"
    "token=$token"
    "engine=V18_V17_FROZEN_GENERIC_STAGE0010"
)|Set-Content $MarkerPath -Encoding UTF8

Log "UPLOAD_CONFIRMED STAGE0010"
exit 0
