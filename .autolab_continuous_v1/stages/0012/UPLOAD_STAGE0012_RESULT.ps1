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

function Normalize-UiText([string]$s){
    if($null -eq $s){return ""}
    return ($s.Trim().ToLowerInvariant())
}

function Get-SendCandidatesInComposerZone($p,$composer,[switch]$VerboseLog){
    $ctx=Get-FirefoxRootV11 $p
    $all=$ctx.Root.FindAll(
        [System.Windows.Automation.TreeScope]::Descendants,
        [System.Windows.Automation.Condition]::TrueCondition
    )

    $cr=$composer.Current.BoundingRectangle
    $zoneLeft=[double]($cr.Right-150)
    $zoneRight=[double]($cr.Right+10)
    $zoneTop=[double]($cr.Top-20)
    $zoneBottom=[double]($cr.Bottom+55)

    $cand=@()
    $seen=@()

    for($i=0;$i -lt $all.Count;$i++){
        $e=$all.Item($i)
        try{
            if($e.Current.ControlType -ne [System.Windows.Automation.ControlType]::Button){continue}
            $r=$e.Current.BoundingRectangle
            if($r.Width -le 0 -or $r.Height -le 0){continue}

            $cx=$r.Left+$r.Width/2
            $cy=$r.Top+$r.Height/2
            if($cx -lt $zoneLeft -or $cx -gt $zoneRight){continue}
            if($cy -lt $zoneTop -or $cy -gt $zoneBottom){continue}

            $name=([string]$e.Current.Name).Trim()
            $norm=Normalize-UiText $name

            $seen += [pscustomobject]@{
                Name=$name
                Enabled=[bool]$e.Current.IsEnabled
                X=[int]$cx
                Y=[int]$cy
                W=[int]$r.Width
                H=[int]$r.Height
            }

            if($norm -notin @("envoyer","send","submit")){continue}
            if(-not $e.Current.IsEnabled){continue}
            if($r.Width -lt 22 -or $r.Width -gt 80){continue}
            if($r.Height -lt 22 -or $r.Height -gt 80){continue}

            $cand += [pscustomobject]@{
                E=$e
                R=$r
                Name=$name
                X=[int]$cx
                Y=[int]$cy
            }
        }catch{}
    }

    if($VerboseLog){
        foreach($s in $seen){
            Log ("      ZONE BTN name='{0}' enabled={1} x={2} y={3} w={4} h={5}" -f `
                $s.Name,$s.Enabled,$s.X,$s.Y,$s.W,$s.H)
        }
    }

    return @($cand)
}

function Wait-ExactSendByTextInZone($p,$composer,[int]$seconds=180){
    $deadline=(Get-Date).AddSeconds($seconds)
    $lastDiag=(Get-Date).AddSeconds(-999)
    while((Get-Date)-lt $deadline){
        try{
            $diag=((Get-Date)-$lastDiag).TotalSeconds -ge 5
            $cand=Get-SendCandidatesInComposerZone $p $composer -VerboseLog:$diag
            if($diag){$lastDiag=Get-Date}

            if($cand.Count -eq 1){return $cand[0]}
            if($cand.Count -gt 1){
                Log "HOLD : plusieurs boutons Envoyer exacts dans la zone; aucun clic"
                return $null
            }
        }catch{}
        Start-Sleep -Milliseconds 350
    }
    return $null
}

function Revalidate-SendTarget($p,$composer,$previous){
    $cand=Get-SendCandidatesInComposerZone $p $composer
    if($cand.Count -ne 1){return $null}
    $x=$cand[0]
    if((Normalize-UiText $x.Name) -notin @("envoyer","send","submit")){return $null}
    return $x
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

Log "[1/9] Attachement avec moteur V17 fige"
& py.exe -3 $Attach --file $FilePath
$rc=$LASTEXITCODE
if($rc -ne 0){Fail $rc "ATTACH_STAGE0007_V18.py echec"}

Start-Sleep 1
$baseName=[IO.Path]::GetFileName($FilePath)
$p=Get-FirefoxWindowV11
if(-not(Activate-FirefoxV11 $p)){Fail 75 "Firefox non activable"}

Log "[2/9] Preuve nom exact piece jointe"
$proof=Wait-AttachmentProof $p $baseName 60
if(-not $proof){Fail 77 "nom exact piece jointe non prouve"}

$ctx=Get-FirefoxRootV11 $p
$composer=Find-ComposerV11 $ctx.Root $ctx.Rect
if(-not $composer){Fail 78 "compositeur introuvable"}

Log "[3/9] Focus compositeur"
if(-not(Prove-ComposerFocusV11 $p $composer)){Fail 79 "focus compositeur non prouve"}

Start-Sleep 1
$sha=((Get-FileHash $FilePath -Algorithm SHA256).Hash).ToLowerInvariant()
$token="AUTOLAB0012-"+$sha.Substring(0,10)+"-"+(Get-Date -Format "HHmmss")
$fullMessage=$Message+" ["+$token+"]"

Log "[4/9] Saisie message"
[System.Windows.Forms.SendKeys]::SendWait("^a")
Start-Sleep -Milliseconds 100
Send-Literal $fullMessage

Log "[5/9] RECONNAISSANCE TEXTE dans zone droite du compositeur"
Log "      cible autorisee = texte exact 'Envoyer' / 'Send' / 'Submit'"
Log "      aucun fallback par position; 'Creer une image' est impossible comme cible"
$ready=Wait-ExactSendByTextInZone $p $composer 180
if(-not $ready){Fail 80 "aucun unique bouton Envoyer exact reconnu dans la zone"}

Log ("      RECONNU name='{0}' x={1} y={2}" -f $ready.Name,$ready.X,$ready.Y)

Start-Sleep 1

Log "[6/9] Revalidation texte + zone juste avant clic"
$ready2=Revalidate-SendTarget $p $composer $ready
if(-not $ready2){Fail 86 "cible Envoyer perdue/ambigue avant clic"}

Log ("      REVALIDE name='{0}' x={1} y={2}" -f $ready2.Name,$ready2.X,$ready2.Y)

Log "[7/9] Deplacement souris physique vers cible reconnue + clic UNIQUE"
[System.Windows.Forms.Cursor]::Position=New-Object System.Drawing.Point($ready2.X,$ready2.Y)
Start-Sleep 1
Mouse-ClickV11 $ready2.X $ready2.Y 0

Log "[8/9] Preuve post-envoi par token dans la conversation"
if(-not(Wait-TokenProof $p $token 60)){
    Log "HOLD : token non prouve; aucun doublon automatique"
    exit 89
}

Log "[9/9] Marqueur upload confirme"
New-Item -ItemType Directory -Force -Path (Split-Path $MarkerPath -Parent)|Out-Null
@(
    "confirmed_at=$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "file=$FilePath"
    "sha256=$sha"
    "token=$token"
    "engine=TEXT_RECOGNITION_IN_COMPOSER_ZONE_V1"
)|Set-Content $MarkerPath -Encoding UTF8

Log "UPLOAD_CONFIRMED STAGE0012"
exit 0
