#!/usr/bin/env bash
# (팀14, 11/25) 엔트로피 모델(run_20261125_122835)에서 이어 20만 스텝: 동수원 두 지점 집중 학습
#   보상은 우리 원래 값 (차선 엔트로피 0.01, 속도 기준값 0.05), 정지 실패 끔, 고친 교통(6bd1285)
#   집중 출발 50%: 동수원IC 앞 차로 감소 1116479399 ≈19%, 진출 램프 468241513 ≈19%,
#                  고속도로 합류 가속 차로 ≈6%, 부곡IC 진입(영업소) ≈6%  / 나머지 50%는 전 구간
set -euo pipefail
export SUMO_HOME="${SUMO_HOME:-$(python -c 'import sumo,os;print(os.path.dirname(sumo.__file__))')}"
export SUMO_USE_LIBSUMO=1 PYTHONIOENCODING=utf-8
export COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150
export PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.05
export PROGRESS_GAP_PENALTY_OVERRIDE=0.1 GAP_RSS_DECEL_OVERRIDE=5
export FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1
export EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 LANE_ENTROPY_OVERRIDE=0.01
export HARD_START_TARGETS_OVERRIDE="1116479399@300,1116479399@300,1116479399@300,468241513@300,468241513@300,468241513@300,474882669#1-AddedOnRampEdge@300,51066582#1@300"
export CKPT_EVERY_OVERRIDE=20480
python -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train \
  --steps "${1:-200704}" --hard-start-prob 0.5 \
  --init-model "${2:-results/run_20261125_122835_tof_route_outcome_ft_s0/model.pt}"
