[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$SourceSm,

    [Parameter(Mandatory = $true)]
    [string]$OutputSm,

    [Parameter(Mandatory = $true)]
    [string]$MaterialsJson,

    [int]$NumberSm = 0,

    [string]$ObjectContains = '',

    [string]$CodePrefix = 'MAT'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Add-Parameters {
    param(
        [System.Data.OleDb.OleDbCommand]$Command,
        [object[]]$Specs
    )
    if ($Specs.Count -gt 0 -and $Specs[0] -is [System.Data.OleDb.OleDbType]) {
        $Specs = ,$Specs
    }
    foreach ($spec in $Specs) {
        $parameter = $Command.Parameters.Add('@p', $spec[0])
        if ([int]$spec[1] -gt 0) {
            $parameter.Size = [int]$spec[1]
        }
        $parameter.Value = $spec[2]
    }
}

function Open-AccessConnection {
    param([string]$Path)

    $errors = @()
    foreach ($provider in @(
        'Microsoft.ACE.OLEDB.16.0',
        'Microsoft.ACE.OLEDB.12.0',
        'Microsoft.Jet.OLEDB.4.0'
    )) {
        $connection = New-Object System.Data.OleDb.OleDbConnection(
            "Provider=$provider;Data Source=$Path;"
        )
        try {
            $connection.Open()
            return $connection
        }
        catch {
            $errors += "$provider`: $($_.Exception.Message)"
            $connection.Dispose()
        }
    }
    throw "No Access OLEDB provider could open the file. $($errors -join ' | ')"
}

$sourcePath = [System.IO.Path]::GetFullPath($SourceSm)
$outputPath = [System.IO.Path]::GetFullPath($OutputSm)
$jsonPath = [System.IO.Path]::GetFullPath($MaterialsJson)

if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
    throw "Source .sm file not found: $sourcePath"
}
if (-not (Test-Path -LiteralPath $jsonPath -PathType Leaf)) {
    throw "Materials JSON not found: $jsonPath"
}
if ([string]::Equals($sourcePath, $outputPath, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'OutputSm must differ from SourceSm.'
}
if (Test-Path -LiteralPath $outputPath) {
    throw "Output file already exists: $outputPath"
}
if (-not (Test-Path -LiteralPath ([System.IO.Path]::GetDirectoryName($outputPath)) -PathType Container)) {
    throw "Output directory does not exist: $([System.IO.Path]::GetDirectoryName($outputPath))"
}
if ($NumberSm -le 0 -and [string]::IsNullOrWhiteSpace($ObjectContains)) {
    throw 'Provide NumberSm or ObjectContains.'
}

$parsedJson = Get-Content -LiteralPath $jsonPath -Raw -Encoding UTF8 | ConvertFrom-Json
$rawItems = @($parsedJson | ForEach-Object { $_ })
if ($rawItems.Count -eq 1 -and $null -ne $rawItems[0].PSObject.Properties['materials']) {
    $rawItems = @($rawItems[0].materials)
}
if ($rawItems.Count -eq 0) {
    throw 'Materials JSON contains no rows.'
}

$items = @()
for ($i = 0; $i -lt $rawItems.Count; $i++) {
    $row = $rawItems[$i]
    foreach ($required in @('name', 'unit', 'quantity', 'unit_price')) {
        if ($null -eq $row.PSObject.Properties[$required]) {
            throw "Row $($i + 1) has no '$required' field."
        }
    }

    $name = ([string]$row.name).Trim()
    $unit = ([string]$row.unit).Trim()
    $quantity = [double]$row.quantity
    $price = [double]$row.unit_price
    $total = [Math]::Round($quantity * $price, 2)

    if ([string]::IsNullOrWhiteSpace($name) -or $name.Length -gt 250) {
        throw "Invalid material name in row $($i + 1)."
    }
    if ([string]::IsNullOrWhiteSpace($unit) -or $unit.Length -gt 50) {
        throw "Invalid unit in row $($i + 1)."
    }
    if ($quantity -le 0 -or $price -lt 0) {
        throw "Quantity must be positive and price non-negative in row $($i + 1)."
    }
    if ($null -ne $row.PSObject.Properties['amount']) {
        $declared = [double]$row.amount
        if ([Math]::Abs($declared - $total) -gt 0.001) {
            throw "Amount mismatch in row $($i + 1): declared=$declared calculated=$total."
        }
    }

    $requestedCode = ''
    if ($null -ne $row.PSObject.Properties['code']) {
        $requestedCode = ([string]$row.code).Trim()
    }
    if ($requestedCode.Length -gt 16) {
        throw "Code is longer than 16 characters in row $($i + 1)."
    }

    $items += [pscustomobject]@{
        Index = $i + 1
        Name = $name
        Unit = $unit
        Quantity = $quantity
        Price = $price
        Total = $total
        RequestedCode = $requestedCode
    }
}

$invoiceTotal = [Math]::Round(
    (($items | Measure-Object -Property Total -Sum).Sum),
    2
)
$sourceHashBefore = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
Copy-Item -LiteralPath $sourcePath -Destination $outputPath

$connection = $null
$transaction = $null

try {
    $connection = Open-AccessConnection -Path $outputPath

    $objectRows = @()
    $objectCommand = $connection.CreateCommand()
    if ($NumberSm -gt 0) {
        $objectCommand.CommandText = 'SELECT NumberSm, Stroika FROM ReportHead WHERE NumberSm=?'
        Add-Parameters $objectCommand @(
            @([System.Data.OleDb.OleDbType]::Integer, 0, $NumberSm)
        )
    }
    else {
        $objectCommand.CommandText = 'SELECT NumberSm, Stroika FROM ReportHead WHERE Stroika LIKE ?'
        Add-Parameters $objectCommand @(
            @([System.Data.OleDb.OleDbType]::VarWChar, 255, "%$ObjectContains%")
        )
    }

    $objectReader = $objectCommand.ExecuteReader()
    while ($objectReader.Read()) {
        $objectRows += [pscustomobject]@{
            NumberSm = [int]$objectReader['NumberSm']
            Name = ([string]$objectReader['Stroika']).Trim()
        }
    }
    $objectReader.Close()
    $objectCommand.Dispose()

    if ($objectRows.Count -ne 1) {
        throw "Object lookup returned $($objectRows.Count) rows; expected exactly one."
    }
    $target = $objectRows[0]
    if (
        -not [string]::IsNullOrWhiteSpace($ObjectContains) -and
        $target.Name.IndexOf($ObjectContains, [System.StringComparison]::OrdinalIgnoreCase) -lt 0
    ) {
        throw 'NumberSm and ObjectContains refer to different objects.'
    }
    $NumberSm = $target.NumberSm

    $maxCommand = $connection.CreateCommand()
    $maxCommand.CommandText = @'
SELECT
    IIF(MAX(Kod) IS NULL,0,MAX(Kod)) AS MaxKod,
    IIF(MAX([Order]) IS NULL,0,MAX([Order])) AS MaxOrder
FROM TRascenkiFull
WHERE NumberSm=?
'@
    Add-Parameters $maxCommand @(
        @([System.Data.OleDb.OleDbType]::Integer, 0, $NumberSm)
    )
    $maxReader = $maxCommand.ExecuteReader()
    [void]$maxReader.Read()
    $maxKod = [int]$maxReader['MaxKod']
    $maxOrder = [int]$maxReader['MaxOrder']
    $maxReader.Close()
    $maxCommand.Dispose()

    $prefix = $CodePrefix.Trim()
    if ([string]::IsNullOrWhiteSpace($prefix)) {
        $prefix = 'MAT'
    }
    if ($prefix.Length -gt 12) {
        $prefix = $prefix.Substring(0, 12)
    }

    $prepared = @()
    for ($i = 0; $i -lt $items.Count; $i++) {
        $item = $items[$i]
        $code = $item.RequestedCode
        if ([string]::IsNullOrWhiteSpace($code)) {
            $code = '{0}-{1:D3}' -f $prefix, ($i + 1)
        }
        if ($code.Length -gt 16) {
            throw "Generated code is longer than 16 characters: $code"
        }

        $duplicate = $connection.CreateCommand()
        $duplicate.CommandText = 'SELECT COUNT(*) FROM TRascenkiFull WHERE NumberSm=? AND Rascenka=?'
        Add-Parameters $duplicate @(
            @([System.Data.OleDb.OleDbType]::Integer, 0, $NumberSm),
            @([System.Data.OleDb.OleDbType]::VarWChar, 16, $code)
        )
        if ([int]$duplicate.ExecuteScalar() -ne 0) {
            throw "Rascenka code already exists in the estimate: $code"
        }
        $duplicate.Dispose()

        if (@($prepared | Where-Object { $_.Code -ceq $code }).Count -ne 0) {
            throw "Duplicate material code in input: $code"
        }

        $prepared += [pscustomobject]@{
            Kod = $maxKod + $i + 1
            Order = $maxOrder + $i + 1
            Code = $code
            Name = $item.Name
            Unit = $item.Unit
            Quantity = $item.Quantity
            Price = $item.Price
            Total = $item.Total
        }
    }

    $transaction = $connection.BeginTransaction()

    $rascenkaSql = @'
INSERT INTO TRascenkiFull
([Kod],[NumberSm],[Rascenka],[Volume],[Prim],[Demontag],[Primenitelno],
 [Stesn],[StesnMeh],[NaklPlan],[Razdel],[PrZatrOb],[OsnZPOb],[EkspMMOb],
 [ZPMashOb],[MaterOb],[NaklRash],[PlanNakopl],[Rabota],[KodRascenk],
 [EdIzm],[Sort],[Garbage],[TrydRab],[ZimYdor],[Order],[Method],[PriceIron],
 [Transport],[KoefAll],[ZimYdorZP],[Import],[Oboryd],[MatZak],[Position],
 [MashOther],[MaterialOther],[ZPMashOther],[NotPr103],[id_parent],[Metall],
 [trydmash],[ExcludeRasc],[rank],[rankkoef],[zp_koef1],[zp_koef2],
 [eksp_koef1],[eksp_koef2],[zp_koef_sp],[manualcalc])
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
'@

    $materialSql = @'
INSERT INTO TVibMater
([NumberSm],[Material],[Volume],[OtvHran],[OprihZak],
 [Price91],[Stoim91],[Priznak],[FaktPrice],[FaktStoim],
 [Transport],[TransOb],[KodRascenki],[Razdel],[Norma],
 [Name],[EdIzm],[Metall],[IndexMat],[VzvPrice],
 [NDS],[WithNDS],[Import],[Koef91],[KoefTrans91],
 [TranspZak],[b_excludeZS],[OtklPrice],[b_price_manual],
 [matzak],[transp_percent],[roundcheck],[roundval])
VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
'@

    foreach ($item in $prepared) {
        $rascenka = $connection.CreateCommand()
        $rascenka.Transaction = $transaction
        $rascenka.CommandText = $rascenkaSql
        Add-Parameters $rascenka @(
            @([System.Data.OleDb.OleDbType]::Integer, 0, $item.Kod),
            @([System.Data.OleDb.OleDbType]::Integer, 0, $NumberSm),
            @([System.Data.OleDb.OleDbType]::VarWChar, 16, $item.Code),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Quantity),
            @([System.Data.OleDb.OleDbType]::VarWChar, 60, ''),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::VarWChar, 50, '0% 0%'),
            @([System.Data.OleDb.OleDbType]::Integer, 0, 0),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Price),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Price),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::VarWChar, 250, $item.Name),
            @([System.Data.OleDb.OleDbType]::Integer, 0, 0),
            @([System.Data.OleDb.OleDbType]::VarWChar, 50, $item.Unit),
            @([System.Data.OleDb.OleDbType]::Integer, 0, 0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Integer, 0, $item.Order),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::VarWChar, 50, ''),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Integer, 0, 0),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $true)
        )
        if ($rascenka.ExecuteNonQuery() -ne 1) {
            throw "Failed to insert TRascenkiFull row: $($item.Code)"
        }
        $rascenka.Dispose()

        $resource = $connection.CreateCommand()
        $resource.Transaction = $transaction
        $resource.CommandText = $materialSql
        Add-Parameters $resource @(
            @([System.Data.OleDb.OleDbType]::Integer, 0, $NumberSm),
            @([System.Data.OleDb.OleDbType]::VarWChar, 30, $item.Code),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Quantity),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Price),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Total),
            @([System.Data.OleDb.OleDbType]::VarWChar, 50, [string][char]0x0424),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Price),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Total),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Integer, 0, $item.Kod),
            @([System.Data.OleDb.OleDbType]::Integer, 0, 0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::VarWChar, 250, $item.Name),
            @([System.Data.OleDb.OleDbType]::VarWChar, 250, $item.Unit),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Total),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Double, 0, 1.0),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Double, 0, $item.Price),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $true),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Double, 0, 0.0),
            @([System.Data.OleDb.OleDbType]::Boolean, 0, $false),
            @([System.Data.OleDb.OleDbType]::Integer, 0, 0)
        )
        if ($resource.ExecuteNonQuery() -ne 1) {
            throw "Failed to insert TVibMater row: $($item.Code)"
        }
        $resource.Dispose()
    }

    $transaction.Commit()
    $transaction.Dispose()
    $transaction = $null

    $firstKod = $maxKod + 1
    $lastKod = $maxKod + $prepared.Count
    $verify = $connection.CreateCommand()
    $verify.CommandText = @'
SELECT
    COUNT(*) AS RowCount,
    SUM(vm.Stoim91) AS BaseTotal,
    SUM(vm.FaktStoim) AS FaktTotal,
    SUM(IIF(rf.manualcalc<>0,0,1)) AS BadManual,
    SUM(IIF(
        vm.Material=rf.Rascenka
        AND vm.Name=rf.Rabota
        AND vm.EdIzm=rf.EdIzm
        AND ABS(vm.Volume-rf.Volume)<0.000001
        AND ABS(vm.Price91-rf.MaterOb)<0.000001,
        0,
        1
    )) AS BadLinks
FROM TRascenkiFull rf
INNER JOIN TVibMater vm
    ON vm.NumberSm=rf.NumberSm AND vm.KodRascenki=rf.Kod
WHERE rf.NumberSm=? AND rf.Kod>=? AND rf.Kod<=?
'@
    Add-Parameters $verify @(
        @([System.Data.OleDb.OleDbType]::Integer, 0, $NumberSm),
        @([System.Data.OleDb.OleDbType]::Integer, 0, $firstKod),
        @([System.Data.OleDb.OleDbType]::Integer, 0, $lastKod)
    )
    $verifyReader = $verify.ExecuteReader()
    [void]$verifyReader.Read()
    $savedCount = [int]$verifyReader['RowCount']
    $baseTotal = [Math]::Round([double]$verifyReader['BaseTotal'], 2)
    $faktTotal = [Math]::Round([double]$verifyReader['FaktTotal'], 2)
    $badManual = [int]$verifyReader['BadManual']
    $badLinks = [int]$verifyReader['BadLinks']
    $verifyReader.Close()
    $verify.Dispose()

    if (
        $savedCount -ne $prepared.Count -or
        [Math]::Abs($baseTotal - $invoiceTotal) -gt 0.001 -or
        [Math]::Abs($faktTotal - $invoiceTotal) -gt 0.001 -or
        $badManual -ne 0 -or
        $badLinks -ne 0
    ) {
        throw "Verification failed: rows=$savedCount base=$baseTotal fakt=$faktTotal badManual=$badManual badLinks=$badLinks."
    }

    $connection.Close()
    $sourceHashAfter = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
    $outputHash = (Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash

    [pscustomobject]@{
        Output = $outputPath
        Object = $target.Name
        NumberSm = $NumberSm
        AddedRows = $savedCount
        PrintRows = $savedCount
        Total = $baseTotal
        ManualRecalcBlocked = $true
        SourceUnchanged = ($sourceHashBefore -eq $sourceHashAfter)
        OutputHash = $outputHash
    }
}
catch {
    if ($null -ne $transaction) {
        try { $transaction.Rollback() } catch {}
    }
    if ($null -ne $connection -and $connection.State -eq 'Open') {
        $connection.Close()
    }
    if (Test-Path -LiteralPath $outputPath) {
        Remove-Item -LiteralPath $outputPath -Force
    }
    throw
}
finally {
    if ($null -ne $connection) {
        if ($connection.State -eq 'Open') {
            $connection.Close()
        }
        $connection.Dispose()
    }
}
