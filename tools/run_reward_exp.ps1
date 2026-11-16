# 준희 79% 모델(6175a3e)에서 이어서, 보상만 고쳐 학습 (보조 규칙 없음)
# 실행: 저장소 폴더에서  powershell -ExecutionPolicy Bypass -File tools\run_reward_exp.ps1
# 바꾼 것: 할인율 0.99→0.995(약 100초 앞까지 봄), 충돌·경로이탈 -5→-30, 완주 +2→+30, 막힘 감점 0.05→0
$env:PYTHONIOENCODING = "utf-8"
$env:TEAM14_SCENARIO = "museum"
$env:SIM_REUSE = "5"
$py = "python"; if (-not (Get-Command python -ErrorAction SilentlyContinue)) { $py = "py" }
& $py -u train.py --lr 3e-5 --gamma 0.995 --collision-penalty 30 --arrival-bonus 30 --blocked-penalty 0 `
    --timesteps 400000 --ckpt-every 40000 --tag reward_fix_from_jh79 `
    --init-model results\run_20261114_153509_route_lane_deadline_600k\model.pt 2>&1 | Tee-Object -FilePath train_reward_fix.log
