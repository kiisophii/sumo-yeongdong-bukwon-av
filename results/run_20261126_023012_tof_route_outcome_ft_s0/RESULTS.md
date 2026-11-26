# 교차로 안 관측 유지(A) 8만 스텝 (11/26, 램프 고친 map6) — 20판 완주 18

- 시작 모델: `results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt` (20판 16, 무작위 100판 82)
- 지도: map6 + 진출 램프 수정 (`5b867b8`, `4d87133`)
- **평가할 때도 `TEAM14_TOF_JUN_INSIDE=1`을 켜야 함** (관측이 바뀜)

## 바꾼 것

1. **교차로 안 관측 유지 (`TEAM14_TOF_JUN_INSIDE=1`, `env/tof_observation.py`)**
   - 기존: 양보 교차로 내부 차선에 들어서면 교차로 관측 세 칸이 [1, −1, −1](교차로 없음, 교차 차량 없음)으로 바뀜
   - 바꾼 뒤: 바로 전에 다가가던 양보 교차로 안이면 [거리 0, 양보 의무 +1, 교차 차량(ToF)]를 계속 보여 줌. 교차 차량 판단은 기존 함수 그대로(ToF로 보이는 차만)
   - 원인: 신협오거리 좌회전 충돌 추적(시드 955703434)에서, 교차로 안에서 관측이 사라져 건너는 중에 가속(+0.28)하다 충돌. 옵션만 켜도(학습 전) 같은 순간 감속(−0.11)으로 바뀜
   - 새 정보 없음, 경로 차선 관측 아님. 옵션을 끄면 기존과 완전히 같음(같은 판 추적값 일치)
2. **동수원IC 앞 차로 감소 출발 15%** (이어 학습할 때마다 가장 먼저 잊는 곳)
3. 작은 업데이트: `n_steps` 20000, `n_epochs` 3, `lr` 2e-5, 8만에서 끊고 2만마다 체크포인트
4. 양보 위반 감점은 원래 값 2 (A의 효과만 보려고)

## 설정

```bash
TEAM14_TOF_JUN_INSIDE=1 \
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 CKPT_EVERY_OVERRIDE=20000 \
PPO_N_STEPS=20000 PPO_N_EPOCHS=3 PPO_LR=2e-5 \
HARD_START_TARGETS_OVERRIDE='1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,-40839116#4@150,-40839116#4@150,-40839116#4@150,-40839116#4@150,568664967#4@100,568664967#4@100,568664967#4@100,568664967#4@100,51066582#1@300,51066582#1@300,1250775757@300,1250775757@300,474882669#1-AddedOnRampEdge@300,474882669#1-AddedOnRampEdge@300' \
python3 -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train --steps 80000 --hard-start-prob 0.5 \
  --init-model results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt
```

집중 출발 50%: 동수원IC 앞 차로 감소 15%, 신협 10%, 회전교차로 10%, 부곡 영업소 뒤 5%, 동수원IC 출구 직후 합류 5%, 고속도로 합류 가속 차로 5%

## 학습 보상

| 스텝 | 학습 보상 |
|---:|---:|
| 2만 | +22.6 |
| 4만 | +27.1 |
| 6만 | +11.3 |
| 8만 | +36.0 |

## 체크포인트별 20판 (시드 955703411~955703430, A 켜고 평가)

결과 파일: `checkpoints/model_<스텝>_eval10_seed*.json` (10판씩, 같은 20판). 최종 `model.pt` = `checkpoints/model_80000.pt`

| 모델 | 완주 | 신협 | 회전교차로 (충돌·신호 위반) | 동수원IC 출구 놓침 | 그 외 |
|---|---:|---:|---:|---:|---|
| `211523` (시작 모델, A 없이) | 16 | 0 | 2 | 1 | 부곡 1 |
| 2만 | 15 | 0 | 3 | 1 | 출구 직후 합류 `1224608702.60` 1 |
| 4만 | 17 | 2 | 0 | 0 | 고속도로 합류 1 |
| 6만 | 15 | 2 | 2 | 0 | 교차로 `:13739111090` 1 |
| **8만** | **18** | 1 | 1 (신호 위반) | **0** | |
