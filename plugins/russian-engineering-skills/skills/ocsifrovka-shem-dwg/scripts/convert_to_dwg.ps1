param(
    [Parameter(Mandatory = $true)]
    [string]$Dxf,
    [Parameter(Mandatory = $true)]
    [string]$OutDwg
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Find-AcCoreConsole {
    $roots = @(
        "C:\Program Files\Autodesk\AutoCAD LT 2025\accoreconsole.exe",
        "C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe",
        "C:\Program Files\Autodesk\AutoCAD LT 2024\accoreconsole.exe",
        "C:\Program Files\Autodesk\AutoCAD 2024\accoreconsole.exe",
        "C:\Program Files\Autodesk\AutoCAD LT 2023\accoreconsole.exe",
        "C:\Program Files\Autodesk\AutoCAD LT 2022\accoreconsole.exe"
    )
    foreach ($path in $roots) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    $found = Get-ChildItem -Path "C:\Program Files\Autodesk" -Filter "accoreconsole.exe" -Recurse -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($found) {
        return $found.FullName
    }
    throw "accoreconsole.exe not found"
}

$dxfItem = Get-Item -LiteralPath $Dxf
$outPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutDwg)
$work = "C:\Temp\ocsifrovka_work"
New-Item -ItemType Directory -Force -Path $work | Out-Null
$workDxf = Join-Path $work "input.dxf"
$workDwg = Join-Path $work "output.dwg"
$workScr = Join-Path $work "saveas.scr"
$workLog = Join-Path $work "accore_saveas.log"
$workPathFile = Join-Path $work "outpath.txt"
Copy-Item -LiteralPath $dxfItem.FullName -Destination $workDxf -Force
if (Test-Path -LiteralPath $workDwg) {
    Remove-Item -LiteralPath $workDwg -Force
}

$lsp = Join-Path $PSScriptRoot "saveas_dwg.lsp"
$lspUnix = ($lsp -replace "\\", "/")
$dwgUnix = ($workDwg -replace "\\", "/")
Set-Content -LiteralPath $workPathFile -Value $dwgUnix -Encoding Ascii
@(
    "FILEDIA"
    "0"
    "CMDDIA"
    "0"
    "(load ""$lspUnix"")"
) | Set-Content -LiteralPath $workScr -Encoding Ascii

$accore = Find-AcCoreConsole
$accoreArgs = @("/i", $workDxf, "/s", $workScr)
Write-Host "ACCORE=$accore"
& $accore @accoreArgs *>&1 | Tee-Object -FilePath $workLog
if (Test-Path -LiteralPath $workDwg) {
    $destDir = Split-Path -Parent $outPath
    if ($destDir) {
        New-Item -ItemType Directory -Force -Path $destDir | Out-Null
    }
    Copy-Item -LiteralPath $workDwg -Destination $outPath -Force
    Write-Host "DWG=$outPath"
    exit 0
}

Write-Host "SAVEAS failed. Log: $workLog"
exit 1
