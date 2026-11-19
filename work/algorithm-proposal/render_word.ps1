$ErrorActionPreference = 'Stop'
$root = 'C:\Users\sumir\Documents\ChatGPT\lss'
$inputPath = Join-Path $root 'outputs\MS Thesis Proposal - Lightweight Secure Offline Sync.docx'
$renderPath = Join-Path $root 'work\algorithm-proposal\rendered'
New-Item -ItemType Directory -Path $renderPath -Force | Out-Null
$pdfPath = Join-Path $renderPath 'encrypted-proposal.pdf'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$word.AutomationSecurity = 3
$word.Options.SaveNormalPrompt = $false
$word.Options.UpdateLinksAtOpen = $false
$doc = $null
try {
    $doc = $word.Documents.Open($inputPath, $false, $false)
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    $doc.Fields.Update() | Out-Null
    $doc.Save()
    $doc.ExportAsFixedFormat($pdfPath, 17)
    Write-Output ('PDF exported: ' + $pdfPath)
} finally {
    if ($null -ne $doc) { $doc.Close(0) }
    $word.Quit(0)
    if ($null -ne $doc) { [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc) | Out-Null }
    [System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word) | Out-Null
}
