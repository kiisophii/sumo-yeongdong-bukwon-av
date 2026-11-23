#!/usr/bin/env bash
# (팀14, 11/23) 새 모델 처음부터 학습: ToF 센서 관측 + 경로 차선 관측 없음 + 주행 결과 보상
#
# 사용법 (Git Bash, 저장소 루트에서):
#   bash experiments/tof-progress-1123/train.sh               # 기본: 시드 0, 100만 스텝
#   bash experiments/tof-progress-1123/train.sh 1 1000000     # 시드 1 (PC마다 시드를 다르게)
#
# 결과: results/run_<날짜>_tof_progress_s<시드>/ (model.pt, checkpoints/, training_log.csv, eval_log.csv)
set -euo pipefail
SEED="${1:-0}"
STEPS="${2:-1000000}"

# 조교 답변상 쓰면 안 되는 보조 규칙·보상 실험 옵션은 전부 지운다 (PC에 남아 있어도 안전하게)
for v in ASSIST_PROB ROUTE_ASSIST_M ROUTE_SHIELD_M MERGE_SUMO MERGE_STOP MERGE_SPEEDMATCH MERGE_COOP \
         LC_REVERSE_COOLDOWN LC_COOLDOWN_EXEMPT LC_TRACK_SUMO RED_STOP JUNCTION_YIELD JUNCTION_ROW \
         ZIPPER_FOLLOW ROUNDABOUT_VMAX STOP_SHAPING STOP_SHAPING_YELLOW EXEC_ACTION_BUFFER \
         TEAM14_JUN_INSIDE TEAM14_OVERSPEED_W TEAM14_TOF_LEAD_HOLD_S TEAM14_TOF_LEAD_GAP_WINDOW \
         HARD_START_PROB HARD_START_TARGETS HARD_START_BACK_M; do   # 어려운 구간 출발 없이 항상 경로 처음부터 학습
  unset "$v"
done

export PYTHONIOENCODING=utf-8
export TEAM14_SCENARIO=museum
export TEAM14_TOF_OBS=1             # 주변 차·신호·교차로를 ToF 센서(가림 포함)로 본다
export TEAM14_TOF_REAR_DENSITY=1    # 좌우 후방 ToF 밀도 2칸 사용
export TEAM14_ROUTE_OBS=none        # 경로 차선 관측 5칸 제거 (+ 구간 제한속도 1칸) → 관측 39칸 (차로 끝 5칸 포함)
export TEAM14_DROP_SIGNAL_TIME=1      # 신호 남은 시간 칸 제거 (ToF로는 볼 수 없음)
export TEAM14_LANE_END_OBS=1          # 차로 끝 5칸: 차로가 50 m 안에서 물리적으로 끝나는지 (수업 원본 차로 연결성, 경로 무관)
export TEAM14_LANE_END_RANGE=50
export TEAM14_NO_SPEED_CAP=1        # 제한속도에서 자르지 않음 (차량 최고속도 120 km/h만)
export TEAM14_REWARD=progress       # 보상 = 전진 거리 + 완주 + 실패(충돌·경로이탈·신호위반) + 과속 감점
export PROGRESS_TOTAL=20            # 경로 끝까지 전진하면 받는 전진 보상 합
export PROGRESS_OVERSPEED_W=0.1     # 과속 감점: 스텝당 0.1 × (속도/제한속도 - 1)
export SIM_REUSE=5                  # 시뮬레이션 5판마다 새로 시작

python -u train.py \
  --seed "$SEED" \
  --gamma 0.995 \
  --collision-penalty 10 \
  --arrival-bonus 10 \
  --timesteps "$STEPS" \
  --ckpt-every 51200 \
  --tag "tof_progress_s${SEED}"
