param(
    [string]$BaseUrl = "https://api.tracker.yandex.net",
    [string[]]$QueueKeys = @(),
    [string]$Assignee = "",
    [int]$MaxIssuesPerQueue = 200,
    [int]$DueSoonDays = 2,
    [int]$StaleDays = 7,
    [int]$TopIssuesPerQueue = 7,
    [switch]$RiskOnly,
    [switch]$AsJson
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-RequiredEnv {
    param([string]$Name)
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "Missing required environment variable: $Name"
    }
    return $value
}

function Get-OptionalEnv {
    param([string]$Name, [string]$DefaultValue = "")
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value)) { return $DefaultValue }
    return $value
}

function Get-ExcludedQueueKeys {
    $defaults = @("UZUNOVO", "PERVAYA", "TEST")
    $fromEnv = Get-OptionalEnv -Name "TRACKER_QUEUE_KEYS_EXCLUDE" -DefaultValue ""
    if ([string]::IsNullOrWhiteSpace($fromEnv)) { return $defaults }

    $extra = @($fromEnv.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    return @($defaults + $extra | Sort-Object -Unique)
}

function Ensure-Array {
    param([object]$Value)
    if ($null -eq $Value) { return @() }
    if ($Value -is [string]) { return ,$Value }
    if ($Value -is [System.Array]) { return $Value }
    if ($Value -is [System.Collections.IDictionary]) { return ,$Value }

    $result = New-Object System.Collections.Generic.List[object]
    if ($Value -is [System.Collections.IEnumerable]) {
        foreach ($item in $Value) {
            $result.Add($item) | Out-Null
        }
        return $result.ToArray()
    }

    $result.Add($Value) | Out-Null
    return $result.ToArray()
}

function New-TrackerHeaders {
    $scheme = Get-OptionalEnv -Name "TRACKER_AUTH_SCHEME" -DefaultValue "OAuth"
    $token = Get-RequiredEnv -Name "TRACKER_TOKEN"
    $orgHeader = Get-OptionalEnv -Name "TRACKER_ORG_HEADER" -DefaultValue "X-Org-ID"
    $orgId = Get-RequiredEnv -Name "TRACKER_ORG_ID"

    $headers = @{
        "Authorization" = "$scheme $token"
        "Accept" = "application/json"
    }
    $headers[$orgHeader] = $orgId
    return $headers
}

function Add-QueryString {
    param(
        [string]$Url,
        [hashtable]$Query
    )

    if (-not $Query -or $Query.Count -eq 0) { return $Url }

    $pairs = New-Object System.Collections.Generic.List[string]
    foreach ($k in $Query.Keys) {
        if ($null -eq $Query[$k]) { continue }
        $key = [uri]::EscapeDataString([string]$k)
        $val = [uri]::EscapeDataString([string]$Query[$k])
        $pairs.Add("$key=$val") | Out-Null
    }

    if ($pairs.Count -eq 0) { return $Url }
    return "${Url}?$(($pairs -join '&'))"
}

function Invoke-TrackerApi {
    param(
        [ValidateSet("GET", "POST")]
        [string]$Method,
        [string]$Path,
        [hashtable]$Query = $null,
        [object]$Body = $null
    )

    $url = Add-QueryString -Url ("$BaseUrl$Path") -Query $Query
    if ($Method -eq "GET") {
        return Invoke-RestMethod -Uri $url -Method Get -Headers $script:TrackerHeaders
    }

    $json = $null
    if ($null -ne $Body) { $json = $Body | ConvertTo-Json -Depth 15 }
    return Invoke-RestMethod -Uri $url -Method Post -Headers $script:TrackerHeaders -ContentType "application/json; charset=utf-8" -Body $json
}

function Convert-ToDate {
    param([object]$Value)

    if ($null -eq $Value) { return $null }
    $str = [string]$Value
    if ([string]::IsNullOrWhiteSpace($str)) { return $null }

    try { return [DateTimeOffset]::Parse($str) } catch { return $null }
}

function Get-PropertyValue {
    param(
        [object]$Object,
        [string]$PropertyName
    )

    if ($null -eq $Object) { return $null }

    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($PropertyName)) { return $Object[$PropertyName] }
        return $null
    }

    $matched = $Object.PSObject.Properties.Match($PropertyName)
    if ($matched.Count -gt 0) {
        return $matched[0].Value
    }

    return $null
}

function Get-TextValue {
    param([object]$Value)

    if ($null -eq $Value) { return "" }
    if ($Value -is [string]) { return $Value.Trim() }

    $candidateProps = @("key", "id", "name", "display", "login", "uid")
    foreach ($prop in $candidateProps) {
        if ($Value.PSObject.Properties.Match($prop).Count -gt 0 -and $Value.$prop) {
            return [string]$Value.$prop
        }
    }

    return [string]$Value
}

function Get-SafeAssigneeLabel {
    param([object]$Value)

    if ($null -eq $Value) { return "-" }
    if ($Value -is [string]) {
        $trimmed = $Value.Trim()
        if ([string]::IsNullOrWhiteSpace($trimmed)) { return "-" }
        if ($trimmed -match '^\d+$') { return "-" }
        return $trimmed
    }

    foreach ($prop in @("display", "name", "login")) {
        $candidate = Get-PropertyValue -Object $Value -PropertyName $prop
        if ($candidate) {
            $text = [string]$candidate
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                return $text.Trim()
            }
        }
    }

    return "-"
}

function Get-AssigneeSearchText {
    param([object]$Value)

    if ($null -eq $Value) { return "" }
    if ($Value -is [string]) { return $Value.Trim().ToLowerInvariant() }

    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($prop in @("display", "name", "login", "uid")) {
        $candidate = Get-PropertyValue -Object $Value -PropertyName $prop
        if ($candidate) {
            $text = [string]$candidate
            if (-not [string]::IsNullOrWhiteSpace($text)) {
                $parts.Add($text.Trim().ToLowerInvariant()) | Out-Null
            }
        }
    }

    return (($parts | Select-Object -Unique) -join " ").Trim()
}

function Get-NormalizedIssueText {
    param([object]$Value)

    if ($null -eq $Value) { return "" }
    if ($Value -is [string]) { return $Value.Trim().ToLowerInvariant() }

    $parts = New-Object System.Collections.Generic.List[string]
    foreach ($prop in @("key", "id", "name", "display", "value")) {
        if ($Value.PSObject.Properties.Match($prop).Count -gt 0 -and $Value.$prop) {
            $parts.Add(([string]$Value.$prop).Trim()) | Out-Null
        }
    }

    if ($parts.Count -eq 0) {
        $raw = [string]$Value
        if (-not [string]::IsNullOrWhiteSpace($raw)) {
            $parts.Add($raw.Trim()) | Out-Null
        }
    }

    return (($parts -join " ").Trim().ToLowerInvariant())
}

function Convert-ToIssueArray {
    param([object]$Response)

    if ($null -eq $Response) { return @() }
    if ($Response -is [System.Array]) { return @($Response) }
    if ($Response.PSObject.Properties.Match("issues").Count -gt 0) { return @(Ensure-Array $Response.issues) }
    return @(Ensure-Array $Response)
}

function Select-TopUniqueIssues {
    param(
        [object[]]$SourceLists,
        [int]$Limit = 7
    )

    $selected = New-Object System.Collections.Generic.List[object]
    $seen = @{}

    foreach ($list in (Ensure-Array $SourceLists)) {
        foreach ($issue in (Ensure-Array $list)) {
            $key = Get-TextValue (Get-PropertyValue -Object $issue -PropertyName "key")
            if ([string]::IsNullOrWhiteSpace($key)) { continue }
            if ($seen.ContainsKey($key)) { continue }

            $seen[$key] = $true
            $selected.Add($issue) | Out-Null

            if ($selected.Count -ge $Limit) {
                return $selected.ToArray()
            }
        }
    }

    return $selected.ToArray()
}

function Invoke-IssueSearch {
    param(
        [string]$QueueKey,
        [string]$Query,
        [int]$PerPage = 100
    )

    $effectivePerPage = [Math]::Min([Math]::Max($PerPage, 1), 1000)
    $errors = New-Object System.Collections.Generic.List[string]

    if (-not [string]::IsNullOrWhiteSpace($Query)) {
        try {
            $body = @{ query = $Query; perPage = $effectivePerPage }
            $response = Invoke-TrackerApi -Method POST -Path "/v3/issues/_search" -Body $body
            return @(Convert-ToIssueArray $response)
        } catch {
            $errors.Add("POST /v3/issues/_search failed: $($_.Exception.Message)") | Out-Null
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($QueueKey)) {
        try {
            $byQueue = Invoke-TrackerApi -Method GET -Path "/v3/issues" -Query @{ queue = $QueueKey; perPage = $effectivePerPage }
            return @(Convert-ToIssueArray $byQueue)
        } catch {
            $errors.Add("GET /v3/issues by queue failed: $($_.Exception.Message)") | Out-Null
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($Query)) {
        try {
            $fallback = Invoke-TrackerApi -Method GET -Path "/v3/issues" -Query @{ query = $Query; perPage = $effectivePerPage }
            return @(Convert-ToIssueArray $fallback)
        } catch {
            $errors.Add("GET /v3/issues by query failed: $($_.Exception.Message)") | Out-Null
        }
    }

    if ($errors.Count -gt 0) {
        $queueLabel = $QueueKey
        if ([string]::IsNullOrWhiteSpace($queueLabel)) { $queueLabel = "-" }
        throw "Failed to load issues for queue '$queueLabel'. $($errors -join ' | ')"
    }

    return @()
}

function Test-AssigneeMatch {
    param(
        [object]$Issue,
        [string]$AssigneeFilter
    )

    if ([string]::IsNullOrWhiteSpace($AssigneeFilter)) { return $true }

    $filter = $AssigneeFilter.Trim().ToLowerInvariant()
    $searchText = Get-AssigneeSearchText (Get-PropertyValue -Object $Issue -PropertyName "assignee")
    if ([string]::IsNullOrWhiteSpace($searchText)) { return $false }

    return $searchText -like "*$filter*"
}

function Build-QueueSummary {
    param(
        [string]$QueueKey,
        [object[]]$Issues,
        [DateTimeOffset]$TodayStart,
        [DateTimeOffset]$DueSoonDate,
        [int]$StaleThresholdDays,
        [int]$TopIssuesLimit
    )

    $issueList = @(Ensure-Array $Issues)

    $overdue = New-Object System.Collections.Generic.List[object]
    $dueSoon = New-Object System.Collections.Generic.List[object]
    $highPriority = New-Object System.Collections.Generic.List[object]
    $stale = New-Object System.Collections.Generic.List[object]
    $blocked = New-Object System.Collections.Generic.List[object]

    foreach ($issue in $issueList) {
        $deadline = Convert-ToDate (Get-PropertyValue -Object $issue -PropertyName "deadline")
        $updated = Convert-ToDate (Get-PropertyValue -Object $issue -PropertyName "updatedAt")
        $statusText = Get-NormalizedIssueText (Get-PropertyValue -Object $issue -PropertyName "status")
        $priorityText = ((Get-NormalizedIssueText (Get-PropertyValue -Object $issue -PropertyName "priority")) + " " + (Get-NormalizedIssueText (Get-PropertyValue -Object $issue -PropertyName "priorityText"))).Trim().ToLowerInvariant()

        if ($deadline -and $deadline -lt $TodayStart) { $overdue.Add($issue) | Out-Null }
        if ($deadline -and $deadline -ge $TodayStart -and $deadline -le $DueSoonDate) { $dueSoon.Add($issue) | Out-Null }
        if ($priorityText -match 'critical|blocker|highest|high|urgent') { $highPriority.Add($issue) | Out-Null }
        if ($updated -and $updated -lt $TodayStart.AddDays(-1 * $StaleThresholdDays)) { $stale.Add($issue) | Out-Null }
        if ($statusText -match 'block|hold|wait|blocked') { $blocked.Add($issue) | Out-Null }
    }

    $topRisks = Select-TopUniqueIssues -SourceLists @(
        $overdue.ToArray(),
        $blocked.ToArray(),
        $highPriority.ToArray(),
        $dueSoon.ToArray()
    ) -Limit $TopIssuesLimit

    $health = "OK"
    if ($overdue.Count -gt 0 -or $blocked.Count -gt 0) {
        $health = "CRITICAL"
    } elseif ($dueSoon.Count -gt 0 -or $highPriority.Count -gt 0) {
        $health = "WARNING"
    } elseif ($stale.Count -gt 0) {
        $health = "WATCH"
    }

    $riskScore = ($overdue.Count * 4) + ($blocked.Count * 4) + ($dueSoon.Count * 2) + ($highPriority.Count * 2) + $stale.Count

    return [PSCustomObject]@{
        QueueKey = $QueueKey
        Health = $health
        RiskScore = $riskScore
        OpenIssues = $issueList.Count
        OverdueCount = $overdue.Count
        DueSoonCount = $dueSoon.Count
        HighPriorityCount = $highPriority.Count
        StaleCount = $stale.Count
        BlockedCount = $blocked.Count
        TopRisks = @($topRisks)
        SampleSize = $issueList.Count
    }
}

function Build-AssigneeSummary {
    param(
        [string]$AssigneeName,
        [object[]]$Issues,
        [DateTimeOffset]$TodayStart,
        [DateTimeOffset]$DueSoonDate,
        [int]$StaleThresholdDays
    )

    $issueList = @(Ensure-Array $Issues)
    $overdue = 0
    $dueSoon = 0
    $blocked = 0
    $highPriority = 0
    $stale = 0

    foreach ($issue in $issueList) {
        $deadline = Convert-ToDate (Get-PropertyValue -Object $issue -PropertyName "deadline")
        $updated = Convert-ToDate (Get-PropertyValue -Object $issue -PropertyName "updatedAt")
        $statusText = Get-NormalizedIssueText (Get-PropertyValue -Object $issue -PropertyName "status")
        $priorityText = ((Get-NormalizedIssueText (Get-PropertyValue -Object $issue -PropertyName "priority")) + " " + (Get-NormalizedIssueText (Get-PropertyValue -Object $issue -PropertyName "priorityText"))).Trim().ToLowerInvariant()

        if ($deadline -and $deadline -lt $TodayStart) { $overdue++ }
        if ($deadline -and $deadline -ge $TodayStart -and $deadline -le $DueSoonDate) { $dueSoon++ }
        if ($statusText -match 'block|hold|wait|blocked') { $blocked++ }
        if ($priorityText -match 'critical|blocker|highest|high|urgent') { $highPriority++ }
        if ($updated -and $updated -lt $TodayStart.AddDays(-1 * $StaleThresholdDays)) { $stale++ }
    }

    $sortedIssues = @(
        $issueList | Sort-Object `
            @{ Expression = {
                $deadline = Convert-ToDate (Get-PropertyValue -Object $_ -PropertyName "deadline")
                if ($deadline) { $deadline.UtcDateTime } else { [DateTime]::MaxValue }
            }; Descending = $false }, `
            @{ Expression = { Get-TextValue (Get-PropertyValue -Object $_ -PropertyName "key") }; Descending = $false }
    )

    return [PSCustomObject]@{
        Assignee = $AssigneeName
        IssueCount = $issueList.Count
        OverdueCount = $overdue
        DueSoonCount = $dueSoon
        BlockedCount = $blocked
        HighPriorityCount = $highPriority
        StaleCount = $stale
        Issues = $sortedIssues
    }
}

function Format-IssueLine {
    param([object]$Issue)

    $key = Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "key")
    $summary = (Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "summary")) -replace "\s+", " "
    $summary = $summary.Trim()
    if ($summary.Length -gt 120) { $summary = $summary.Substring(0, 117) + "..." }

    $assignee = Get-SafeAssigneeLabel (Get-PropertyValue -Object $Issue -PropertyName "assignee")
    $deadline = Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "deadline")
    $status = Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "status")

    if ([string]::IsNullOrWhiteSpace($deadline)) { $deadline = "-" }
    if ([string]::IsNullOrWhiteSpace($assignee)) { $assignee = "-" }
    if ([string]::IsNullOrWhiteSpace($status)) { $status = "-" }

    return "- $key | status: $status | deadline: $deadline | assignee: $assignee | $summary"
}

function Format-AssigneeIssueLine {
    param([object]$Issue)

    $key = Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "key")
    $queueKey = Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "queueKey")
    $summary = (Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "summary")) -replace "\s+", " "
    $summary = $summary.Trim()
    if ($summary.Length -gt 120) { $summary = $summary.Substring(0, 117) + "..." }

    $deadline = Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "deadline")
    $status = Get-TextValue (Get-PropertyValue -Object $Issue -PropertyName "status")

    if ([string]::IsNullOrWhiteSpace($deadline)) { $deadline = "-" }
    if ([string]::IsNullOrWhiteSpace($status)) { $status = "-" }
    if ([string]::IsNullOrWhiteSpace($queueKey)) { $queueKey = "-" }

    return "- $key | queue: $queueKey | deadline: $deadline | status: $status | $summary"
}

function Get-HealthBadge {
    param([string]$Health)

    switch ($Health) {
        "CRITICAL" { return "[CRIT]" }
        "WARNING" { return "[WARN]" }
        "WATCH" { return "[WATCH]" }
        default { return "[OK]" }
    }
}

function New-MetricBar {
    param(
        [int]$Value,
        [int]$MaxValue,
        [int]$Width = 16
    )

    if ($Width -lt 1) { $Width = 1 }
    if ($MaxValue -le 0) { return ("." * $Width) }

    $filled = [Math]::Min($Width, [Math]::Ceiling(($Value / [double]$MaxValue) * $Width))
    if ($filled -lt 0) { $filled = 0 }

    return (("#" * $filled) + ("." * ($Width - $filled)))
}

function Get-RiskHeadline {
    param(
        [string]$OverallHealth,
        [object]$Totals
    )

    if ($OverallHealth -eq "CRITICAL") {
        return "Main focus today: eliminate overdue and blocked work before backlog grows further."
    }
    if ($OverallHealth -eq "WARNING") {
        return "Main focus today: protect near-deadline and high-priority tasks."
    }
    if ($OverallHealth -eq "WATCH") {
        return "Main focus today: clean stale work before it turns into hidden risk."
    }

    return "Main focus today: flow is stable, keep queue hygiene and monitor deadlines."
}

function Get-QueueActionLines {
    param([object]$QueueSummary)

    if ($QueueSummary.Health -eq "CRITICAL") {
        return @(
            "Triage overdue and blocked tasks first."
            "Confirm owner and next unblock step for each top risk."
        )
    }
    if ($QueueSummary.Health -eq "WARNING") {
        return @(
            "Protect due-soon and high-priority tasks with a fixed time slot."
            "Reconfirm deadline realism and assignee commitment."
        )
    }
    if ($QueueSummary.Health -eq "WATCH") {
        return @(
            "Review stale issues and either close, move, or replan them."
            "Make the next action explicit to prevent silent drift."
        )
    }

    return @(
        "No urgent risks right now."
        "Keep the queue clean and monitor SLA boundaries."
    )
}

$script:TrackerHeaders = New-TrackerHeaders

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
} catch {
}

$null = Invoke-TrackerApi -Method GET -Path "/v3/myself"

if (@(Ensure-Array $QueueKeys).Count -eq 0) {
    $fromEnv = Get-OptionalEnv -Name "TRACKER_QUEUE_KEYS" -DefaultValue ""
    if (-not [string]::IsNullOrWhiteSpace($fromEnv)) {
        $QueueKeys = @($fromEnv.Split(",") | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
}

if (@(Ensure-Array $QueueKeys).Count -eq 0) {
    $queuesResponse = Invoke-TrackerApi -Method GET -Path "/v3/queues"
    $allQueueKeys = @($queuesResponse | ForEach-Object { Get-TextValue $_.key } | Where-Object { $_ })
    if ($allQueueKeys.Count -eq 0) {
        throw "Failed to get queue list."
    }
    $excludedQueueKeys = @(Get-ExcludedQueueKeys)
    $QueueKeys = @($allQueueKeys | Where-Object { $excludedQueueKeys -notcontains $_ })
}

$todayStart = [DateTimeOffset]::Now.Date
$dueSoonDate = $todayStart.AddDays($DueSoonDays + 1).AddSeconds(-1)

$queueIssues = New-Object System.Collections.Generic.List[object]
$summaries = New-Object System.Collections.Generic.List[object]
foreach ($queueKey in (Ensure-Array $QueueKeys)) {
    $query = "Queue: $queueKey Status: !closed"
    $allIssuesForQueue = @(Invoke-IssueSearch -QueueKey $queueKey -Query $query -PerPage $MaxIssuesPerQueue)
    $issues = @(
        $allIssuesForQueue |
            Where-Object { Test-AssigneeMatch -Issue $_ -AssigneeFilter $Assignee } |
            ForEach-Object {
                $issueCopy = $_ | Select-Object *
                if (-not (Get-PropertyValue -Object $issueCopy -PropertyName "queueKey")) {
                    Add-Member -InputObject $issueCopy -NotePropertyName "queueKey" -NotePropertyValue $queueKey -Force
                }
                $issueCopy
            }
    )

    $queueIssues.Add([PSCustomObject]@{
        QueueKey = $queueKey
        Issues = $issues
    }) | Out-Null

    $summary = Build-QueueSummary -QueueKey $queueKey -Issues $issues -TodayStart $todayStart -DueSoonDate $dueSoonDate -StaleThresholdDays $StaleDays -TopIssuesLimit $TopIssuesPerQueue
    $summaries.Add($summary) | Out-Null
}

$allFilteredIssues = @($queueIssues | ForEach-Object { Ensure-Array $_.Issues })
$assigneeSummaries = @(
    $allFilteredIssues |
        Group-Object -Property { Get-SafeAssigneeLabel (Get-PropertyValue -Object $_ -PropertyName "assignee") } |
        Sort-Object -Property Name |
        ForEach-Object {
            Build-AssigneeSummary -AssigneeName $_.Name -Issues $_.Group -TodayStart $todayStart -DueSoonDate $dueSoonDate -StaleThresholdDays $StaleDays
        } |
        Sort-Object `
            @{ Expression = { $_.OverdueCount }; Descending = $true }, `
            @{ Expression = { $_.BlockedCount }; Descending = $true }, `
            @{ Expression = { $_.DueSoonCount }; Descending = $true }, `
            @{ Expression = { $_.IssueCount }; Descending = $true }, `
            @{ Expression = { $_.Assignee }; Descending = $false }
)

$allSummaries = $summaries.ToArray()
$outputSummaries = $allSummaries
if ($RiskOnly) {
    $outputSummaries = @($allSummaries | Where-Object { $_.RiskScore -gt 0 })
}

$totals = [PSCustomObject]@{
    OpenIssues = ($allSummaries | Measure-Object -Property OpenIssues -Sum).Sum
    Overdue = ($allSummaries | Measure-Object -Property OverdueCount -Sum).Sum
    DueSoon = ($allSummaries | Measure-Object -Property DueSoonCount -Sum).Sum
    HighPriority = ($allSummaries | Measure-Object -Property HighPriorityCount -Sum).Sum
    Blocked = ($allSummaries | Measure-Object -Property BlockedCount -Sum).Sum
    Stale = ($allSummaries | Measure-Object -Property StaleCount -Sum).Sum
}

if ($null -eq $totals.OpenIssues) { $totals.OpenIssues = 0 }
if ($null -eq $totals.Overdue) { $totals.Overdue = 0 }
if ($null -eq $totals.DueSoon) { $totals.DueSoon = 0 }
if ($null -eq $totals.HighPriority) { $totals.HighPriority = 0 }
if ($null -eq $totals.Blocked) { $totals.Blocked = 0 }
if ($null -eq $totals.Stale) { $totals.Stale = 0 }

$overallHealth = "OK"
if ($totals.Overdue -gt 0 -or $totals.Blocked -gt 0) {
    $overallHealth = "CRITICAL"
} elseif ($totals.DueSoon -gt 0 -or $totals.HighPriority -gt 0) {
    $overallHealth = "WARNING"
} elseif ($totals.Stale -gt 0) {
    $overallHealth = "WATCH"
}

if ($AsJson) {
    $output = [PSCustomObject]@{
        generatedAt = [DateTimeOffset]::Now.ToString("o")
        overallHealth = $overallHealth
        assigneeFilter = $Assignee
        totals = $totals
        queueCount = $allSummaries.Count
        summaries = $outputSummaries
        assigneeSummaries = $assigneeSummaries
    }
    $output | ConvertTo-Json -Depth 10
    exit 0
}

$sb = New-Object System.Text.StringBuilder
$null = $sb.AppendLine("# Yandex Tracker Dashboard")
$null = $sb.AppendLine("")
$generatedAt = [DateTimeOffset]::Now.ToString("yyyy-MM-dd HH:mm zzz")
$maxOpen = [Math]::Max((($allSummaries | Measure-Object -Property OpenIssues -Maximum).Maximum), 1)
$maxRisk = [Math]::Max((($allSummaries | Measure-Object -Property RiskScore -Maximum).Maximum), 1)
$sortedSummaries = @(
    $outputSummaries | Sort-Object `
        @{ Expression = { $_.RiskScore }; Descending = $true }, `
        @{ Expression = { $_.OpenIssues }; Descending = $true }, `
        @{ Expression = { $_.QueueKey }; Descending = $false }
)
$focusQueues = @($sortedSummaries | Where-Object { $_.RiskScore -gt 0 } | Select-Object -First 2)

$null = $sb.AppendLine("Generated at: $generatedAt")
$null = $sb.AppendLine("Overall health: $(Get-HealthBadge -Health $overallHealth) $overallHealth")
$null = $sb.AppendLine((Get-RiskHeadline -OverallHealth $overallHealth -Totals $totals))
$null = $sb.AppendLine("Queues in scope: $(@(Ensure-Array $QueueKeys) -join ', ')")
if (-not [string]::IsNullOrWhiteSpace($Assignee)) {
    $null = $sb.AppendLine("Assignee filter: $Assignee")
}
$null = $sb.AppendLine("")
$null = $sb.AppendLine("## KPI")
$null = $sb.AppendLine("| Open | Overdue | Blocked | Due soon | High priority | Stale |")
$null = $sb.AppendLine("|---:|---:|---:|---:|---:|---:|")
$null = $sb.AppendLine("| $($totals.OpenIssues) | $($totals.Overdue) | $($totals.Blocked) | $($totals.DueSoon) | $($totals.HighPriority) | $($totals.Stale) |")
$null = $sb.AppendLine("")

if ($RiskOnly -and $outputSummaries.Count -eq 0) {
    $null = $sb.AppendLine("No active risks detected in monitored queues.")
    $sb.ToString()
    exit 0
}

if ($allFilteredIssues.Count -eq 0) {
    if (-not [string]::IsNullOrWhiteSpace($Assignee)) {
        $null = $sb.AppendLine("No open issues found for assignee filter '$Assignee'.")
    } else {
        $null = $sb.AppendLine("No open issues found in monitored queues.")
    }
    $sb.ToString()
    exit 0
}

$null = $sb.AppendLine("## Queue Ranking")
$null = $sb.AppendLine("| Queue | Health | Risk | Load | Open | Overdue | Blocked | Due soon | Priority | Stale |")
$null = $sb.AppendLine("|---|---|---|---|---:|---:|---:|---:|---:|---:|")

foreach ($item in $sortedSummaries) {
    $riskBar = New-MetricBar -Value $item.RiskScore -MaxValue $maxRisk -Width 12
    $loadBar = New-MetricBar -Value $item.OpenIssues -MaxValue $maxOpen -Width 12
    $null = $sb.AppendLine("| $($item.QueueKey) | $(Get-HealthBadge -Health $item.Health) $($item.Health) | [$riskBar] $($item.RiskScore) | [$loadBar] $($item.OpenIssues) | $($item.OpenIssues) | $($item.OverdueCount) | $($item.BlockedCount) | $($item.DueSoonCount) | $($item.HighPriorityCount) | $($item.StaleCount) |")
}

$null = $sb.AppendLine("")
$null = $sb.AppendLine("## Focus Today")
if ($focusQueues.Count -eq 0) {
    $null = $sb.AppendLine("No queues with active operational risk.")
} else {
    foreach ($item in $focusQueues) {
        $null = $sb.AppendLine("- $($item.QueueKey): overdue=$($item.OverdueCount), blocked=$($item.BlockedCount), dueSoon=$($item.DueSoonCount), highPriority=$($item.HighPriorityCount), risk=$($item.RiskScore)")
    }
}

foreach ($item in $sortedSummaries) {
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("## $($item.QueueKey) $(Get-HealthBadge -Health $item.Health)")
    $null = $sb.AppendLine("Health: $($item.Health)")
    $null = $sb.AppendLine("Snapshot: open=$($item.OpenIssues), overdue=$($item.OverdueCount), blocked=$($item.BlockedCount), dueSoon=$($item.DueSoonCount), highPriority=$($item.HighPriorityCount), stale=$($item.StaleCount), riskScore=$($item.RiskScore)")
    $null = $sb.AppendLine("Actions today:")
    foreach ($actionLine in (Get-QueueActionLines -QueueSummary $item)) {
        $null = $sb.AppendLine("- $actionLine")
    }

    $topRisks = @(Ensure-Array $item.TopRisks)
    if ($topRisks.Count -gt 0) {
        $null = $sb.AppendLine("")
        $null = $sb.AppendLine("Top risk issues:")
        foreach ($iss in $topRisks) {
            $null = $sb.AppendLine((Format-IssueLine -Issue $iss))
        }
    }
}

$null = $sb.AppendLine("")
$null = $sb.AppendLine("## Assignee Overview")
$null = $sb.AppendLine("| Assignee | Open | Overdue | Blocked | Due soon | High priority | Stale |")
$null = $sb.AppendLine("|---|---:|---:|---:|---:|---:|---:|")
foreach ($assigneeSummary in $assigneeSummaries) {
    $null = $sb.AppendLine("| $($assigneeSummary.Assignee) | $($assigneeSummary.IssueCount) | $($assigneeSummary.OverdueCount) | $($assigneeSummary.BlockedCount) | $($assigneeSummary.DueSoonCount) | $($assigneeSummary.HighPriorityCount) | $($assigneeSummary.StaleCount) |")
}

foreach ($assigneeSummary in $assigneeSummaries) {
    $null = $sb.AppendLine("")
    $null = $sb.AppendLine("## Assignee: $($assigneeSummary.Assignee)")
    $null = $sb.AppendLine("Snapshot: open=$($assigneeSummary.IssueCount), overdue=$($assigneeSummary.OverdueCount), blocked=$($assigneeSummary.BlockedCount), dueSoon=$($assigneeSummary.DueSoonCount), highPriority=$($assigneeSummary.HighPriorityCount), stale=$($assigneeSummary.StaleCount)")
    $null = $sb.AppendLine("Tasks:")
    foreach ($iss in (Ensure-Array $assigneeSummary.Issues)) {
        $null = $sb.AppendLine((Format-AssigneeIssueLine -Issue $iss))
    }
}

$sb.ToString()
