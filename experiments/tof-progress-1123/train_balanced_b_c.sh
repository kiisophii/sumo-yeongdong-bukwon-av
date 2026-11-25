#!/usr/bin/env bash
# (팀14, 11/25) 동수원 집중 모델(run_20261125_141518)에서 이어 20만 스텝: 출발 비율 다시 나누기(B) + 차선 탐색 중간값(C)
#   B: 출발 50%를 10칸(각 5%)으로 나눔
#      동수원IC 출구 20%  : 1116479399@1500 → 50981265 시작(약 1.5 km 전)부터, 차선 1~2칸 옮기기 전체를 연습
#      진출 램프 5%       : 468241513@300 (이전 19% → 해결돼서 줄임)
#      신협오거리 5%      : -40839116#4@150 (앞쪽 망각 방지, 이전 0%)
#      의왕역 회전교차로 5%: 568664967#4@100 (이전 0%)
#      합류 정체 5%       : 1307152438@300
#      고속도로 합류 5%   : 474882669#1-AddedOnRampEdge@300
#      부곡IC 진입 5%     : 51066582#1@300
#   C: 차선 엔트로피 0.01 → 0.025 (0.05는 합류를 풀었지만 흔들림이 컸음)
#   나머지 보상은 그대로 (속도 기준값 0.05, 정지 실패 끔, 고친 교통 6bd1285)
set -euo pipefail
export SUMO_HOME="${SUMO_HOME:-$(python -c 'import sumo,os;print(os.path.dirname(sumo.__file__))')}"
export SUMO_USE_LIBSUMO=1 PYTHONIOENCODING=utf-8
export COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150
export PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.05
export PROGRESS_GAP_PENALTY_OVERRIDE=0.1 GAP_RSS_DECEL_OVERRIDE=5
export FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1
export EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 LANE_ENTROPY_OVERRIDE=0.025
export HARD_START_TARGETS_OVERRIDE="1116479399@1500,1116479399@1500,1116479399@1500,1116479399@1500,468241513@300,-40839116#4@150,568664967#4@100,1307152438@300,474882669#1-AddedOnRampEdge@300,51066582#1@300"
export CKPT_EVERY_OVERRIDE=20480
python -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train \
  --steps "${1:-200704}" --hard-start-prob 0.5 \
  --init-model "${2:-results/run_20261125_141518_tof_route_outcome_ft_s0/model.pt}"
