# 생성물을 Excel 로 실제로 열어 수식이 골든과 같은 값으로 계산되는지 확인한다.
# 개발 검증용이며 런타임 경로가 아니다.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$checks = @(
    @{ File = "FS5045_260722";   Sheet = "TOTAL";       Cells = @("G20", "H20") },
    @{ File = "FS5045_260722";   Sheet = "4680-3P4 #1"; Cells = @("G28", "H28") },
    @{ File = "X-ROIS 통합서버#2"; Sheet = "TOTAL";       Cells = @("G24", "H24") },
    @{ File = "X-ROIS 통합서버#2"; Sheet = "SERVER 1";    Cells = @("G105", "H105") }
)

$e = New-Object -ComObject Excel.Application
$e.Visible = $false
$e.DisplayAlerts = $false
try {
    # Excel 은 같은 이름의 워크북을 동시에 열 수 없다 (.cache\X.xlsx 와 out\X.xlsx).
    # 골든을 먼저 전부 읽어 닫은 뒤 생성물을 연다.
    $goldValues = @{}
    foreach ($c in $checks) {
        $wb = $e.Workbooks.Open((Join-Path $root ".cache\$($c.File).xlsx"), 0, $true)
        foreach ($addr in $c.Cells) {
            $goldValues["$($c.File)|$($c.Sheet)|$addr"] =
                "$($wb.Worksheets($c.Sheet).Range($addr).Text)".Trim()
        }
        $wb.Close($false)
    }

    $fail = 0
    foreach ($c in $checks) {
        # openpyxl 은 수식의 캐시값을 저장하지 않는다. Excel 이 열면서 계산한다.
        $wb = $e.Workbooks.Open((Join-Path $root "out\$($c.File).xlsx"))
        $e.CalculateFullRebuild()
        foreach ($addr in $c.Cells) {
            $key = "$($c.File)|$($c.Sheet)|$addr"
            $g = $goldValues[$key]
            $m = "$($wb.Worksheets($c.Sheet).Range($addr).Text)".Trim()
            if ($g -eq $m) { $mark = "OK  " } else { $mark = "차이"; $fail++ }
            "$mark [$($c.File)] $($c.Sheet)!$addr  골든=$g  생성=$m"
        }
        $wb.Close($false)
    }
    if ($fail -gt 0) { throw "$fail 건 불일치" }
    "`n모든 계산 결과가 골든과 일치합니다."
}
finally {
    $e.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($e)
}
