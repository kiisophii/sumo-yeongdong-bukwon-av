#!/bin/bash
# (팀14) map6b 모델 데이터 수집 — 표준 조건을 고정해서 실행한다.
#
#   bash tools/collect_map6b.sh <시작 시드> <판 수> <저장 폴더> [이름]
#   예) bash tools/collect_map6b.sh 700000 100 data/map6b s700000
#
# 판 i의 시드 = 시작 시드 + i. 판 시드가 SUMO 시드이고, 판마다 SUMO를 새로 시작한다(SIM_REUSE=1).
# 조건: 신협오거리 지나는 기존 경로, coarse 37칸 관측, 결정적 행동, SUMO 1.28.0.
# 병렬: WORKERS=3 bash tools/collect_map6b.sh ...  (한 폴더에서 이 스크립트를 동시에 두 번 돌리지 말 것)
# 파이썬 지정: PY=/path/to/python bash tools/collect_map6b.sh ...
set -e
[ $# -ge 3 ] || { echo "사용법: bash tools/collect_map6b.sh <시작 시드> <판 수> <저장 폴더> [이름]"; exit 1; }
cd "$(dirname "$0")/.."
# 결과에 영향을 주는 환경변수를 모두 지운 뒤 표준값만 켠다.
unset ASSIST_PROB EXEC_ACTION_BUFFER HARD_START_BACK_M HARD_START_PROB HARD_START_TARGETS JUNCTION_ROW \
      JUNCTION_YIELD LC_COOLDOWN_EXEMPT LC_REVERSE_COOLDOWN LC_TRACK_SUMO MERGE_COOP MERGE_SPEEDMATCH \
      MERGE_STOP MERGE_SUMO RED_STOP ROUNDABOUT_VMAX ROUTE_ASSIST_M ROUTE_SHIELD_M SPAWN_CLEAR_OVERRIDE \
      STOP_SHAPING STOP_SHAPING_DECEL STOP_SHAPING_HEADWAY STOP_SHAPING_YELLOW ZIPPER_FOLLOW \
      TEAM14_JUN_INSIDE TEAM14_TOF_OBS TEAM14_RESET_LOGSTD TEAM14_FIVE_SCALE TEAM14_EVAL_SCRIPT TEAM14_SEED_FILE
export TEAM14_SCENARIO=museum TEAM14_ROUTE_OBS=coarse TEAM14_NO_SPEED_CAP=1
export TEAM14_OVERSPEED_W=1.0 TEAM14_IDLE_PEN=0.3 TEAM14_ROUTE_NO_SHINHYUP=0 SIM_REUSE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONIOENCODING=utf-8
PY=${PY:-python}
exec "$PY" -u collect_pomdp_data.py --episodes "$2" --seed "$1" --policy ppo \
     --model models/map5_ft_200704.pt --workers "${WORKERS:-1}" \
     --collision-penalty 30 --arrival-bonus 30 --blocked-penalty 0 --gamma 0.995 \
     --out-dir "$3" --name "${4:-s$1_n$2}"
