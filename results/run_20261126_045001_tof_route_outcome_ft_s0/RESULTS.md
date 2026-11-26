# A 8만 위에 관측 방안 B 추가 10만 스텝 (11/26, 램프 고친 map6) — 4만: 20판 19, 무작위 100판 92

- 시작 모델: `results/run_20261126_023012_tof_route_outcome_ft_s0/model.pt` (A 8만, 20판 18, 무작위 100판 86)
- 지도: map6 + 진출 램프 수정 (`5b867b8`, `4d87133`), **신호 연동 패치 없음** (쓰지 않기로 결정)
- SUMO 1.28.0 (eclipse-sumo·libsumo pip)
- **평가할 때도 `TEAM14_TOF_JUN_INSIDE=1`과 `JUNCTION_SKIP_SHORT_OVERRIDE=50`을 둘 다 켜야 함** (관측이 바뀜)

## 바꾼 것

A 학습(`023012`)과 비교해 **관측 방안 B(`JUNCTION_SKIP_SHORT_OVERRIDE=50`) 하나만 추가**.
- 집중 출발 50%: A와 같은 `HARD_START_TARGETS` 문자열 → 동수원IC 앞 15, 신협 10, 회전교차로 10, 부곡 뒤 5, 출구 직후 5, 고속도로 합류 5
- 양보 위반 감점 2, PPO 20000·3·2e-5, 2만마다 체크포인트, 나머지 보상은 A와 같음
- 이전 A+B 동시 적용(`211523`에서 한 번에, 20판 13~15)과 달리 **A를 먼저 배운 모델에 B를 나중에** 얹음

## 설정

```bash
TEAM14_TOF_JUN_INSIDE=1 JUNCTION_SKIP_SHORT_OVERRIDE=50 \
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 CKPT_EVERY_OVERRIDE=20000 \
PPO_N_STEPS=20000 PPO_N_EPOCHS=3 PPO_LR=2e-5 \
HARD_START_TARGETS_OVERRIDE='1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,-40839116#4@150,-40839116#4@150,-40839116#4@150,-40839116#4@150,568664967#4@100,568664967#4@100,568664967#4@100,568664967#4@100,51066582#1@300,51066582#1@300,1250775757@300,1250775757@300,474882669#1-AddedOnRampEdge@300,474882669#1-AddedOnRampEdge@300' \
python3 -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train --steps 100000 --hard-start-prob 0.5 \
  --init-model results/run_20261126_023012_tof_route_outcome_ft_s0/model.pt
```

## 학습 보상

| 스텝 | 학습 보상 |
|---:|---:|
| 2만 | −12.5 |
| 4만 | +34.0 |
| 6만 | +39.4 |
| 8만 | +48.1 |
| 10만 | +28.5 |

학습 보상이 가장 높은 8만이 평가에서는 동수원IC 출구 망각으로 나빴음 → 체크포인트는 평가로 골라야 함.

## 체크포인트별 20판 (시드 955703411~955703430, A·B 켜고 평가)

결과 파일: `checkpoints/model_<스텝>_eval10_seed*.json` (10판씩, 같은 20판). 최종 `model.pt` = `checkpoints/model_100000.pt` (쓰지 말 것)

| 모델 | 완주 | 실패 |
|---|---:|---|
| A 8만 (시작 모델) | 18 | 신협 1, 회전교차로 신호 위반 1 |
| 2만 | 16 | 회전교차로 충돌 2, 고속도로 합류 1, `206488704` 1 |
| **4만** | **19** | 신협 좌회전 1 |
| 6만 | 18 | 신협 1, 회전교차로 앞 신호 위반 1 |
| 8만 | 9 | **동수원IC 출구 놓침 9**, 신협 1, 신호 위반 1 |
| 10만 | 1 | **동수원IC 출구 놓침 16**, 신협 2, 회전교차로 1 |

동수원IC 앞 출발 15%로도 A 학습에 이어 누적 14만~18만 스텝째에 출구 망각이 다시 나옴.

## 무작위 시드 100판: 4만 (A 8만과 같은 판)

- 시드: `../run_20261126_023012_tof_route_outcome_ft_s0/rand100_seeds.txt`. 판마다 `np.random.seed(시드)` 후 SUMO 새로 시작 (`evaluate.py --independent-seeds` 한 판과 같음)
- 판별 결과: `checkpoints/model_40000_eval100_rand_seeds.csv`

| 결과 | 위치 | A 8만 | **A+B 4만** |
|---|---|---:|---:|
| **완주** | | 86 | **92** |
| 충돌 | 회전교차로 진입 `:4582364294_0` | 5 | 1 |
| 충돌 | 회전교차로 안 `:4582364295_4` | 2 | 1 |
| 충돌 | 회전교차로 `568664967#4` | 1 | 0 |
| 충돌 | 회전교차로 앞 `496583281#0` / `#1` | 1 | 1 |
| 신호 위반 | 회전교차로 뒤 `488779086#1` | 2 | 0 |
| 충돌 | 신협오거리 좌회전 `:1681517542_9` | 0 | 3 |
| 충돌 | 신협오거리 진입로 `-472043938#1` | 1 | 0 |
| 충돌 | 고속도로 합류 가속 차로 `474882669#1` | 1 | 0 |
| 이탈 | 동수원IC 갈림길 `377057231` | 1 | 1 |
| 충돌 | 도착 직전 교차로 `:12702213665` | 0 | 1 |
| 평균 속도 | | 48.3 km/h | 49.1 km/h |

- 회전교차로 주변 실패 11 → 3, 신호 위반 2 → 0 (B가 노린 곳)
- 신협 좌회전 충돌 0 → 3 (B 4만 단독 평가에서도 신협이 늘었음)
- 같은 판 비교: A+B만 완주 13판, A 8만만 완주 7판, 둘 다 실패 1판. 엇갈린 20판의 부호 검정 양측 p ≈ 0.26이라 92 대 86은 아직 확실한 차이라고 보기 어려움
