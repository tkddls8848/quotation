param()

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$gui = Join-Path $root "dist\QuotationTool.exe"
$cli = Join-Path $root "dist\QuotationTool-cli.exe"
$templateName = (-join @([char]0xACAC, [char]0xC801, [char]0xC11C)) +
    "_template.xlsx"
$distTemplate = Join-Path (Join-Path $root "dist") $templateName

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

if (Test-Path -LiteralPath $distTemplate) {
    Remove-Item -LiteralPath $distTemplate -Force
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
    $seeded = Test-Path -LiteralPath $distTemplate
}
Check "Template seeding" $seeded
Stop-Process -Name QuotationTool -Force -ErrorAction SilentlyContinue

"`n=== Result: pass $pass / fail $fail"
if ($fail -gt 0) { exit 1 }
exit 0
