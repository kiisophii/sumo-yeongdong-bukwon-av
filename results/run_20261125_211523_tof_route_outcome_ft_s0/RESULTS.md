# 망각 완화 16만 스텝 (11/26, 램프 고친 map6) — 20판 완주 16

- 시작 모델: `results/run_20261125_191050_tof_route_outcome_ft_s0/model.pt` (램프 고친 map6 20판 완주 12)
- 지도: map6 + 진출 램프 수정 (`5b867b8`, `4d87133`)
- 바꾼 것 두 가지
  1. **업데이트를 덜 공격적으로:** `n_steps` 2048 → 8192, `n_epochs` 10 → 4, `lr` 1e-4 → 5e-5 (`train.py`의 `PPO_N_STEPS` / `PPO_N_EPOCHS` / `PPO_LR` 환경변수).
     2048은 전 구간 약 한 판 분량이라, 그 판에 없던 구간(신협오거리 등)의 행동이 10 epoch × 미니배치(약 320번 수정) 동안 밀려났음.
  2. **앞쪽 구간 최소 연습 비율 고정:** 신협오거리·회전교차로 각 10%
- 직전 학습(`run_20261125_204209`, 기존 업데이트 설정 + 신협 5%)은 같은 시작 모델에서 20판 완주 6 (신협 충돌 7)

## 설정

```bash
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 CKPT_EVERY_OVERRIDE=32768 \
PPO_N_STEPS=8192 PPO_N_EPOCHS=4 PPO_LR=5e-5 \
HARD_START_TARGETS_OVERRIDE='-40839116#4@150,-40839116#4@150,-40839116#4@150,-40839116#4@150,568664967#4@100,568664967#4@100,568664967#4@100,568664967#4@100,51066582#1@300,51066582#1@300,51066582#1@300,51066582#1@300,1116479399@300,1116479399@300,1116479399@300,1250775757@300,1250775757@300,1250775757@300,474882669#1-AddedOnRampEdge@300,474882669#1-AddedOnRampEdge@300' \
python3 -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train --steps 163840 --hard-start-prob 0.5 \
  --init-model results/run_20261125_191050_tof_route_outcome_ft_s0/model.pt
```

집중 출발 50%: 신협 10%, 회전교차로 10%, 부곡 영업소 뒤 10%, 동수원IC 앞 차로 감소 7.5%, 동수원IC 출구 직후 합류 7.5%, 고속도로 합류 가속 차로 5%

## 학습 보상

| 구간 | 평균 학습 보상 | 학습 중 평가 속도 (m/s) | 학습 중 평가 완주 (5판) |
|---|---:|---:|---:|
| 0~4.1만 | +24.5 | 14.5 | 3/5 |
| 4.1~8.2만 | +29.7 | 14.5 | 5/5 |
| 8.2~12.3만 | +27.3 | 14.6 | 5/5 |
| 12.3~16.4만 | +23.3 | 14.2 | 5/5 |

## 최종 `model.pt` 20판 (시드 955703411~955703430, 램프 고친 map6, 근처 생성 차 지우기 끔)

결과 파일: `model_eval10_seed955703411.json`, `model_eval10_seed955703421.json` (10판씩, 시드 = 시작 시드 + 회차라 같은 20판)

| 결과 | 위치 | 차선 | 판 수 |
|---|---|---|---:|
| **완주** | 광교박물관 주차장 `611808767` | | **16** |
| 충돌 | 의왕역 회전교차로 `:4582364294` | 0번 | 1 |
| 신호 위반 | 회전교차로 앞 `496583281#1` | 0번 | 1 |
| 경로 이탈 | 부곡 영업소 부스 출구 `51066582#1.110` | 1번 | 1 |
| 경로 이탈 | 동수원IC 갈림길 `377057231` | 2번 | 1 |

평균 속도 약 53 km/h.

### 같은 조건 20판 비교

| 모델 | 완주 | 신협오거리 충돌 |
|---|---:|---:|
| 시작 모델 `run_20261125_191050` | 12 | 1 |
| 직전 학습 `run_20261125_204209` (기존 업데이트 설정) | 6 | 7 |
| **이번** | **16** | **0** |
