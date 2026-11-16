# 14조 주행 데이터 10^7 나눠서 수집 (사람마다 워커 번호가 겹치지 않게 나눔)
# 실행: 저장소 폴더에서
#   powershell -ExecutionPolicy Bypass -File tools\run_collect_team.ps1 <이름>
#   <이름> = dongju / yunho / junhee / sua / extra1 / extra2 (extra: 대신 돌릴 때 쓰는 예비 번호, 누구와도 안 겹침)
# 끊기면 같은 명령을 다시 실행하면 이어서 모읍니다.
param([Parameter(Mandatory = $true)][ValidateSet("dongju", "yunho", "junhee", "sua", "extra1", "extra2")][string]$who)

$ErrorActionPreference = "Continue"
$offset = @{ dongju = 0; yunho = 16; junhee = 32; sua = 48; extra1 = 64; extra2 = 80 }[$who]
$steps = 2600000                       # 4명 x 260만 = 1,040만 (10^7 + 여유)
$cores = [Environment]::ProcessorCount
$n = [Math]::Max(2, [Math]::Min(12, $cores - 2))
$out = Join-Path $env:USERPROFILE "team14_data_$who"

# 수집 조건 (현재 최고 조합: v9a + 보조 규칙, 180회 평가 완주 94.4% / 충돌 5.0%)
$env:PYTHONIOENCODING = "utf-8"
$env:TEAM14_SCENARIO = "museum"
$env:SIM_REUSE = "1"
$env:ROUTE_ASSIST_M = "600"
$env:MERGE_SUMO = "1"
$env:MERGE_STOP = "1"
$env:LC_REVERSE_COOLDOWN = "3"
$env:RED_STOP = "1"
$env:JUNCTION_YIELD = "3"

$py = "python"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $py = "py" }

Write-Host "[$who] CPU $cores 개 -> 워커 $n 개, 목표 $steps 스텝, 저장 폴더 $out"
Write-Host "컴퓨터 절전이 되면 멈춥니다. 충전기 연결 + 덮개 열어 두기 (끝나는 데 약 2~6시간)"
& $py -u tools\collect_data.py --model results\sua_v9a\model_401408.pt --out-dir $out `
    --launch $n --worker-offset $offset --total-steps $steps --jsonl

& $py tools\collect_data.py --out-dir $out --summarize
Write-Host ""
Write-Host "끝났으면: $out 폴더를 통째로 압축해서 팀 드라이브에 올려 주세요 (약 3 GB)."
Write-Host "중간에 멈췄으면 같은 명령을 다시 실행하면 이어서 모읍니다."
