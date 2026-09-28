param(
    [Parameter(Mandatory = $true)]
    [string]$RemarksFolder,
    [Parameter(Mandatory = $true)]
    [string]$WorkbookPath,
    [string]$PdftotextPath = "$env:USERPROFILE\YandexDisk\Кодекс\tools\poppler\poppler-24.08.0\Library\bin\pdftotext.exe"
)

$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Import-Module ImportExcel -ErrorAction Stop

function Normalize-Text {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $v = $Value -replace "[\u0000-\u0008\u000B\u000C\u000E-\u001F]", " "
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
        [string]$EndPattern,
        [string[]]$RemovePatterns
    )
    $v = Get-RegexGroup -Text $Text -Pattern ($StartPattern + "(.*?)" + $EndPattern)
    foreach ($rp in $RemovePatterns) {
        if ([string]::IsNullOrWhiteSpace($rp)) { continue }
        $v = [regex]::Replace($v, $rp, " ", [Text.RegularExpressions.RegexOptions]::Singleline)
    }
    return (Normalize-Text $v)
}

function Join-Parts {
    param([string]$Left, [string]$Right)
    if ([string]::IsNullOrWhiteSpace($Left)) { return (Normalize-Text $Right) }
    if ([string]::IsNullOrWhiteSpace($Right)) { return (Normalize-Text $Left) }
    return (Normalize-Text ($Left + " " + $Right))
}

function Get-SectionFromPdf {
    param([System.IO.FileInfo]$Pdf)
    $section = ""
    if ($Pdf.Name -match "_Раздел\s+(.+?)_Пакет_") {
        $section = $matches[1]
    }
    if ([string]::IsNullOrWhiteSpace($section)) {
        if ($Pdf.Directory.Name -match "Раздел\s+(.+)$") {
            $section = $matches[1]
        }
    }
    $section = Normalize-Text ($section -replace "^Раздел\s+", "")
    return $section
}

function Resolve-SectionByContent {
    param(
        [string]$SourceSection,
        [string]$Conclusion,
        [string]$LayoutText
    )

    $section = Normalize-Text $SourceSection
    $conclusionNorm = (Normalize-Text $Conclusion).ToLowerInvariant()
    $layoutNorm = (Normalize-Text $LayoutText).ToLowerInvariant()

    # Primary rule: classify by the referenced project documentation section for every package.
    if (
        $layoutNorm -match 'раздел\s*01\.\s*пояснительная\s+записка' -or
        $conclusionNorm -match '^раздел\s*[«"]?\s*пояснительн' -or
        $layoutNorm -match 'раздел\s*[«"]?\s*пояснительн'
    ) {
        return '1 ПЗ'
    }

    if ($layoutNorm -match 'технологические\s+решения' -or $layoutNorm -match '_тх[_\s]') { return 'ТХ' }
    if ($layoutNorm -match 'раздел\s*02\.' -or $layoutNorm -match 'схем[аы]\s+планировочной\s+организации') { return 'СПОЗУ' }
    if ($layoutNorm -match 'раздел\s*03\.' -or $layoutNorm -match 'объемно-планировочн' -or $layoutNorm -match 'архитектурн') { return 'АР' }
    if ($layoutNorm -match 'раздел\s*04\.' -or $layoutNorm -match 'конструктивн') { return 'КР' }
    if ($layoutNorm -match 'раздел\s*05\.' -or $layoutNorm -match 'сведения\s+об\s+инженерном\s+оборудовании') {
        if ($layoutNorm -match 'подраздел\s*1\.' -or $layoutNorm -match 'электроснабжен') { return 'ЭС' }
        if ($layoutNorm -match 'подраздел\s*2\.' -or $layoutNorm -match 'водоснабжен') { return 'ВК' }
        if ($layoutNorm -match 'подраздел\s*3\.' -or $layoutNorm -match 'водоотвед' -or $layoutNorm -match 'канализац') { return 'ВК' }
        if ($layoutNorm -match 'подраздел\s*4\.' -or $layoutNorm -match 'отоплен' -or $layoutNorm -match 'вентиляц' -or $layoutNorm -match 'кондиционирован') { return 'ОВ' }
        if ($layoutNorm -match 'подраздел\s*5\.' -or $layoutNorm -match 'сети\s+связи' -or $layoutNorm -match 'систем[аы]\s+связи') { return 'УСС' }
        if ($layoutNorm -match 'подраздел\s*6\.' -or $layoutNorm -match 'газоснабжен') { return 'ГС' }
        if ($layoutNorm -match 'подраздел\s*7\.' -or $layoutNorm -match 'технологическ') { return 'ТХ' }
    }
    if ($layoutNorm -match 'раздел\s*06\.' -or $layoutNorm -match 'проект\s+организации\s+строительства') { return 'ПОС' }
    if ($layoutNorm -match 'раздел\s*08\.' -or $layoutNorm -match 'охран[аы]\s+окружающей\s+среды') { return 'ЭЭ' }
    if ($layoutNorm -match 'раздел\s*09\.' -or $layoutNorm -match 'пожарной\s+безопасности') { return 'ПБ' }
    if ($layoutNorm -match 'раздел\s*10\.' -or $layoutNorm -match 'инвалид') { return 'ОДИ' }
    if ($layoutNorm -match 'раздел\s*11\.' -or $layoutNorm -match 'смет') { return 'СМ' }
    if ($layoutNorm -match 'раздел\s*12\.' -or $layoutNorm -match 'гражданской\s+обороны' -or $layoutNorm -match 'чрезвычайн') { return 'ИТМГОЧС' }

    # Re-mapping for PromB package based on the mismatch conclusion text.
    if ($section -eq 'ПромБ') {
        if (
            $conclusionNorm -match 'газоснабжен' -or
            $conclusionNorm -match 'система\s+газоснабжения' -or
            $conclusionNorm -match 'раздел\s*5\s*подраздел\s*6'
        ) {
            return 'ГСН'
        }

        return 'ПЗ'
    }

    return $section
}

function Get-SafeSheetName {
    param(
        [string]$Name,
        [hashtable]$Used
    )
    $safe = Normalize-Text $Name
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = "Без раздела" }
    $safe = $safe -replace '[:\\/?*\[\]]', '-'
    if ($safe.Length -gt 31) { $safe = $safe.Substring(0, 31) }

    if ($Used.ContainsKey($safe)) {
        $Used[$safe]++
        $suffix = "_" + $Used[$safe]
        $max = 31 - $suffix.Length
        if ($max -lt 1) { $max = 1 }
        $safe = $safe.Substring(0, [Math]::Min($safe.Length, $max)) + $suffix
    }
    else {
        $Used[$safe] = 1
    }

    return $safe
}

function Apply-TextBasedColumnWidths {
    param($Worksheet)
    if (-not $Worksheet.Dimension) { return }

    $end = $Worksheet.Dimension.End.Row
    $cfg = @{
        1 = @{ Min = 6; Max = 8 }
        2 = @{ Min = 14; Max = 24 }
        3 = @{ Min = 16; Max = 24 }
        4 = @{ Min = 24; Max = 56 }
        5 = @{ Min = 10; Max = 24 }
        6 = @{ Min = 30; Max = 95 }
        7 = @{ Min = 26; Max = 90 }
        8 = @{ Min = 30; Max = 95 }
    }

    for ($col = 1; $col -le 8; $col++) {
        $maxLen = $Worksheet.Cells[1, $col].Text.Length
        for ($r = 2; $r -le $end; $r++) {
            $cellText = $Worksheet.Cells[$r, $col].Text
            if ([string]::IsNullOrWhiteSpace($cellText)) { continue }
            foreach ($part in ($cellText -split "`n")) {
                if ($part.Length -gt $maxLen) { $maxLen = $part.Length }
            }
        }

        $raw = [Math]::Ceiling(2 + ($maxLen * 0.9))
        $minW = [double]$cfg[$col].Min
        $maxW = [double]$cfg[$col].Max
        $finalW = [Math]::Max($minW, [Math]::Min($maxW, $raw))
        $Worksheet.Column($col).Width = $finalW
    }
}

function Apply-WrapAndRowHeights {
    param($Worksheet)
    if (-not $Worksheet.Dimension) { return }

    $end = $Worksheet.Dimension.End.Row
    $rg = $Worksheet.Cells["A1:H$end"]
    $rg.Style.WrapText = $true
    $rg.Style.VerticalAlignment = [OfficeOpenXml.Style.ExcelVerticalAlignment]::Top

    for ($r = 2; $r -le $end; $r++) {
        $maxLines = 1
        for ($col = 1; $col -le 8; $col++) {
            $cellText = $Worksheet.Cells[$r, $col].Text
            if ([string]::IsNullOrWhiteSpace($cellText)) { continue }
            $colWidth = [double]$Worksheet.Column($col).Width
            if ($colWidth -lt 1) { $colWidth = 10 }
            $lines = 0
            foreach ($part in ($cellText -split "`n")) {
                $pLen = $part.Length
                $lines += [Math]::Max(1, [int][Math]::Ceiling($pLen / ($colWidth * 0.95)))
            }
            if ($lines -gt $maxLines) { $maxLines = $lines }
        }
        $Worksheet.Row($r).Height = [Math]::Min(220, [Math]::Max(18, 4 + ($maxLines * 14)))
    }
}

function Apply-AlternatingRowColors {
    param($Worksheet)
    if (-not $Worksheet.Dimension) { return }

    $end = $Worksheet.Dimension.End.Row
    if ($end -lt 2) { return }

    for ($r = 2; $r -le $end; $r++) {
        if ($r % 2 -eq 0) {
            $stripe = $Worksheet.Cells[$r, 1, $r, 8]
            $stripe.Style.Fill.PatternType = [OfficeOpenXml.Style.ExcelFillStyle]::Solid
            $stripe.Style.Fill.BackgroundColor.SetColor([System.Drawing.Color]::FromArgb(243, 248, 255))
        }
    }
}

if (-not (Test-Path -LiteralPath $RemarksFolder)) { throw "Не найдена папка: $RemarksFolder" }
if (-not (Test-Path -LiteralPath $PdftotextPath)) { throw "Не найден pdftotext: $PdftotextPath" }
if (-not (Test-Path -LiteralPath $WorkbookPath)) { throw "Не найден workbook: $WorkbookPath" }

$pdfFiles = Get-ChildItem -LiteralPath $RemarksFolder -Recurse -File -Filter *.pdf | Sort-Object FullName
if ($pdfFiles.Count -eq 0) { throw "В папке нет PDF: $RemarksFolder" }

$rows = New-Object System.Collections.Generic.List[object]
$i = 1

foreach ($pdf in $pdfFiles) {
    $cmdLayout = '"' + $PdftotextPath + '" -enc UTF-8 -layout "' + $pdf.FullName + '" - 2>nul'
    $cmdPlain = '"' + $PdftotextPath + '" -enc UTF-8 "' + $pdf.FullName + '" - 2>nul'
    $layout = (cmd /c $cmdLayout | Out-String)
    $plain = (cmd /c $cmdPlain | Out-String)

    $codeVal = Get-RegexGroup -Text $plain -Pattern 'Код:\s*(.+?)\s*(?:\n|$)'
    $dateVal = Get-RegexGroup -Text $plain -Pattern 'Замечание\s+от\s+([0-9]{2}\.[0-9]{2}\.[0-9]{4}(?:\s+[0-9]{2}:[0-9]{2})?)'

    $directionVal = Get-InterleavedBlock -Text $layout -StartPattern 'Направление\s+деятельности' -EndPattern 'эксперта\s*:' -RemovePatterns @()
    if ([string]::IsNullOrWhiteSpace($directionVal)) {
        $directionVal = Get-Block -Text $layout -StartPattern 'эксперта\s*:' -EndPatterns @('Тип\s+несоответствия')
    }

    $conclusionVal = Get-Block -Text $plain -StartPattern 'Вывод\s+о\s+несоответствии\s*:' -EndPatterns @('Ссылка\s+на\s+материалы')

    $materialsMid = Get-InterleavedBlock -Text $layout -StartPattern 'Ссылка\s+на\s+материалы,\s*в' -EndPattern 'о\s+несоответствии\s*:' -RemovePatterns @()
    $materialsTail = Get-Block -Text $layout -StartPattern 'о\s+несоответствии\s*:' -EndPatterns @('Ссылка\s+на\s+конкретное')
    $materialsVal = Join-Parts -Left $materialsMid -Right $materialsTail

    $normMid = Get-InterleavedBlock -Text $layout -StartPattern 'Ссылка\s+на\s+конкретное' -EndPattern 'экспертизы\s*:' -RemovePatterns @(
        'требование,\s*несоответствие',
        'которому\s+было\s+выявлено\s+в\s+ходе'
    )
    $normTail = Get-Block -Text $layout -StartPattern 'экспертизы\s*:' -EndPatterns @('Предложения\s+по\s+отработке')
    $normVal = Join-Parts -Left $normMid -Right $normTail

    $proposalMid = Get-InterleavedBlock -Text $layout -StartPattern 'Предложения\s+по\s+отработке' -EndPattern 'замечани[яй]\s*:' -RemovePatterns @()
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
    $proposalVal = Join-Parts -Left $proposalMid -Right $proposalTail

    $sourceSection = Get-SectionFromPdf -Pdf $pdf
    $section = Resolve-SectionByContent -SourceSection $sourceSection -Conclusion $conclusionVal -LayoutText $layout

    $rows.Add([PSCustomObject]@{
        '№' = $i
        'Код' = $codeVal
        'Дата' = $dateVal
        'Направление деятельности эксперта' = $directionVal
        'Раздел' = $section
        'Вывод о несоответствии' = $conclusionVal
        'Ссылка на требования / нормативы' = $normVal
        'Предложения по отработке замечания' = $proposalVal
    })
    $i++
}

$outputDir = Split-Path -Path $WorkbookPath -Parent
$backupPath = Join-Path $outputDir ("Сводная таблица замечаний 2026-04-13_123731.backup_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".xlsx")
Copy-Item -LiteralPath $WorkbookPath -Destination $backupPath -Force

$tempPath = Join-Path $outputDir ("_svodnaya_tmp_" + (Get-Date -Format "yyyyMMdd_HHmmssfff") + ".xlsx")

$rows | Export-Excel -Path $tempPath -WorksheetName 'Сводная' -AutoFilter -FreezeTopRow -ClearSheet

$summary = $rows |
    Group-Object Раздел |
    Sort-Object Name |
    ForEach-Object {
        [PSCustomObject]@{
            'Раздел' = $_.Name
            'Количество замечаний' = $_.Count
        }
    }
$summary += [PSCustomObject]@{ 'Раздел' = 'ИТОГО'; 'Количество замечаний' = $rows.Count }
$summary | Export-Excel -Path $tempPath -WorksheetName 'Свод по разделам' -ClearSheet -AutoFilter -FreezeTopRow -TableName 'SummaryBySection' -BoldTopRow

$used = @{}
$groups = $rows | Group-Object Раздел | Sort-Object Name
foreach ($g in $groups) {
    $sheetName = Get-SafeSheetName -Name $g.Name -Used $used
    $g.Group | Export-Excel -Path $tempPath -WorksheetName $sheetName -ClearSheet -AutoFilter -FreezeTopRow
}

$pkg = Open-ExcelPackage -Path $tempPath
try {
    $dataSheets = $pkg.Workbook.Worksheets | Where-Object { $_.Name -ne 'Свод по разделам' } | ForEach-Object { $_.Name }
    foreach ($name in $dataSheets) {
        $ws = $pkg.Workbook.Worksheets[$name]
        if (-not $ws) { continue }
        Apply-TextBasedColumnWidths -Worksheet $ws
        Apply-WrapAndRowHeights -Worksheet $ws
        Apply-AlternatingRowColors -Worksheet $ws
    }

    $ws2 = $pkg.Workbook.Worksheets['Свод по разделам']
    if ($ws2 -and $ws2.Dimension) {
        $ws2.Column(1).AutoFit()
        $ws2.Column(2).AutoFit()
        if ($ws2.Column(1).Width -gt 36) { $ws2.Column(1).Width = 36 }
        if ($ws2.Column(2).Width -gt 24) { $ws2.Column(2).Width = 24 }
        $e2 = $ws2.Dimension.End.Row
        $ws2.Cells["A1:B$e2"].Style.VerticalAlignment = [OfficeOpenXml.Style.ExcelVerticalAlignment]::Top
        $ws2.Cells["A1:B$e2"].Style.WrapText = $true
    }

    $pkg.Save()
}
finally {
    if ($pkg) { $pkg.Dispose() }
}

Move-Item -LiteralPath $tempPath -Destination $WorkbookPath -Force

Write-Output ("OK_WORKBOOK: " + $WorkbookPath)
Write-Output ("BACKUP: " + $backupPath)
Write-Output ("PDF_COUNT: " + $pdfFiles.Count)
Write-Output ("ROW_COUNT: " + $rows.Count)
