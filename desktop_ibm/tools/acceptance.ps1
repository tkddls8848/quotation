param()

$ErrorActionPreference = "Continue"
# desktop_ibm\tools -> desktop_ibm. 배포본은 desktop_ibm\dist 에 낸다 (--distpath).
$desktop_ibm = Split-Path -Parent $PSScriptRoot
$dist = Join-Path $desktop_ibm "dist"
$gui = Join-Path $dist "QuotationTool.exe"
$cli = Join-Path $dist "QuotationTool-cli.exe"
$templateBase = -join @([char]0xACAC, [char]0xC801, [char]0xC11C)  # 견적서
# IBM 문서용·레노버 x86 문서용 두 템플릿 다 첫 실행 때 만들어져야 한다.
$distTemplates = @(
    (Join-Path $dist "${templateBase}_template_IBM.xlsx")
    (Join-Path $dist "${templateBase}_template_Lenovo.xlsx")
)

$pass = 0
$fail = 0
function Check($name, $ok, $detail = "") {
    if ($ok) {
        $script:pass++
        "  OK   $name"
    }
    else {
        $script:fail++
        "  FAIL $name  $detail"
    }
}

"=== 1. Distribution files"
Check "GUI EXE" (Test-Path -LiteralPath $gui)
Check "GUI EXE size" ((Get-Item -LiteralPath $gui).Length -gt 5MB)
Check "CLI EXE removed" (-not (Test-Path -LiteralPath $cli))

foreach ($t in $distTemplates) {
    if (Test-Path -LiteralPath $t) {
        Remove-Item -LiteralPath $t -Force
    }
}

"`n=== 2. GUI startup"
$proc = Start-Process -FilePath $gui -WindowStyle Hidden -PassThru
$running = $false
for ($i = 0; $i -lt 30 -and -not $running; $i++) {
    Start-Sleep -Milliseconds 500
    $running = (Get-Process QuotationTool -ErrorAction SilentlyContinue |
        Measure-Object).Count -gt 0
}
Check "GUI process stays running" $running
$seeded = $false
for ($i = 0; $i -lt 30 -and -not $seeded; $i++) {
    Start-Sleep -Milliseconds 500
    $seeded = ($distTemplates | ForEach-Object { Test-Path -LiteralPath $_ }) `
        -notcontains $false
}
Check "Template seeding (IBM + Lenovo)" $seeded
Stop-Process -Name QuotationTool -Force -ErrorAction SilentlyContinue

"`n=== Result: pass $pass / fail $fail"
if ($fail -gt 0) { exit 1 }
exit 0
