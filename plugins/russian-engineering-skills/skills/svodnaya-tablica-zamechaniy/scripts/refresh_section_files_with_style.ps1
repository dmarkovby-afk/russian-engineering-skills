param(
    [Parameter(Mandatory = $true)]
    [string]$SourceWorkbook,
    [Parameter(Mandatory = $true)]
    [string]$RemarksFolder,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$Prefix = "Замечания по Объекту Кашира БМК 6.0",
    [string]$DateStamp = "",
    [string]$CommentHeader = "коментарий проектировщика.",
    [string]$PdftotextPath = "$env:USERPROFILE\YandexDisk\Кодекс\tools\poppler\poppler-24.08.0\Library\bin\pdftotext.exe"
)

$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Import-Module ImportExcel -ErrorAction Stop

function Normalize-Text {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $v = $Value -replace "[\u0000-\u001F]", " "
    $v = $v -replace "\r", ""
    $v = $v -replace "\n+", " "
    $v = $v -replace "\s{2,}", " "
    return $v.Trim()
}

function Get-RegexGroup {
    param(
        [string]$Text,
        [string]$Pattern
    )
    $m = [regex]::Match($Text, $Pattern, [Text.RegularExpressions.RegexOptions]::Singleline)
    if ($m.Success -and $m.Groups.Count -gt 1) {
        return (Normalize-Text $m.Groups[1].Value)
    }
    return ""
}

function Get-Block {
    param(
        [string]$Text,
        [string]$StartPattern,
        [string[]]$EndPatterns
    )
    $opt = [Text.RegularExpressions.RegexOptions]::Singleline
    $s = [regex]::Match($Text, $StartPattern, $opt)
    if (-not $s.Success) { return "" }

    $tail = $Text.Substring($s.Index + $s.Length)
    $end = $tail.Length
    foreach ($ep in $EndPatterns) {
        if ([string]::IsNullOrWhiteSpace($ep)) { continue }
        $m = [regex]::Match($tail, $ep, $opt)
        if ($m.Success -and $m.Index -lt $end) { $end = $m.Index }
    }
    return (Normalize-Text $tail.Substring(0, $end))
}

function Get-InterleavedBlock {
    param(
        [string]$Text,
        [string]$StartPattern,
        [string]$EndPattern
    )
    return (Get-RegexGroup -Text $Text -Pattern ($StartPattern + "(.*?)" + $EndPattern))
}

function Join-Parts {
    param([string]$Left, [string]$Right)
    if ([string]::IsNullOrWhiteSpace($Left)) { return (Normalize-Text $Right) }
    if ([string]::IsNullOrWhiteSpace($Right)) { return (Normalize-Text $Left) }
    return (Normalize-Text ($Left + " " + $Right))
}

function Get-SafeNamePart {
    param([string]$Name)
    $safe = Normalize-Text $Name
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = "Не указано" }
    $safe = $safe -replace '[\\/:*?"<>|]', "-"
    return $safe.Trim()
}

function Get-ProposalFromPdf {
    param([System.IO.FileInfo]$Pdf)

    $cmdLayout = '"' + $PdftotextPath + '" -enc UTF-8 -layout "' + $Pdf.FullName + '" - 2>nul'
    $layout = (cmd /c $cmdLayout | Out-String)

    $proposalMid = Get-InterleavedBlock -Text $layout -StartPattern 'Предложения\s+по\s+отработке' -EndPattern 'замечани[яй]\s*:'
    $proposalTail = Get-Block -Text $layout -StartPattern 'замечани[яй]\s*:' -EndPatterns @('\f')
    if ([string]::IsNullOrWhiteSpace($proposalTail)) {
        $proposalTail = Get-RegexGroup -Text $layout -Pattern 'замечани[яй]\s*:\s*([\s\S]*)$'
    }
    $proposalTail = [regex]::Replace(
        $proposalTail,
        '\s*Требуется\s+внесение\s+изменений\s+или\s+добавлений\s+в\s+документацию\.?\s*$',
        '',
        [Text.RegularExpressions.RegexOptions]::Singleline
    )
    $proposalTail = Normalize-Text $proposalTail
    return (Join-Parts -Left $proposalMid -Right $proposalTail)
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
    $Worksheet.Row(1).Height = 28

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
        }
    }

    $widths = @(7, 18, 18, 38, 16, 72, 60, 72, 42)
    for ($i = 1; $i -le $endCol; $i++) {
        if ($i -le $widths.Count) {
            $Worksheet.Column($i).Width = $widths[$i - 1]
        }
        else {
            $Worksheet.Column($i).Width = 24
        }
    }

    if ($endRow -ge 2) {
        for ($r = 2; $r -le $endRow; $r++) {
            $maxLines = 1
            for ($c = 1; $c -le $endCol; $c++) {
                $txt = [string]$Worksheet.Cells[$r, $c].Text
                if ([string]::IsNullOrWhiteSpace($txt)) { continue }
                $colWidth = [double]$Worksheet.Column($c).Width
                if ($colWidth -lt 1) { $colWidth = 10 }
                $lines = 0
                foreach ($part in ($txt -split "`n")) {
                    $pLen = $part.Length
                    $lines += [Math]::Max(1, [int][Math]::Ceiling($pLen / ($colWidth * 0.95)))
                }
                if ($lines -gt $maxLines) { $maxLines = $lines }
            }
            $Worksheet.Row($r).Height = [Math]::Min(220, [Math]::Max(20, 6 + ($maxLines * 14)))
        }
    }
}

if (-not (Test-Path -LiteralPath $SourceWorkbook)) { throw "Не найден исходный файл: $SourceWorkbook" }
if (-not (Test-Path -LiteralPath $RemarksFolder)) { throw "Не найдена папка с PDF: $RemarksFolder" }
if (-not (Test-Path -LiteralPath $PdftotextPath)) { throw "Не найден pdftotext: $PdftotextPath" }
if ([string]::IsNullOrWhiteSpace($DateStamp)) { $DateStamp = (Get-Date -Format "yyyy-MM-dd") }
if (-not (Test-Path -LiteralPath $OutputDir)) { New-Item -ItemType Directory -Path $OutputDir | Out-Null }

$rows = Import-Excel -Path $SourceWorkbook -WorksheetName "Сводная"
if (-not $rows -or $rows.Count -eq 0) { throw "Лист 'Сводная' пуст: $SourceWorkbook" }

$pdfFiles = Get-ChildItem -LiteralPath $RemarksFolder -Recurse -File -Filter *.pdf | Sort-Object FullName
if ($pdfFiles.Count -ne $rows.Count) {
    throw "Количество PDF ($($pdfFiles.Count)) не совпадает с количеством строк сводной ($($rows.Count))."
}

$setToNotSpecified = 0
for ($idx = 0; $idx -lt $rows.Count; $idx++) {
    $proposal = Get-ProposalFromPdf -Pdf $pdfFiles[$idx]
    if ([string]::IsNullOrWhiteSpace($proposal)) {
        $proposal = "Не указано"
        $setToNotSpecified++
    }
    $rows[$idx]."Предложения по отработке замечания" = $proposal
}

$groups = $rows | Group-Object -Property "Раздел" | Sort-Object Name
$created = New-Object System.Collections.Generic.List[string]

foreach ($g in $groups) {
    $sectionName = Get-SafeNamePart -Name $g.Name
    $fileName = "{0} {1} {2}.xlsx" -f $Prefix, $sectionName, $DateStamp
    $outPath = Join-Path $OutputDir $fileName

    $g.Group |
        ForEach-Object {
            [PSCustomObject]@{
                "№" = $_."№"
                "Код" = $_."Код"
                "Дата" = $_."Дата"
                "Направление деятельности эксперта" = $_."Направление деятельности эксперта"
                "Раздел" = $_."Раздел"
                "Вывод о несоответствии" = $_."Вывод о несоответствии"
                "Ссылка на требования / нормативы" = $_."Ссылка на требования / нормативы"
                "Предложения по отработке замечания" = $_."Предложения по отработке замечания"
                $CommentHeader = ""
            }
        } |
        Export-Excel -Path $outPath -WorksheetName "Замечания" -ClearSheet -AutoFilter -FreezeTopRow -BoldTopRow

    $pkg = Open-ExcelPackage -Path $outPath
    try {
        $ws = $pkg.Workbook.Worksheets["Замечания"]
        Style-Worksheet -Worksheet $ws
        $pkg.Save()
    }
    finally {
        if ($pkg) { $pkg.Dispose() }
    }

    $created.Add($outPath)
}

Write-Output ("SOURCE: " + $SourceWorkbook)
Write-Output ("REMARKS_FOLDER: " + $RemarksFolder)
Write-Output ("OUT_DIR: " + $OutputDir)
Write-Output ("FILE_COUNT: " + $created.Count)
Write-Output ("ROWS_TOTAL: " + $rows.Count)
Write-Output ("PROPOSAL_SET_TO_NOT_SPECIFIED: " + $setToNotSpecified)
$created | ForEach-Object { Write-Output ("FILE: " + $_) }
