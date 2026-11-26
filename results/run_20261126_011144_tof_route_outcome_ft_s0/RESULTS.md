# 양보 위반 감점 5 + 동수원IC 앞 12.5% 8만 스텝 (11/26, 램프 고친 map6) — 20판 완주 17

- 시작 모델: `results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt` (20판 16, 무작위 100판 82)
- 지도: map6 + 진출 램프 수정 (`5b867b8`, `4d87133`)
- 바꾼 것
  1. **양보 위반 감점 2 → 5** (`YIELD_PENALTY_OVERRIDE=5`): 결과 기준 보상. 양보해야 하는 비신호 교차로에 교차 차량이 다가오는데 들어가면 감점(SUMO 실제 상태로 판정, 종료 안 함).
     신협오거리 좌회전 충돌 추적에서 교차 차량이 건물에 가려 "모름"인 채 진입하는 것이 원인이었음. 정지거리 기반 속도 감점처럼 운전 방법을 정하는 보상은 쓰지 않음.
  2. **동수원IC 앞 차로 감소 출발 7.5% → 12.5%**: 211523에서 이어 학습할 때마다(5번) 누적 약 4~10만 스텝에서 동수원IC 출구를 잊었음.
  3. **업데이트를 더 작게:** `n_steps` 20000, `n_epochs` 3, `lr` 2e-5 (211523 학습은 8192·4·5e-5). 학습은 8만에서 끊음.

## 설정

```bash
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 CKPT_EVERY_OVERRIDE=40000 \
PPO_N_STEPS=20000 PPO_N_EPOCHS=3 PPO_LR=2e-5 YIELD_PENALTY_OVERRIDE=5 \
HARD_START_TARGETS_OVERRIDE='1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,-40839116#4@150,-40839116#4@150,-40839116#4@150,-40839116#4@150,568664967#4@100,568664967#4@100,568664967#4@100,568664967#4@100,51066582#1@300,51066582#1@300,51066582#1@300,1250775757@300,1250775757@300,474882669#1-AddedOnRampEdge@300,474882669#1-AddedOnRampEdge@300' \
python3 -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train --steps 80000 --hard-start-prob 0.5 \
  --init-model results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt
```

집중 출발 50%: 동수원IC 앞 차로 감소 12.5%, 신협 10%, 회전교차로 10%, 부곡 영업소 뒤 7.5%, 동수원IC 출구 직후 합류 5%, 고속도로 합류 가속 차로 5%

## 학습 보상

| 스텝 | 학습 보상 |
|---:|---:|
| 2만 | +27.5 |
| 4만 | +28.8 |
| 6만 | +33.7 |
| 8만 | +33.6 |

(양보 감점이 5라 이전 학습과 보상 숫자를 그대로 비교할 수 없음. 업데이트 4번이라 학습 중 평가는 없음)

## 20판 평가 (시드 955703411~955703430, 램프 고친 map6)

결과 파일: `checkpoints/model_40000_eval10_seed*.json`, `model_eval10_seed*.json` (10판씩, 같은 20판)

| 모델 | 완주 | 실패 |
|---|---:|---|
| 4만 `checkpoints/model_40000.pt` | **17** | 회전교차로 `:4582364294` 충돌 1, 교차로 `:13739111090` 충돌 1, 광교로 `-667234604#1` 충돌 1 |
| 8만 `model.pt` | **17** | 동수원IC 진출로 `50981102` 충돌 1, 회전교차로 뒤 `488779086#0` 충돌 1, 부곡 영업소 부스 출구 `51066582#1.110` 이탈 1 |

평균 속도 약 55 km/h. 두 모델 모두 신협 충돌 0, 동수원IC 출구 놓침 0.

### 같은 20판 비교

| 모델 | 완주 | 동수원IC 출구 놓침 |
|---|---:|---:|
| 시작 모델 `211523` | 16 | 1 |
| 211523에서 이어 학습한 이전 5번 (비율·업데이트 크기 바꿔 가며) | 0~15 | 최대 15 |
| **이번 4만 / 8만** | **17 / 17** | **0 / 0** |

17판과 16판은 20판으로는 구별이 어려운 차이라, 양보 감점의 효과는 더 많은 판으로 확인해야 함.
