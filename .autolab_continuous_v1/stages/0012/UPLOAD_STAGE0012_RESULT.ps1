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
$Log=Join-Path $DevRoot "logs\AUTOLAB_UPLOAD_STAGE0012.log"

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
function Find-ExactSendButton($p,$composer){
    try{
        $ctx=Get-FirefoxRootV11 $p
        $all=$ctx.Root.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants,
            [System.Windows.Automation.Condition]::TrueCondition
        )
        $cr=$composer.Current.BoundingRectangle
        $cand=@()
        for($i=0;$i -lt $all.Count;$i++){
            $e=$all.Item($i)
            try{
                if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::Button){continue}
                if(-not $e.Current.IsEnabled){continue}
                $name=([string]$e.Current.Name).Trim()
                if($name -match 'Créer une image|Creer une image|image|micro|voix|dictée|dictee|outils|tools'){continue}
                $r=$e.Current.BoundingRectangle
                if($r.Width -lt 22 -or $r.Width -gt 70 -or $r.Height -lt 22 -or $r.Height -gt 70){continue}
                $cx=$r.Left+$r.Width/2
                $cy=$r.Top+$r.Height/2
                if($cx -lt ($cr.Right-110)){continue}
                if($cy -lt ($cr.Top-15) -or $cy -gt ($cr.Bottom+45)){continue}
                $exact=0
                if($name -match '^(Envoyer|Send|Submit)$'){$exact=1000}
                $cand += [pscustomobject]@{E=$e;R=$r;Name=$name;Score=($exact+$cx)}
            }catch{}
        }
        if($cand.Count -eq 0){return $null}
        return $cand | Sort-Object Score -Descending | Select-Object -First 1
    }catch{
        return $null
    }
}
function Wait-ExactSendReady($p,$composer,[int]$seconds=180){
    $deadline=(Get-Date).AddSeconds($seconds)
    while((Get-Date)-lt $deadline){
        $x=Find-ExactSendButton $p $composer
        if($x){return $x}
        Start-Sleep -Milliseconds 350
    }
    return $null
}
function Wait-TokenProof($p,[string]$token,[int]$seconds=60){
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
                if($name -like "*$token*"){return $true}
            }
        }catch{}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

if(-not(Test-Path $FilePath)){Fail 71 "result ZIP absent"}
if(-not(Test-Path $Attach)){Fail 72 "V18 attach engine absent: $Attach"}
if(-not(Test-Path $Engine)){Fail 72 "post-attach UI engine absent: $Engine"}

. $Engine
Initialize-AutoLabUI
Remove-Item $MarkerPath -Force -ErrorAction SilentlyContinue

Log "[1/8] Attachement avec moteur V17 fige"
& py.exe -3 $Attach --file $FilePath
$rc=$LASTEXITCODE
if($rc -ne 0){Fail $rc "ATTACH_STAGE0007_V18.py echec"}

Start-Sleep 1
$baseName=[IO.Path]::GetFileName($FilePath)
$p=Get-FirefoxWindowV11
if(-not(Activate-FirefoxV11 $p)){Fail 75 "Firefox non activable"}

Log "[2/8] Preuve nom exact piece jointe"
$proof=Wait-AttachmentProof $p $baseName 60
if(-not $proof){Fail 77 "nom exact piece jointe non prouve"}

$ctx=Get-FirefoxRootV11 $p
$composer=Find-ComposerV11 $ctx.Root $ctx.Rect
if(-not $composer){Fail 78 "compositeur introuvable"}

Log "[3/8] Focus compositeur"
if(-not(Prove-ComposerFocusV11 $p $composer)){Fail 79 "focus compositeur non prouve"}

Start-Sleep 1
$sha=((Get-FileHash $FilePath -Algorithm SHA256).Hash).ToLowerInvariant()
$token="AUTOLAB0012-"+$sha.Substring(0,10)+"-"+(Get-Date -Format "HHmmss")
$fullMessage=$Message+" ["+$token+"]"

Log "[4/8] Saisie message"
[System.Windows.Forms.SendKeys]::SendWait("^a")
Start-Sleep -Milliseconds 100
Send-Literal $fullMessage

Log "[5/8] Recherche bouton Envoyer exact - exclusion explicite Creer une image"
$ready=Wait-ExactSendReady $p $composer 180
if(-not $ready){Fail 80 "bouton Envoyer exact non trouve"}

Start-Sleep 1
$sendX=[int]($ready.R.Left+$ready.R.Width/2)
$sendY=[int]($ready.R.Top+$ready.R.Height/2)
Log "      CIBLE name='$($ready.Name)' x=$sendX y=$sendY"

Log "[6/8] Clic physique UNIQUE Envoyer"
Mouse-ClickV11 $sendX $sendY 0

Log "[7/8] Preuve post-envoi par token dans la conversation"
if(-not(Wait-TokenProof $p $token 60)){
    Log "HOLD : token non prouve; aucun doublon automatique"
    exit 89
}

Log "[8/8] Marqueur upload confirme"
New-Item -ItemType Directory -Force -Path (Split-Path $MarkerPath -Parent)|Out-Null
@(
    "confirmed_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "file=$FilePath"
    "sha256=$sha"
    "token=$token"
    "engine=STAGE0012_EXACT_SEND_TOKEN_PROOF"
)|Set-Content $MarkerPath -Encoding UTF8

Log "UPLOAD_CONFIRMED STAGE0012"
exit 0
