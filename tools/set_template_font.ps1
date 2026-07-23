# 템플릿(.xls)의 특정 셀 글꼴을 바꾼다. 원본이 .xls 라 Excel 이 필요하다.
#   .\tools\set_template_font.ps1 -Sheet template -Cell H5 -FontName "HY헤드라인M"
param(
    [string]$Path = "견적서_template.xls",
    [Parameter(Mandatory = $true)][string]$Sheet,
    [Parameter(Mandatory = $true)][string]$Cell,
    [Parameter(Mandatory = $true)][string]$FontName
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$file = Join-Path $root $Path

$e = New-Object -ComObject Excel.Application
$e.Visible = $false
$e.DisplayAlerts = $false
try {
    $wb = $e.Workbooks.Open($file)
    $ws = $wb.Worksheets($Sheet)
    $range = $ws.Range($Cell)
    "이전: [$Sheet] $Cell = '$($range.Text)'  글꼴 $($range.Font.Name)/$($range.Font.Size)"
    $range.Font.Name = $FontName
    "이후: [$Sheet] $Cell  글꼴 $($range.Font.Name)/$($range.Font.Size)"
    $wb.Save()
    $wb.Close($true)
}
finally {
    $e.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($e)
}
