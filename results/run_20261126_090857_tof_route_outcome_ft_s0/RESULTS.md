# A'+B+C sequence 모델 (4만) — A' 6만에 B 켜고 동수원IC 20%로 이어 학습

**최종 후보: `model_ApBC_seq_40000.pt`** (= `checkpoints/model_40000.pt`)

- 계보: A 8만(023012) → A' 6만(073700, 4갈래 신협 지도) → **B 켜고 이어 4만** → 평가 때 C 켬
- C(`TEAM14_FOE_UPSTREAM_M=40`, `d54cf10`)는 학습 없이 평가에서만 켬. C는 관측 칸 뜻을 바꾸지 않고 회전교차로 짧은 진입로의 교차 차량을 더 일찍 +1로 보여 줌
- 지도: map6 + 진출 램프 수정 + **신협오거리 4갈래**(`92753ee`), SUMO 1.28.0, 신호 연동 패치 없음
- **평가할 때 A·B·C 모두 켜야 함**: `TEAM14_TOF_JUN_INSIDE=1 JUNCTION_SKIP_SHORT_OVERRIDE=50 TEAM14_FOE_UPSTREAM_M=40`

## 학습 설정

- 시작 모델: `results/run_20261126_073700_tof_route_outcome_ft_s0/checkpoints/model_60000.pt`
- 관측: A·B 켬 (C는 학습 때 끔)
- 집중 출발 50%: **동수원IC 앞 20**, 신협 10, 회전교차로 7.5, 부곡 뒤 5, 출구 직후 5, 고속도로 합류 2.5
- PPO 20000·3·2e-5, 양보 위반 감점 2, 8만 스텝 (2만마다 체크포인트)
- 학습 보상: 2만 +18.6 / 4만 +27.9 / 6만 +16.6 / 8만 +27.3

```bash
TEAM14_TOF_JUN_INSIDE=1 JUNCTION_SKIP_SHORT_OVERRIDE=50 YIELD_PENALTY_OVERRIDE=2 SUMO_USE_LIBSUMO=1 PYTHONIOENCODING=utf-8 \
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 CKPT_EVERY_OVERRIDE=20000 \
PPO_N_STEPS=20000 PPO_N_EPOCHS=3 PPO_LR=2e-5 \
HARD_START_TARGETS_OVERRIDE='1116479399@300 ×8, -40839116#4@150 ×4, 568664967#4@100 ×3, 51066582#1@300 ×2, 1250775757@300 ×2, 474882669#1-AddedOnRampEdge@300 ×1 (쉼표로 펼쳐 20개)' \
python3 -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train --steps 80000 --hard-start-prob 0.5 \
  --init-model results/run_20261126_073700_tof_route_outcome_ft_s0/checkpoints/model_60000.pt
```

## 같은 20판 (955703411~, A·B 켜고 C 끔)

| 체크포인트 | 완주 | 동수원IC 출구 놓침 | 그 외 |
|---|---:|---:|---|
| 2만 | 15 | 0 | 회전교차로 앞 1, 신협 1, 회전교차로 뒤 신호 위반 1, 회전교차로 진입 1, 진출 램프 1 |
| **4만** | **17** | 0 | 신협 1, 신호 위반 1, `493209391#2` 1 |
| 6만 | 17 | 0 | 신협 1, 신호 위반 1, 회전교차로 진입 1 |
| 8만 | 8 | 6 | 회전교차로 진입 3, 회전교차로 앞 2, 고속도로 합류 1 |

비교: 같은 시작 모델에서 A 배율(동수원IC 15%)로 학습한 `run_20261126_083655`는 2만 8 / 4만 0 / 6만 4 / 8만 0 (출구 놓침 11·17·12·15). 동수원IC 20%로 6만까지 출구 망각 없음.
8만 체크포인트·최종 model.pt(=8만)는 출구 망각이 다시 생겨 이 커밋에서 뺌.

## 무작위 100판 (A·B·C 켬)

진행 중 — 결과는 뒤 커밋에 추가.
