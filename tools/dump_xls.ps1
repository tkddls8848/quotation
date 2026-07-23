# 골든 견적서(.xls) 셀 단위 덤프. Phase 0 분석용.
param([Parameter(Mandatory=$true)][string]$Path)

$e = New-Object -ComObject Excel.Application
$e.Visible = $false; $e.DisplayAlerts = $false
$wb = $e.Workbooks.Open((Resolve-Path $Path).Path, 0, $true)

"##### FILE: $Path"
"##### SHEETS: $($wb.Worksheets.Count)"
foreach ($ws in $wb.Worksheets) {
    $r = $ws.UsedRange
    "`n===== SHEET [$($ws.Name)]  used=$($r.Address($false,$false))  visible=$($ws.Visible)"
    try { "PrintArea=$($ws.PageSetup.PrintArea)" } catch {}
    # 열 너비
    $cw = @()
    for ($j = 1; $j -le 12; $j++) { $cw += "$([char](64+$j))=$([math]::Round($ws.Columns($j).ColumnWidth,2))" }
    "ColWidths: $($cw -join ' ')"
    # 병합 영역
    $merges = @()
    foreach ($c in $r.Cells) {
        if ($c.MergeCells -and $c.Address($false,$false) -eq $c.MergeArea.Cells(1,1).Address($false,$false)) {
            $merges += $c.MergeArea.Address($false,$false)
        }
    }
    if ($merges.Count) { "Merges: $($merges -join ', ')" }
    # 셀 내용
    "--- CELLS (addr | formula | text | numfmt | halign | bold) ---"
    foreach ($c in $r.Cells) {
        $f = $c.Formula
        if ($null -ne $f -and "$f" -ne "") {
            $addr = $c.Address($false, $false)
            $txt = $c.Text
            $nf = $c.NumberFormat
            $ha = $c.HorizontalAlignment
            $bd = $c.Font.Bold
            "$addr | $f | $txt | $nf | $ha | $bd"
        }
    }
}
$wb.Close($false)
$e.Quit()
[void][Runtime.InteropServices.Marshal]::ReleaseComObject($e)
