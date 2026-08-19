param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(Mandatory=$true)][string]$Message
)

$ErrorActionPreference = "Stop"

$devRoot = "C:\dev_EA_MT5"
$config = Join-Path $devRoot "chatgpt_upload_ui.json"
$logDir = Join-Path $devRoot "logs"
$log = Join-Path $logDir "AUTOLOOP_UPLOAD_V017.log"
$diagPng = Join-Path $logDir "AUTOLOOP_UPLOAD_V017_SEND_TIMEOUT.png"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Log([string]$s) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | $s"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding UTF8
}

if(-not (Test-Path $config)) { throw "Calibration absente : $config" }
if(-not (Test-Path $FilePath)) { throw "ZIP absent : $FilePath" }

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class AutoLoopWin32V017 {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint dwFlags, uint dx, uint dy, uint dwData, UIntPtr dwExtraInfo);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

function Get-FirefoxWindow {
    $p = Get-Process firefox -ErrorAction SilentlyContinue |
         Where-Object { $_.MainWindowHandle -ne 0 } |
         Select-Object -First 1
    if(-not $p) { throw "Firefox visible non trouve." }
    return $p
}

function Activate-Firefox {
    $p = Get-FirefoxWindow
    [AutoLoopWin32V017]::ShowWindow($p.MainWindowHandle,3) | Out-Null
    Start-Sleep -Milliseconds 300
    [AutoLoopWin32V017]::SetForegroundWindow($p.MainWindowHandle) | Out-Null
    Start-Sleep -Milliseconds 700
}

function Click-Point($p) {
    [AutoLoopWin32V017]::SetCursorPos([int]$p.x,[int]$p.y) | Out-Null
    Start-Sleep -Milliseconds 160
    [AutoLoopWin32V017]::mouse_event(0x0002,0,0,0,[UIntPtr]::Zero)
    [AutoLoopWin32V017]::mouse_event(0x0004,0,0,0,[UIntPtr]::Zero)
    Start-Sleep -Milliseconds 450
}

function Get-SendButtonBluePixels($p) {
    $size = 41
    $half = [int](($size-1)/2)
    $bmp = New-Object System.Drawing.Bitmap $size,$size
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    try {
        $g.CopyFromScreen([int]$p.x-$half,[int]$p.y-$half,0,0,$bmp.Size)
        $blue = 0
        $saturated = 0
        for($x=0;$x -lt $size;$x++) {
            for($y=0;$y -lt $size;$y++) {
                $c = $bmp.GetPixel($x,$y)
                $max = [Math]::Max($c.R,[Math]::Max($c.G,$c.B))
                $min = [Math]::Min($c.R,[Math]::Min($c.G,$c.B))
                if(($max-$min) -ge 45) { $saturated++ }
                if($c.B -ge 100 -and ($c.B-$c.R) -ge 25 -and ($c.B-$c.G) -ge 8) {
                    $blue++
                }
            }
        }
        return [pscustomobject]@{ Blue=$blue; Saturated=$saturated }
    }
    finally {
        $g.Dispose()
        $bmp.Dispose()
    }
}

function Save-SendDiagnostic($p) {
    try {
        $w=180; $h=120
        $bmp=New-Object System.Drawing.Bitmap $w,$h
        $g=[System.Drawing.Graphics]::FromImage($bmp)
        try {
            $g.CopyFromScreen([int]$p.x-90,[int]$p.y-60,0,0,$bmp.Size)
            $bmp.Save($diagPng,[System.Drawing.Imaging.ImageFormat]::Png)
        } finally {
            $g.Dispose(); $bmp.Dispose()
        }
        Log "Diagnostic capture : $diagPng"
    } catch {
        Log "Capture diagnostic impossible : $($_.Exception.Message)"
    }
}

function Wait-SendActive($sendPoint,[int]$seconds) {
    $deadline=(Get-Date).AddSeconds($seconds)
    $stable=0
    $lastLog=Get-Date

    while((Get-Date) -lt $deadline) {
        $stats=Get-SendButtonBluePixels $sendPoint

        # Disabled button = grey / low saturation. Active Send = blue.
        if($stats.Blue -ge 25 -and $stats.Saturated -ge 35) {
            $stable++
        } else {
            $stable=0
        }

        if(((Get-Date)-$lastLog).TotalSeconds -ge 5) {
            Log "Attente bouton Envoyer actif... blue=$($stats.Blue) sat=$($stats.Saturated) stable=$stable"
            $lastLog=Get-Date
        }

        # Require 3 consecutive positive samples to avoid clicking during a transient redraw.
        if($stable -ge 3) {
            return $true
        }

        Start-Sleep -Milliseconds 500
    }
    return $false
}

try {
    $coords = Get-Content $config -Raw | ConvertFrom-Json

    Log "[UPLOAD 1/8] Activation Firefox"
    Activate-Firefox

    Log "[UPLOAD 2/8] Clic +"
    Click-Point $coords.plus
    Start-Sleep -Milliseconds 900

    Log "[UPLOAD 3/8] Ajouter un fichier"
    Click-Point $coords.add_file
    Start-Sleep -Seconds 1

    Log "[UPLOAD 4/8] Saisie ZIP"
    Set-Clipboard -Value $FilePath
    Click-Point $coords.filename
    [System.Windows.Forms.SendKeys]::SendWait("^a")
    Start-Sleep -Milliseconds 120
    [System.Windows.Forms.SendKeys]::SendWait("^v")
    Start-Sleep -Milliseconds 400

    Log "[UPLOAD 5/8] Validation fichier"
    Click-Point $coords.open_button
    Start-Sleep -Seconds 1

    Log "[UPLOAD 6/8] Saisie message"
    Activate-Firefox
    Click-Point $coords.composer
    Set-Clipboard -Value $Message
    [System.Windows.Forms.SendKeys]::SendWait("^v")
    Start-Sleep -Milliseconds 700

    Log "[UPLOAD 7/8] Attente REELLE bouton Envoyer actif"
    $ready = Wait-SendActive $coords.send 180

    if(-not $ready) {
        Log "Le chargement prend plus de 180 s. Deuxieme fenetre d'attente 120 s, sans re-selectionner le ZIP."
        $ready = Wait-SendActive $coords.send 120
    }

    if(-not $ready) {
        Save-SendDiagnostic $coords.send
        Log "UPLOAD_ERROR_TIMEOUT_SEND_DISABLED : aucun clic Envoyer n'a ete tente."
        exit 21
    }

    Log "[UPLOAD 8/8] Bouton Envoyer actif stable -> clic UNIQUE"
    Click-Point $coords.send
    Start-Sleep -Seconds 3

    Log "UPLOAD V0.17 : clic Envoyer effectue apres validation visuelle du bouton actif."
    exit 0
}
catch {
    Log ("ERREUR UPLOAD : " + $_.Exception.Message)
    $_.Exception.ToString() |
        Set-Content (Join-Path $logDir "AUTOLOOP_UPLOAD_V017_ERROR.txt") -Encoding UTF8
    exit 20
}
