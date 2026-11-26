# A 적용 전 모델(211523)에서 A+B+C 한 번에 8만 (11/26, 4갈래 지도) — 4만 100판 81

- 시작 모델: `results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt` (A 적용 전, 옛 지도 20판 16 / 무작위 100판 82)
- 관측: A + B + C 한 번에 (`TEAM14_TOF_JUN_INSIDE=1`, `JUNCTION_SKIP_SHORT_OVERRIDE=50`, `TEAM14_FOE_UPSTREAM_M=40`)
- 지도: 4갈래 신협(`92753ee`) + map6 + 진출 램프 수정, 기존 경로(신협 지남), SUMO 1.28.0
- 집중 출발 50%: A'+B+C 순차 학습(`run_20261126_090857`)과 같음 — 동수원IC 앞 20, 신협 10, 회전교차로 7.5, 부곡 뒤 5, 출구 직후 5, 고속도로 합류 2.5
- 양보 위반 감점 2, PPO 20000·3·2e-5, 8만, 2만마다 체크포인트

```bash
TEAM14_TOF_JUN_INSIDE=1 JUNCTION_SKIP_SHORT_OVERRIDE=50 TEAM14_FOE_UPSTREAM_M=40 \
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 CKPT_EVERY_OVERRIDE=20000 \
PPO_N_STEPS=20000 PPO_N_EPOCHS=3 PPO_LR=2e-5 \
HARD_START_TARGETS_OVERRIDE='1116479399@300 ×8, -40839116#4@150 ×4, 568664967#4@100 ×3, 51066582#1@300 ×2, 1250775757@300 ×2, 474882669#1-AddedOnRampEdge@300 ×1 (쉼표로 펼쳐 20개)' \
python3 -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train --steps 80000 --hard-start-prob 0.5 \
  --init-model results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt
```

## 학습 보상

| 스텝 | 2만 | 4만 | 6만 | 8만 |
|---|---:|---:|---:|---:|
| 학습 보상 | +16.7 | +27.7 | +22.8 | +26.3 |

## 무작위 100판 (`rand100_seeds.txt`, A+B+C 켜고, 4갈래 지도, 기존 경로)

| 체크포인트 | 완주 | 비고 |
|---|---:|---|
| 4만 | **81** | 판별 `checkpoints/model_40000_eval100_rand_seeds.csv` |
| 6만 | 76 / 94 | 사용자 지시로 94판에서 중단 (csv 없음) |
| 8만 | – | 평가 안 함 |

4만 실패 19: 동수원IC 갈림길 이탈 `377057231_2` 4, 신협 좌회전 `:1681517542_4` 3, 고속도로 합류 이탈 2, 그 외 충돌 10(회전교차로 3, 동수원IC 진출로·출구 직후 합류·합류 정체·고속도로 본선·광교로 등 1씩).

같은 100판 비교: A' 6만 87, A'+B+C 순차 4만 82, A 8만(옛 지도) 86, A+B 4만(옛 지도) 92. → 세 관측을 한 번에 켜고 학습하는 것은 순서대로 얹는 것보다 낫지 않음.
