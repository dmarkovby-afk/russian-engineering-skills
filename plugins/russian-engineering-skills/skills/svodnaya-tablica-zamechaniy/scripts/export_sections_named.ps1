param(
    [Parameter(Mandatory = $true)]
    [string]$SourceWorkbook,
    [Parameter(Mandatory = $true)]
    [string]$OutputDir,
    [string]$Prefix = "Замечания по Объекту Кашира БМК 6.0",
    [string]$DateStamp = ""
)

$ErrorActionPreference = "Stop"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
Import-Module ImportExcel -ErrorAction Stop

function Normalize-Text {
    param([string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return "" }
    $v = $Value -replace "[\u0000-\u001F]", " "
    $v = $v -replace "\s{2,}", " "
    return $v.Trim()
}

function Get-SafeNamePart {
    param([string]$Name)
    $safe = Normalize-Text $Name
    if ([string]::IsNullOrWhiteSpace($safe)) { $safe = "Не указано" }
    $safe = $safe -replace '[\\/:*?"<>|]', "-"
    return $safe.Trim()
}

if (-not (Test-Path -LiteralPath $SourceWorkbook)) {
    throw "Не найден исходный файл: $SourceWorkbook"
}

if ([string]::IsNullOrWhiteSpace($DateStamp)) {
    $DateStamp = (Get-Date -Format "yyyy-MM-dd")
}

if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$rows = Import-Excel -Path $SourceWorkbook -WorksheetName "Сводная"
if (-not $rows -or $rows.Count -eq 0) {
    throw "На листе 'Сводная' нет данных."
}

$groups = $rows | Group-Object -Property "Раздел" | Sort-Object Name
if (-not $groups -or $groups.Count -eq 0) {
    throw "Не удалось сгруппировать данные по колонке 'Раздел'."
}

$created = New-Object System.Collections.Generic.List[string]
foreach ($g in $groups) {
    $sectionName = Get-SafeNamePart -Name $g.Name
    $fileName = "{0} {1} {2}.xlsx" -f $Prefix, $sectionName, $DateStamp
    $outPath = Join-Path $OutputDir $fileName

    $g.Group |
        Select-Object `
            "№",
            "Код",
            "Дата",
            "Направление деятельности эксперта",
            "Раздел",
            "Вывод о несоответствии",
            "Ссылка на требования / нормативы",
            "Предложения по отработке замечания" |
        Export-Excel -Path $outPath -WorksheetName "Замечания" -ClearSheet -AutoFilter -FreezeTopRow -BoldTopRow

    $pkg = Open-ExcelPackage -Path $outPath
    try {
        $ws = $pkg.Workbook.Worksheets["Замечания"]
        if ($ws -and $ws.Dimension) {
            $endRow = $ws.Dimension.End.Row
            $ws.Cells["A1:H$endRow"].Style.WrapText = $true
            $ws.Cells["A1:H$endRow"].Style.VerticalAlignment = [OfficeOpenXml.Style.ExcelVerticalAlignment]::Top
            for ($c = 1; $c -le 8; $c++) {
                $ws.Column($c).AutoFit()
            }
        }
        $pkg.Save()
    }
    finally {
        if ($pkg) { $pkg.Dispose() }
    }

    $created.Add($outPath)
}

Write-Output ("SOURCE: " + $SourceWorkbook)
Write-Output ("OUT_DIR: " + $OutputDir)
Write-Output ("FILE_COUNT: " + $created.Count)
$created | ForEach-Object { Write-Output ("FILE: " + $_) }
