param(
 [Parameter(Mandatory=$true)][string]$FilePath,
 [Parameter(Mandatory=$true)][string]$Message,
 [Parameter(Mandatory=$true)][string]$MarkerPath
)
$ErrorActionPreference="Stop"
$B="C:\dev_EA_MT5"
$cfg=Join-Path $B "chatgpt_upload_ui.json"
$guard=Join-Path $B "AUTOLAB_CONTINUOUS_GUARD_v2_1"
$core=Join-Path $guard "AUTOLOOP_UPLOAD_CORE_V2.ps1"
$log=Join-Path $B "logs\AUTOLOOP_UPLOAD_V4.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent)|Out-Null
function L([string]$s){$x="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $s";Write-Host $x;Add-Content $log $x -Encoding UTF8}
if(-not(Test-Path $cfg)){throw "Calibration absente: $cfg"}
if(-not(Test-Path $core)){throw "Core uploader v2 absent: $core"}
if(-not(Test-Path $FilePath)){throw "ZIP absent: $FilePath"}

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class ALV4W {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
}
"@

function Click([int]$x,[int]$y){
 [ALV4W]::SetCursorPos($x,$y)|Out-Null
 Start-Sleep -Milliseconds 120
 [ALV4W]::mouse_event(2,0,0,0,[UIntPtr]::Zero)
 [ALV4W]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 300
}

function Firefox-Pids{
 return @(Get-Process firefox -ErrorAction SilentlyContinue|ForEach-Object {$_.Id})
}

function Firefox-ChatGPT{
 $all=@(Get-Process firefox -ErrorAction SilentlyContinue|Where-Object {$_.MainWindowHandle -ne 0})
 if(-not $all){throw "Firefox visible non trouve"}
 $p=$all|Where-Object {$_.MainWindowTitle -match '(?i)ChatGPT|OpenAI'}|Select-Object -First 1
 if(-not $p){$p=$all|Select-Object -First 1}
 [ALV4W]::ShowWindow($p.MainWindowHandle,3)|Out-Null
 Start-Sleep -Milliseconds 250
 [ALV4W]::SetForegroundWindow($p.MainWindowHandle)|Out-Null
 Start-Sleep -Milliseconds 700
 return $p
}

function Meta($e){
 try{
   return (([string]$e.Current.Name)+" "+([string]$e.Current.AutomationId)+" "+([string]$e.Current.HelpText)+" "+([string]$e.Current.LocalizedControlType))
 }catch{return ""}
}

function Find-Composer($p){
 $root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
 $wr=$root.Current.BoundingRectangle
 $minW=[Math]::Max(360.0,$wr.Width*.28)
 $best=$null;$score=-1e12

 # IMPORTANT: Firefox web content can be exposed by another firefox.exe PID.
 # Search descendants of the trusted Firefox top-level root and do NOT require p.Id.
 $all=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
 for($i=0;$i -lt $all.Count;$i++){
  try{
   $e=$all.Item($i)
   $r=$e.Current.BoundingRectangle
   if($r.Width -lt $minW -or $r.Height -lt 18 -or $r.Height -gt 360){continue}
   if($r.Top -lt ($wr.Top+$wr.Height*.48)){continue}
   if($r.Left -lt ($wr.Left-5) -or $r.Right -gt ($wr.Right+5)){continue}

   $ct=$e.Current.ControlType
   $meta=Meta $e
   $focusable=$e.Current.IsKeyboardFocusable
   $candidate=($ct -eq [System.Windows.Automation.ControlType]::Edit) -or
              ($ct -eq [System.Windows.Automation.ControlType]::Document) -or
              ($focusable -and $meta -match '(?i)message|prompt|composer|ask|question|chatgpt')
   if(-not $candidate){continue}

   $s=($r.Top-$wr.Top)*4 + $r.Width
   if($meta -match '(?i)message|send a message|envoyer un message|prompt|composer|ask|question'){$s+=1000000}
   if($ct -eq [System.Windows.Automation.ControlType]::Edit){$s+=200000}
   if($focusable){$s+=100000}
   if($s -gt $score){$best=[pscustomobject]@{E=$e;R=$r;Meta=$meta};$score=$s}
  }catch{}
 }
 return $best
}

function Find-Send($p,$c){
 $root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
 $cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Button)
 $els=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$cond)
 $best=$null;$score=-1e12
 for($i=0;$i -lt $els.Count;$i++){
  try{
   $e=$els.Item($i);$n=Meta $e;$r=$e.Current.BoundingRectangle
   if($n -notmatch '(?i)\bsend\b|envoyer'){continue}
   if($r.Top -lt ($c.R.Top-180) -or $r.Top -gt ($c.R.Bottom+180)){continue}
   $s=$r.Left
   if($n -match '(?i)\bsend\b|envoyer'){$s+=100000}
   if($s -gt $score){$best=$r;$score=$s}
  }catch{}
 }
 return $best
}

function Focus-Is-Safe($p,$c,[int]$cx,[int]$cy){
 $f=[System.Windows.Automation.AutomationElement]::FocusedElement
 if(-not $f){return $false}
 try{
   $fp=[int]$f.Current.ProcessId
   $firefox=@(Firefox-Pids)
   if($firefox -notcontains $fp){return $false}
   $fr=$f.Current.BoundingRectangle
   # Firefox may focus an inner contenteditable child with a tiny rectangle.
   # Accept if click point is in focused rect OR focused element is a descendant-ish
   # Firefox element whose rectangle lies inside the already-proved composer.
   $insideFocus=($cx -ge $fr.Left -and $cx -le $fr.Right -and $cy -ge $fr.Top -and $cy -le $fr.Bottom)
   $insideComposer=($fr.Left -ge ($c.R.Left-20) -and $fr.Right -le ($c.R.Right+20) -and
                    $fr.Top -ge ($c.R.Top-80) -and $fr.Bottom -le ($c.R.Bottom+80))
   $meta=Meta $f
   if($insideFocus){return $true}
   if($insideComposer -and ($f.Current.IsKeyboardFocusable -or $meta -match '(?i)message|prompt|composer|document|edit')){return $true}
 }catch{}
 return $false
}

$p=Firefox-ChatGPT
$c=Find-Composer $p
if(-not $c){L "ABORT: compositeur UIA introuvable sous racine Firefox; aucun texte saisi";exit 41}
L ("Compositeur candidat: "+$c.Meta+" rect="+$c.R.Left+","+$c.R.Top+","+$c.R.Width+","+$c.R.Height)

$cx=[int]($c.R.Left+[Math]::Min(120.0,[Math]::Max(50.0,$c.R.Width*.18)))
$cy=[int]($c.R.Top+$c.R.Height/2)
Click $cx $cy

if(-not(Focus-Is-Safe $p $c $cx $cy)){
 L "ABORT: focus post-clic non prouve comme descendant Firefox/compositeur; aucun texte saisi"
 exit 42
}

$j=Get-Content $cfg -Raw|ConvertFrom-Json
$j.composer.x=$cx;$j.composer.y=$cy
$s=Find-Send $p $c
if($s){
 $j.send.x=[int]($s.Left+$s.Width/2)
 $j.send.y=[int]($s.Top+$s.Height/2)
}
$j|ConvertTo-Json -Depth 8|Set-Content $cfg -Encoding UTF8
L "Recalibration UIA v4 OK composer=$cx,$cy send=$($j.send.x),$($j.send.y)"

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $core -FilePath $FilePath -Message $Message -MarkerPath $MarkerPath
exit $LASTEXITCODE
