param(
    [string]$SourcePath = "",
    [string]$OutputDir = "",
    [string]$CommentDefault = ""
)

$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

function New-TextFromCodes {
    param([int[]]$Codes)
    return (-join ($Codes | ForEach-Object { [char]$_ }))
}

function Normalize-Text {
    param([string]$Value)
    if ($null -eq $Value) { return "" }
    $v = $Value -replace "[\u0000-\u001F]", " "
    $v = $v -replace "\s{2,}", " "
    return $v.Trim()
}

function Get-SafeFilePart {
    param([string]$Name)
    $safe = Normalize-Text $Name
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = "NoSection" }
    $safe = $safe -replace "[\\/:*?""<>|]", "_"
    $safe = $safe -replace "\s+", "_"
    if ($safe.Length -gt 80) {
        $safe = $safe.Substring(0, 80)
    }
    return $safe
}

function Get-LatestWorkbook {
    param([string]$StartPath)
    $candidate = Get-ChildItem -LiteralPath $StartPath -Recurse -File -Filter *.xlsx |
        Where-Object { $_.Name -notlike "~$*" } |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1

    if (-not $candidate) {
        throw "No XLSX workbook found under: $StartPath"
    }

    return $candidate.FullName
}

function Get-WorksheetData {
    param(
        [string]$WorkbookPath,
        [string]$PreferredSheetName,
        [string]$SectionHeaderName,
        [string]$CommentHeaderName,
        [string]$CommentValue
    )

    $pkg = Open-ExcelPackage -Path $WorkbookPath
    try {
        $ws = $pkg.Workbook.Worksheets[$PreferredSheetName]
        if (-not $ws) {
            $ws = $pkg.Workbook.Worksheets | Where-Object { $_.Dimension -and $_.Dimension.End.Row -ge 2 } | Select-Object -First 1
        }
        if (-not $ws -or -not $ws.Dimension) {
            throw "No data worksheet found in workbook."
        }

        $endRow = $ws.Dimension.End.Row
        $endCol = $ws.Dimension.End.Column

        $headers = @()
        for ($c = 1; $c -le $endCol; $c++) {
            $h = Normalize-Text ([string]$ws.Cells[1, $c].Text)
            if ([string]::IsNullOrWhiteSpace($h)) { $h = "Column$c" }
            $headers += $h
        }

        $sectionCol = [array]::IndexOf($headers, $SectionHeaderName) + 1
        if ($sectionCol -le 0) {
            $sectionCol = [Math]::Min(5, $endCol)
        }

        $rows = New-Object System.Collections.Generic.List[object]
        for ($r = 2; $r -le $endRow; $r++) {
            $isEmpty = $true
            for ($c = 1; $c -le $endCol; $c++) {
                if (-not [string]::IsNullOrWhiteSpace([string]($ws.Cells[$r, $c].Text))) {
                    $isEmpty = $false
                    break
                }
            }
            if ($isEmpty) { continue }

            $obj = [ordered]@{}
            for ($c = 1; $c -le $endCol; $c++) {
                $obj[$headers[$c - 1]] = [string]($ws.Cells[$r, $c].Text)
            }

            $sectionValue = Normalize-Text ([string]($ws.Cells[$r, $sectionCol].Text))
            if ([string]::IsNullOrWhiteSpace($sectionValue)) { $sectionValue = "Not specified" }
            $obj[$SectionHeaderName] = $sectionValue
            $obj[$CommentHeaderName] = $CommentValue
            $rows.Add([PSCustomObject]$obj)
        }

        return [PSCustomObject]@{
            Headers = @($headers + $CommentHeaderName)
            SectionHeader = $SectionHeaderName
            Rows = $rows
        }
    }
    finally {
        if ($pkg) { $pkg.Dispose() }
    }
}

function Style-Worksheet {
    param($Worksheet)

    if (-not $Worksheet -or -not $Worksheet.Dimension) { return }
    $endRow = $Worksheet.Dimension.End.Row
    $endCol = $Worksheet.Dimension.End.Column

    $header = $Worksheet.Cells[1, 1, 1, $endCol]
    $header.Style.Font.Bold = $true
    $header.Style.Font.Color.SetColor([System.Drawing.Color]::FromArgb(255, 255, 255))
    $header.Style.Fill.PatternType = [OfficeOpenXml.Style.ExcelFillStyle]::Solid
    $header.Style.Fill.BackgroundColor.SetColor([System.Drawing.Color]::FromArgb(28, 84, 134))
    $header.Style.HorizontalAlignment = [OfficeOpenXml.Style.ExcelHorizontalAlignment]::Center
    $header.Style.VerticalAlignment = [OfficeOpenXml.Style.ExcelVerticalAlignment]::Center

    $all = $Worksheet.Cells[1, 1, $endRow, $endCol]
    $all.Style.Border.Top.Style = [OfficeOpenXml.Style.ExcelBorderStyle]::Thin
    $all.Style.Border.Right.Style = [OfficeOpenXml.Style.ExcelBorderStyle]::Thin
    $all.Style.Border.Bottom.Style = [OfficeOpenXml.Style.ExcelBorderStyle]::Thin
    $all.Style.Border.Left.Style = [OfficeOpenXml.Style.ExcelBorderStyle]::Thin

    if ($endRow -ge 2) {
        $data = $Worksheet.Cells[2, 1, $endRow, $endCol]
        $data.Style.WrapText = $true
        $data.Style.VerticalAlignment = [OfficeOpenXml.Style.ExcelVerticalAlignment]::Top

        for ($r = 2; $r -le $endRow; $r++) {
            if ($r % 2 -eq 0) {
                $stripe = $Worksheet.Cells[$r, 1, $r, $endCol]
                $stripe.Style.Fill.PatternType = [OfficeOpenXml.Style.ExcelFillStyle]::Solid
                $stripe.Style.Fill.BackgroundColor.SetColor([System.Drawing.Color]::FromArgb(243, 248, 255))
            }
            $Worksheet.Row($r).Height = 40
        }
    }

    $widths = @(7, 18, 18, 38, 16, 72, 60, 72, 42)
    for ($i = 1; $i -le $endCol; $i++) {
        if ($i -le $widths.Count) {
            $Worksheet.Column($i).Width = $widths[$i - 1]
        } else {
            $Worksheet.Column($i).Width = 28
        }
    }

    $commentCol = $endCol
    if ($endRow -ge 2) {
        for ($r = 2; $r -le $endRow; $r++) {
            $txt = Normalize-Text ([string]($Worksheet.Cells[$r, $commentCol].Text))
            if ([string]::IsNullOrWhiteSpace($txt)) {
                $c = $Worksheet.Cells[$r, $commentCol]
                $c.Style.Fill.PatternType = [OfficeOpenXml.Style.ExcelFillStyle]::Solid
                $c.Style.Fill.BackgroundColor.SetColor([System.Drawing.Color]::FromArgb(255, 245, 204))
            }
        }
    }
}

Import-Module ImportExcel -ErrorAction Stop

$summarySheetName = New-TextFromCodes @(1057,1074,1086,1076,1085,1072,1103)
$sectionHeader = New-TextFromCodes @(1056,1072,1079,1076,1077,1083)
$commentHeader = New-TextFromCodes @(1050,1086,1084,1084,1077,1085,1090,1072,1088,1080,1081,32,1080,1089,1087,1086,1083,1085,1080,1090,1077,1083,1103)

if ([string]::IsNullOrWhiteSpace($SourcePath)) {
    $SourcePath = Get-LatestWorkbook -StartPath (Get-Location).Path
}

if (-not (Test-Path -LiteralPath $SourcePath)) {
    throw "Source workbook not found: $SourcePath"
}

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $sourceDir = Split-Path -Path $SourcePath -Parent
    $OutputDir = Join-Path $sourceDir ("sections_split_" + (Get-Date -Format "yyyy-MM-dd_HHmmss"))
}

if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$data = Get-WorksheetData -WorkbookPath $SourcePath -PreferredSheetName $summarySheetName -SectionHeaderName $sectionHeader -CommentHeaderName $commentHeader -CommentValue $CommentDefault
if (-not $data.Rows -or $data.Rows.Count -eq 0) {
    throw "No data rows found in source workbook: $SourcePath"
}

$groups = $data.Rows | Group-Object -Property $data.SectionHeader | Sort-Object Name
if (-not $groups -or $groups.Count -eq 0) {
    throw "No section groups could be created."
}

$createdFiles = New-Object System.Collections.Generic.List[string]
foreach ($group in $groups) {
    $name = Normalize-Text $group.Name
    if ([string]::IsNullOrWhiteSpace($name)) { $name = "Not_specified" }

    $out = Join-Path $OutputDir ("remarks_" + (Get-SafeFilePart -Name $name) + ".xlsx")
    $group.Group |
        Select-Object -Property $data.Headers |
        Export-Excel -Path $out -WorksheetName "Remarks" -AutoFilter -FreezeTopRow -BoldTopRow -ClearSheet

    $pkgOut = Open-ExcelPackage -Path $out
    try {
        $wsOut = $pkgOut.Workbook.Worksheets["Remarks"]
        Style-Worksheet -Worksheet $wsOut
        $pkgOut.Save()
    }
    finally {
        if ($pkgOut) { $pkgOut.Dispose() }
    }

    $createdFiles.Add($out)
}

Write-Output ("SOURCE: " + $SourcePath)
Write-Output ("OUT_DIR: " + $OutputDir)
Write-Output ("SECTION_FILES: " + $createdFiles.Count)
$createdFiles | ForEach-Object { Write-Output ("FILE: " + $_) }
