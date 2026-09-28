param(
  [Parameter(Mandatory = $true)]
  [string]$Template,

  [Parameter(Mandatory = $true)]
  [string]$Output,

  [Parameter(Mandatory = $true)]
  [string]$ReplacementsJson
)

$ErrorActionPreference = "Stop"

function Resolve-ExistingFile([string]$PathValue) {
  $item = Get-Item -LiteralPath $PathValue
  return $item.FullName
}

function Replace-InRange($Range, [string]$FindText, [string]$ReplaceText) {
  $find = $Range.Find
  $find.ClearFormatting()
  $find.Replacement.ClearFormatting()
  $find.Text = $FindText
  $find.Replacement.Text = $ReplaceText
  $find.Forward = $true
  $find.Wrap = 1
  $find.Format = $false
  $find.MatchCase = $false
  $find.MatchWholeWord = $false
  $find.MatchWildcards = $false
  $find.MatchSoundsLike = $false
  $find.MatchAllWordForms = $false
  [void]$find.Execute($FindText, $false, $false, $false, $false, $false, $true, 1, $false, $ReplaceText, 2)
}

$templatePath = Resolve-ExistingFile $Template
$replacementPath = Resolve-ExistingFile $ReplacementsJson
$outputPath = [System.IO.Path]::GetFullPath($Output)
$outputDir = [System.IO.Path]::GetDirectoryName($outputPath)
if (-not [System.IO.Directory]::Exists($outputDir)) {
  [System.IO.Directory]::CreateDirectory($outputDir) | Out-Null
}

Copy-Item -LiteralPath $templatePath -Destination $outputPath -Force

$json = Get-Content -LiteralPath $replacementPath -Raw -Encoding UTF8
$replacementObject = $json | ConvertFrom-Json
$pairs = @()
foreach ($property in $replacementObject.PSObject.Properties) {
  $pairs += [PSCustomObject]@{
    Find = [string]$property.Name
    Replace = [string]$property.Value
  }
}

$word = $null
$doc = $null
try {
  $word = New-Object -ComObject Word.Application
  $word.Visible = $false
  $word.DisplayAlerts = 0
  $doc = $word.Documents.Open($outputPath, $false, $false)

  foreach ($pair in $pairs) {
    $story = $doc.StoryRanges.Item(1)
    while ($null -ne $story) {
      Replace-InRange $story.Duplicate $pair.Find $pair.Replace
      $next = $story.NextStoryRange
      $story = $next
    }

    foreach ($shape in $doc.Shapes) {
      if ($shape.TextFrame.HasText -ne 0) {
        Replace-InRange $shape.TextFrame.TextRange $pair.Find $pair.Replace
      }
    }
  }

  $doc.Save()
  Write-Host "Saved: $outputPath"
  Write-Host "Replacements requested: $($pairs.Count)"
}
finally {
  if ($null -ne $doc) {
    $doc.Close($true) | Out-Null
  }
  if ($null -ne $word) {
    $word.Quit() | Out-Null
  }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}
