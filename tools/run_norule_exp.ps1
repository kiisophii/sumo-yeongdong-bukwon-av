# 14조 규칙 없는 학습 실험 (컨설팅 11/17: 주행 시 보조 규칙 금지)
# 실행: 저장소 폴더에서
#   powershell -ExecutionPolicy Bypass -File tools\run_norule_exp.ps1 <A|B|C>
#   A: 어려운 구간(부곡 합류·차로 합류·출구) 500 m 앞 출발 50%
#   B: A + 미리 멈추기 보상 (끊기는 차로 끝·빨간불 앞에서 못 멈출 속도면 최대 0.2/스텝 감점)
#   C: 미리 멈추기 보상만
# 공통: 시작 모델 results\norule_v1 (규칙 없이 완주 80%), 충돌·완주 ±30, gamma 0.995, lr 3e-5, 40만 스텝
#   두 번째 인자로 시드를 주면 같은 실험을 다른 난수로 반복 (예: ... B 1 → 태그 norule_B_s1)
#   세 번째 인자 cont: 실험 B 결과 모델(results\norule_B)에서 40만 스텝 더 학습 (예: ... B 0 cont → 태그 norule_B_cont)
param([Parameter(Mandatory = $true)][ValidateSet("A", "B", "C")][string]$exp, [int]$seed = 0, [string]$cont = "")

foreach ($k in "ROUTE_ASSIST_M","MERGE_SUMO","MERGE_STOP","LC_REVERSE_COOLDOWN","RED_STOP","JUNCTION_YIELD",
               "ZIPPER_FOLLOW","ROUTE_SHIELD_M","ASSIST_PROB","HARD_START_PROB","STOP_SHAPING","EXEC_ACTION_BUFFER") {
    Remove-Item "Env:$k" -ErrorAction SilentlyContinue
}
$env:PYTHONIOENCODING = "utf-8"
$env:TEAM14_SCENARIO = "museum"
$env:SIM_REUSE = "5"
if ($exp -in "A", "B") { $env:HARD_START_PROB = "0.5" }
if ($exp -in "B", "C") { $env:STOP_SHAPING = "0.2" }

$tag = "norule_$exp"; if ($seed -ne 0) { $tag = "norule_${exp}_s$seed" }
$init = "results\norule_v1\model.pt"
if ($cont -eq "cont") { $init = "results\norule_B\model.pt"; $tag = "${tag}_cont" }
$py = "python"; if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $py = "py" }
Write-Host "실험 $exp : HARD_START_PROB=$env:HARD_START_PROB STOP_SHAPING=$env:STOP_SHAPING (약 2~3시간)"
& $py -u train.py --lr 3e-5 --gamma 0.995 --collision-penalty 30 --arrival-bonus 30 --blocked-penalty 0 `
    --timesteps 400000 --ckpt-every 40000 --tag $tag --seed $seed `
    --init-model $init 2>&1 | Out-File -Encoding utf8 "train_$tag.log"
Write-Host "끝: results\run_*_norule_$exp 폴더와 train_norule_$exp.log 확인"
