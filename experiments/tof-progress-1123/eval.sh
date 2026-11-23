#!/usr/bin/env bash
# (팀14, 11/23) tof-progress-1123/train.sh로 학습한 모델 평가. 학습과 같은 관측 설정이어야 한다.
#
# 사용법 (Git Bash, 저장소 루트에서):
#   bash experiments/tof-progress-1123/eval.sh results/run_..._tof_progress_s0/model.pt          # 100판
#   bash experiments/tof-progress-1123/eval.sh results/run_..._tof_progress_s0/model.pt 300 2026
set -euo pipefail
MODEL="$1"
EPISODES="${2:-100}"
SEED="${3:-2026}"

for v in ASSIST_PROB ROUTE_ASSIST_M ROUTE_SHIELD_M MERGE_SUMO MERGE_STOP MERGE_SPEEDMATCH MERGE_COOP \
         LC_REVERSE_COOLDOWN LC_COOLDOWN_EXEMPT LC_TRACK_SUMO RED_STOP JUNCTION_YIELD JUNCTION_ROW \
         ZIPPER_FOLLOW ROUNDABOUT_VMAX STOP_SHAPING STOP_SHAPING_YELLOW EXEC_ACTION_BUFFER \
         TEAM14_JUN_INSIDE TEAM14_OVERSPEED_W TEAM14_TOF_LEAD_HOLD_S TEAM14_TOF_LEAD_GAP_WINDOW HARD_START_PROB; do
  unset "$v"
done

export PYTHONIOENCODING=utf-8
export TEAM14_SCENARIO=museum
export TEAM14_TOF_OBS=1
export TEAM14_TOF_REAR_DENSITY=1
export TEAM14_ROUTE_OBS=none
export TEAM14_NO_SPEED_CAP=1
export TEAM14_REWARD=progress
export SIM_REUSE=1                  # 평가는 판마다 SUMO를 새로 시작

OUT="$(dirname "$MODEL")/eval_${EPISODES}_seed${SEED}.json"
python -u tools/evaluate.py --model "$MODEL" --episodes "$EPISODES" --seed "$SEED" \
  --independent-seeds --no-baseline --out "$OUT"
echo "결과: $OUT"
