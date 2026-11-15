# v10 학습 (수아 보조 규칙 켠 환경, v9a에서 이어서 40만 스텝, 4만마다 중간 모델 저장)
# 실행: 저장소 폴더에서  powershell -ExecutionPolicy Bypass -File tools\run_v10_dongju.ps1
$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$env:TEAM14_SCENARIO = "museum"
$env:SIM_REUSE = "5"              # 시뮬레이션 재사용 5회 (50회면 출구 정체가 쌓여 학습이 망가짐)
$env:ROUTE_ASSIST_M = "600"       # 경로 차로가 끊기기 600 m 전부터 경로 쪽으로 차선변경 지시
$env:MERGE_SUMO = "1"             # 꼭 필요한 합류가 막히면 SUMO 차선변경(이웃 양보) 사용
$env:MERGE_STOP = "1"             # 합류가 막힌 채 차로 끝이 다가오면 멈춰서 기다림
$env:LC_REVERSE_COOLDOWN = "3"    # 방금 바꾼 방향의 반대로 3초 안엔 못 바꿈 (핑퐁 방지)
python train.py --lr 3e-5 --timesteps 400000 --ckpt-every 40000 --tag v10_dongju --init-model results/sua_v9a/model_401408.pt 2>&1 | Tee-Object -FilePath train_v10_dongju.log
# 끝나면 결과를 별도 브랜치로 올림 (city-route·sua-assist는 건드리지 않음)
$run = Get-ChildItem results -Directory -Filter "run_*v10_dongju" | Sort-Object Name | Select-Object -Last 1
if ($run) {
  git checkout -b dongju-v10-results
  git add -f $run.FullName train_v10_dongju.log
  git commit -m "v10_dongju 학습 결과 (중간 모델 포함)"
  git push -u origin dongju-v10-results
  Write-Host "완료: dongju-v10-results 브랜치에 올렸어요 -> $($run.Name)"
} else { Write-Host "결과 폴더를 못 찾았어요. train_v10_dongju.log 마지막 부분을 수아에게 보내 주세요." }
