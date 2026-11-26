# 관측 A + B 동시 적용 8만 스텝 (11/26, 김수아 PC) — 20판 완주 13 (시작 모델 16보다 낮음)

- 시작 모델: `results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt` (모델 A·B와 같은 출발점)
- 코드: `098555c` 그대로 (코드 변경 없음)
- 지도: map6 + 진출 램프 수정, SUMO 1.28.0 (Windows, pip `eclipse-sumo==1.28.0`)
- **평가할 때도 `TEAM14_TOF_JUN_INSIDE=1`, `JUNCTION_SKIP_SHORT_OVERRIDE=50`을 둘 다 켜야 함**

## 바꾼 것

모델 A 학습(`run_20261126_023012`)의 설정에 관측 방안 B만 더함. 나머지는 A와 같음.

| 항목 | 값 |
|---|---|
| 관측 A | 교차로 안 관측 유지 (`TEAM14_TOF_JUN_INSIDE=1`) |
| 관측 B | 짧은 도로 너머 교차로 관측 (`JUNCTION_SKIP_SHORT_OVERRIDE=50`) |
| PPO | `n_steps` 20000, `n_epochs` 3, `lr` 2e-5, 8만 스텝, 2만마다 체크포인트 |
| 집중 출발 | 50%: 동수원IC 앞 차로 감소 15, 신협 10, 회전교차로 10, 부곡 영업소 뒤 5, 출구 직후 합류 5, 고속도로 합류 5% (A 배분) |
| 양보 위반 감점 | 2 (A 값. B 학습은 5) |

## 설정

```bash
TEAM14_TOF_JUN_INSIDE=1 JUNCTION_SKIP_SHORT_OVERRIDE=50 \
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 CKPT_EVERY_OVERRIDE=20000 \
PPO_N_STEPS=20000 PPO_N_EPOCHS=3 PPO_LR=2e-5 \
HARD_START_TARGETS_OVERRIDE='1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,-40839116#4@150,-40839116#4@150,-40839116#4@150,-40839116#4@150,568664967#4@100,568664967#4@100,568664967#4@100,568664967#4@100,51066582#1@300,51066582#1@300,1250775757@300,1250775757@300,474882669#1-AddedOnRampEdge@300,474882669#1-AddedOnRampEdge@300' \
python -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train --steps 80000 --hard-start-prob 0.5 \
  --init-model results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt
```

## 학습 보상

| 스텝 | 학습 보상 | 양보 위험 진입 횟수 |
|---:|---:|---:|
| 2만 | +25.7 | 17 |
| 4만 | +27.3 | 17 |
| 6만 | +35.1 | 11 |
| 8만 | +27.8 | 18 |

## 체크포인트별 20판 (시드 955703411~955703430, A·B 켜고 평가)

결과 파일: `checkpoints/model_<스텝>_eval20_seed955703411.json`. 최종 `model.pt` = 8만.

| 모델 | 완주 | 신협 충돌 (`:1681517542`) | 회전교차로 충돌 (`:4582364294`) | 신호 위반 | 부곡 영업소 뒤 이탈 (`377057231`) | 그 외 |
|---|---:|---:|---:|---:|---:|---|
| `211523` (시작 모델, A·B 없이, 이 PC) | 16 | 0 | 1 | 1 | 1 | 출구 직후 합류 이탈 1 |
| 2만 | 15 | 1 | 0 | 0 | 2 | 충돌 `493209391#2` 1, 출구 직후 합류 이탈 1 |
| 4만 | 14 | 0 | 2 | 0 | 4 | |
| 6만 | 14 | 2 | 2 | 0 | 2 | |
| 8만 | 13 | 1 | 1 | 2 | 2 | 출구 직후 합류 이탈 1 |

참고 (저장소 기록, 같은 20판): 모델 A 8만 18, 모델 B 4만 18 / 8만 17.

## 읽는 법

- 네 체크포인트 모두 시작 모델(16)보다 완주가 적음. A만(18), B만(18)보다도 적음.
- 20판이라 1~2판 차이는 편차 범위. 다만 2만 → 8만으로 갈수록 15 → 13으로 내려감.
- 신협·회전교차로 충돌이 A·B를 각각 켰을 때보다 줄지 않음. 원인(두 관측이 겹치는 구간에서 값이 어떻게 바뀌는지)은 추적하지 않음.
- 같은 시작 모델이 이 PC의 SUMO 1.27.1에서는 18/20, 1.28.0에서는 16/20. 저장소 기록(16)과 완주 수는 같고 실패 판의 종류는 일부 다름.
