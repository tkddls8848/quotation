# Phase 5 인수 테스트 — 빌드된 EXE 를 실사용 조건에서 검증한다.
#   .\tools\acceptance.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$cli = Join-Path $root "dist\QuotationTool-cli.exe"
$gui = Join-Path $root "dist\QuotationTool.exe"
$py = Join-Path $root ".venv\Scripts\python.exe"

$pass = 0; $fail = 0
function Check($name, $ok, $detail = "") {
    if ($ok) { $script:pass++; "  OK   $name" }
    else { $script:fail++; "  실패 $name  $detail" }
}

# 한글/공백/특수문자가 섞인 경로에서 시험한다
$work = Join-Path $env:TEMP "견적 인수시험 #1"
Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$work\입력" | Out-Null
Copy-Item (Join-Path $root "samples\FS5045_260722.xml") "$work\입력\FS5045_260722.xml"
Copy-Item (Join-Path $root "samples\X-ROIS 통합서버#2.xml") "$work\입력\X-ROIS 통합서버#2.xml"

"=== 1. EXE 존재 및 크기"
Check "GUI EXE" (Test-Path $gui)
Check "CLI EXE" (Test-Path $cli)

# 템플릿은 한 번 만들어지면 사용자 편집 보존을 위해 덮어쓰지 않는다.
# 그래서 지난 시험에서 만들어진 낡은 사본이 남아 있을 수 있다. 지우고
# 번들본으로 다시 만들게 해 seeding 경로까지 함께 검증한다.
$distTemplate = Join-Path $root "dist\견적서_template.xlsx"
if (Test-Path $distTemplate) { Remove-Item $distTemplate -Force }
Copy-Item (Join-Path $root "samples\FS5045_260722.xml") "$work\seed.xml"
& $cli "$work\seed.xml" | Out-Null
Check "템플릿 자동 생성" (Test-Path $distTemplate)

"`n=== 2. 한글 경로 일괄 변환"
& $cli "$work\입력\FS5045_260722.xml" "$work\입력\X-ROIS 통합서버#2.xml" | Out-Null
Check "종료 코드 0" ($LASTEXITCODE -eq 0) "실제=$LASTEXITCODE"
Check "산출물 2건" ((Get-ChildItem "$work\입력" -Filter *.xlsx).Count -eq 2)

"`n=== 3. 골든 대조 (EXE 산출물)"
foreach ($n in @("FS5045_260722", "X-ROIS 통합서버#2")) {
    $out = & $py (Join-Path $root "tools\compare.py") `
        (Join-Path $root ".cache\$n.xlsx") "$work\입력\$n.xlsx" `
        --ignore-file (Join-Path $root "tests\golden_ignore.txt") 2>&1
    Check "골든 일치: $n" ($LASTEXITCODE -eq 0) ($out -join " ")
}

"`n=== 4. 오류 처리"
Set-Content "$work\입력\깨진.xml" "<CFXML></CFXML>" -Encoding UTF8
$err = & $cli "$work\입력\깨진.xml" 2>&1
Check "잘못된 XML 은 종료 코드 1" ($LASTEXITCODE -eq 1) "실제=$LASTEXITCODE"
Check "원본 오류 문구 유지" ("$err" -match "CFData을 찾을수 없습니다")

& $cli "$work\입력\FS5045_260722.xml" -o "$work\출력" 2>&1 | Out-Null
Check "저장 폴더 옵션은 없다" ($LASTEXITCODE -ne 0) "실제=$LASTEXITCODE"

"`n=== 5. Excel 이 떠 있는 상태에서 변환 (원본의 핵심 장애)"
$e = New-Object -ComObject Excel.Application
$e.Visible = $false
$e.DisplayAlerts = $false
# 방금 만든 견적서를 Excel 로 열어 둔 채 같은 원본을 다시 변환한다
$held = $e.Workbooks.Open("$work\입력\FS5045_260722.xlsx")
try {
    New-Item -ItemType Directory -Force "$work\입력2" | Out-Null
    Copy-Item (Join-Path $root "samples\X-ROIS 통합서버#2.xml") "$work\입력2\"
    & $cli "$work\입력2\X-ROIS 통합서버#2.xml" | Out-Null
    Check "Excel 실행 중에도 변환 성공" ($LASTEXITCODE -eq 0) "실제=$LASTEXITCODE"

    # 열려 있는 대상 파일에 덮어쓰기를 시도하면 명확히 실패해야 한다
    $locked = & $cli "$work\입력\FS5045_260722.xml" 2>&1
    Check "잠긴 대상은 명확한 오류" ($LASTEXITCODE -eq 1) "실제=$LASTEXITCODE"
}
finally {
    $held.Close($false)
    $e.Quit()
    [void][Runtime.InteropServices.Marshal]::ReleaseComObject($e)
}

"`n=== 6. GUI EXE 기동"
# onefile EXE 는 부트로더가 임시 폴더에 푼 뒤 자식 프로세스로 앱을 띄운다.
# 창을 가진 것은 자식이므로 Start-Process 가 돌려준 부모만 보면 안 된다.
$proc = Start-Process -FilePath $gui -PassThru
$title = ""
for ($i = 0; $i -lt 30 -and -not $title; $i++) {
    Start-Sleep -Milliseconds 500
    $titled = Get-Process QuotationTool -ErrorAction SilentlyContinue |
        Where-Object { $_.MainWindowTitle }
    if ($titled) { $title = $titled[0].MainWindowTitle }
}
Check "GUI 프로세스 유지" (-not $proc.HasExited)
Check "창 제목 표시" ($title -eq "견적서 작성기") "실제='$title'"

Stop-Process -Name QuotationTool -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 800
Check "잔류 프로세스 없음" `
    ((Get-Process QuotationTool* -ErrorAction SilentlyContinue | Measure-Object).Count -eq 0)

"`n=== 결과: 통과 $pass / 실패 $fail"
# 명시적으로 끝낸다. 그러지 않으면 위에서 일부러 실패시킨 CLI 호출의
# 종료 코드가 그대로 남아 스크립트가 실패한 것처럼 보인다.
if ($fail -gt 0) { exit 1 } else { exit 0 }
