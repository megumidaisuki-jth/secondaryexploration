param(
    [string]$InputDocx = 'E:\second\manuscript\joconline\超图支付网络服务可靠性_通信学报中文稿.docx',
    [string]$OutputDirectory = 'E:\second\results\diagnostics\joconline-manuscript-20260929'
)
$ErrorActionPreference = 'Stop'
# Read-only rendering through a separate hidden Word instance. No user document
# is saved or closed. This is the Windows fallback when bundled LO is absent.
$resolvedInput = (Resolve-Path -LiteralPath $InputDocx).Path
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$resolvedOutput = (Resolve-Path -LiteralPath $OutputDirectory).Path
$pdfPath = Join-Path $resolvedOutput 'manuscript-preview.pdf'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Open($resolvedInput, $false, $true)
    $document.Repaginate()
    $pageCount = $document.ComputeStatistics(2)
    $characters = $document.ComputeStatistics(3)
    $document.ExportAsFixedFormat($pdfPath, 17)
    [PSCustomObject]@{ PDF = $pdfPath; Pages = $pageCount; Characters = $characters } | ConvertTo-Json
}
finally {
    if ($null -ne $document) {
        $document.Close(0)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($null -ne $word) {
        $word.Quit(0)
        [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
    }
}
