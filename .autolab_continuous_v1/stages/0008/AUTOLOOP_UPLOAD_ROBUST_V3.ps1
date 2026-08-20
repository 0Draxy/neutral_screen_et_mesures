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
$log=Join-Path $B "logs\AUTOLOOP_UPLOAD_V3.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent)|Out-Null
function L([string]$s){$x="$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $s";Write-Host $x;Add-Content $log $x -Encoding UTF8}
if(-not(Test-Path $cfg)){throw "Calibration absente: $cfg"}
if(-not(Test-Path $core)){throw "Core uploader v2 absent: $core"}
if(-not(Test-Path $FilePath)){throw "ZIP absent: $FilePath"}

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class ALV3W {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
}
"@
function Click([int]$x,[int]$y){
 [ALV3W]::SetCursorPos($x,$y)|Out-Null;Start-Sleep -Milliseconds 120
 [ALV3W]::mouse_event(2,0,0,0,[UIntPtr]::Zero);[ALV3W]::mouse_event(4,0,0,0,[UIntPtr]::Zero)
 Start-Sleep -Milliseconds 250
}
function Firefox-ChatGPT{
 $all=@(Get-Process firefox -ErrorAction SilentlyContinue|Where-Object {$_.MainWindowHandle -ne 0})
 if(-not $all){throw "Firefox visible non trouve"}
 $p=$all|Where-Object {$_.MainWindowTitle -match '(?i)ChatGPT|OpenAI'}|Select-Object -First 1
 if(-not $p){$p=$all|Select-Object -First 1}
 [ALV3W]::ShowWindow($p.MainWindowHandle,3)|Out-Null;Start-Sleep -Milliseconds 200
 [ALV3W]::SetForegroundWindow($p.MainWindowHandle)|Out-Null;Start-Sleep -Milliseconds 600
 return $p
}
function Find-Composer($p){
 $root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
 $wr=$root.Current.BoundingRectangle;$minW=[Math]::Max(420.0,$wr.Width*.35)
 $best=$null;$score=-1e9
 foreach($ct in @([System.Windows.Automation.ControlType]::Edit,[System.Windows.Automation.ControlType]::Document)){
  $cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,$ct)
  $els=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$cond)
  for($i=0;$i -lt $els.Count;$i++){
   try{
    $e=$els.Item($i);$r=$e.Current.BoundingRectangle
    if($e.Current.ProcessId -ne $p.Id -or $r.Width -lt $minW -or $r.Height -lt 18 -or $r.Height -gt 320){continue}
    if($r.Top -lt ($wr.Top+$wr.Height*.48)){continue}
    $s=$r.Width+($r.Top-$wr.Top)
    $meta=([string]$e.Current.Name)+" "+([string]$e.Current.AutomationId)
    if($meta -match '(?i)message|prompt|composer|ask|question'){$s+=100000}
    if($s -gt $score){$best=[pscustomobject]@{E=$e;R=$r};$score=$s}
   }catch{}
  }
 }
 return $best
}
function Find-Send($p,$c){
 $root=[System.Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
 $cond=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Button)
 $els=$root.FindAll([System.Windows.Automation.TreeScope]::Descendants,$cond);$best=$null;$x=-1
 for($i=0;$i -lt $els.Count;$i++){
  try{
   $e=$els.Item($i);$n=[string]$e.Current.Name;$r=$e.Current.BoundingRectangle
   if($n -notmatch '(?i)send|envoyer'){continue}
   if($r.Top -lt ($c.R.Top-140) -or $r.Top -gt ($c.R.Bottom+140)){continue}
   if($r.Left -gt $x){$best=$r;$x=$r.Left}
  }catch{}
 }
 return $best
}
$p=Firefox-ChatGPT
$c=Find-Composer $p
if(-not $c){L "ABORT: compositeur UIA non prouve; aucun texte ne sera saisi";exit 31}
$cx=[int]($c.R.Left+[Math]::Min(90.0,$c.R.Width*.20));$cy=[int]($c.R.Top+$c.R.Height/2)
Click $cx $cy
$f=[System.Windows.Automation.AutomationElement]::FocusedElement
if(-not $f -or $f.Current.ProcessId -ne $p.Id){
 L "ABORT: focus hors Firefox; aucun texte ne sera saisi";exit 32
}
$fr=$f.Current.BoundingRectangle
if($cx -lt $fr.Left -or $cx -gt $fr.Right -or $cy -lt $fr.Top -or $cy -gt $fr.Bottom){
 L "ABORT: focus ne contient pas le point compositeur; aucun texte ne sera saisi";exit 33
}
$j=Get-Content $cfg -Raw|ConvertFrom-Json
$j.composer.x=$cx;$j.composer.y=$cy
$s=Find-Send $p $c
if($s){$j.send.x=[int]($s.Left+$s.Width/2);$j.send.y=[int]($s.Top+$s.Height/2)}
$j|ConvertTo-Json -Depth 8|Set-Content $cfg -Encoding UTF8
L "Recalibration UIA OK composer=$cx,$cy send=$($j.send.x),$($j.send.y)"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $core -FilePath $FilePath -Message $Message -MarkerPath $MarkerPath
exit $LASTEXITCODE
