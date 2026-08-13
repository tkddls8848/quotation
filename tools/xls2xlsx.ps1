# .xls -> .xlsx 1회 변환 (Excel COM). 골든/템플릿 캐시 생성용.
# 런타임에는 사용하지 않는다. 개발 시점에만 실행.
param(
    [string[]]$SrcDir = @("samples", "quotation/resources"),
    [string]$OutDir = ".cache"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$dst = Join-Path $root $OutDir
New-Item -ItemType Directory -Force $dst | Out-Null

# -Filter '*.xls' 는 Windows 8.3 이름 규칙 탓에 .xlsx 까지 잡는다. 확장자를 직접 검사한다.
$files = foreach ($d in $SrcDir) {
    Get-ChildItem -Path (Join-Path $root $d) -File |
        Where-Object { $_.Extension -eq ".xls" }
}

$xlOpenXMLWorkbook = 51

$e = New-Object -ComObject Excel.Application
$e.Visible = $false
$e.DisplayAlerts = $false
try {
    foreach ($f in $files) {
        $target = Join-Path $dst ($f.BaseName + ".xlsx")
        if (Test-Path $target) { Remove-Item $target -Force }
        $wb = $e.Workbooks.Open($f.FullName, 0, $true)
        $wb.SaveAs($target, $xlOpenXMLWorkbook)
        $wb.Close($false)
        "converted: $($f.Name) -> $(Split-Path -Leaf $target)"
    }
}
finally {
    $e.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($e)
}
