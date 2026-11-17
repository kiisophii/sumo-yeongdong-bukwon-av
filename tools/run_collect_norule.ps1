# 14조 주행 데이터 10^7 수집 — 보조 규칙 없이 (컨설팅 11/17: 주행 시 규칙 금지)
# 실행: 저장소 폴더에서
#   powershell -ExecutionPolicy Bypass -File tools\run_collect_norule.ps1 <이름>
#   <이름> = dongju / yunho / junhee / sua (사람마다 워커 번호가 겹치지 않음)
# 끊기면 같은 명령을 다시 실행하면 이어서 모읍니다.
param([Parameter(Mandatory = $true)][ValidateSet("dongju", "yunho", "junhee", "sua")][string]$who,
      [int]$steps = 5200000)

$ErrorActionPreference = "Continue"
$offset = @{ dongju = 100; yunho = 116; junhee = 132; sua = 148 }[$who]
$cores = [Environment]::ProcessorCount
$n = [Math]::Max(2, [Math]::Min(12, $cores - 2))
$out = Join-Path $env:USERPROFILE "team14_norule_$who"
$model = Join-Path (Get-Location) "results\norule_v1\model.pt"

# 보조 규칙 환경변수가 남아 있으면 지운다 (규칙 없이 수집)
foreach ($k in "ROUTE_ASSIST_M","MERGE_SUMO","MERGE_STOP","LC_REVERSE_COOLDOWN","RED_STOP","JUNCTION_YIELD",
               "ZIPPER_FOLLOW","ROUTE_SHIELD_M","ASSIST_PROB","HARD_START_PROB","STOP_SHAPING","EXEC_ACTION_BUFFER") {
    Remove-Item "Env:$k" -ErrorAction SilentlyContinue
}
$env:PYTHONIOENCODING = "utf-8"
$env:TEAM14_SCENARIO = "museum"
$env:SIM_REUSE = "1"

$py = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $py = "py" }

Write-Host "[$who] CPU $cores 개 -> 워커 $n 개, 목표 $steps 스텝, 저장 폴더 $out"
Write-Host "모델: $model (규칙 없이 완주 약 80%)"
Write-Host "컴퓨터 절전이 되면 멈춥니다. 충전기 연결 + 덮개 열어 두기"
& $py -u tools\collect_data.py --model $model --out-dir $out `
    --launch $n --worker-offset $offset --total-steps $steps --jsonl

& $py tools\collect_data.py --out-dir $out --summarize
Write-Host ""
Write-Host "끝났으면: $out 폴더를 통째로 압축해서 팀 드라이브에 올려 주세요."
Write-Host "중간에 멈췄으면 같은 명령을 다시 실행하면 이어서 모읍니다."
