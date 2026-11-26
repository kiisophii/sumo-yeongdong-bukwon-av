# checkpoints/model_40000.pt 100판 평가 (무작위 시드, SUMO 1.28.0) — 관측 방안 B

- 모델: `checkpoints/model_40000.pt` (211523에서 이어 4만, 관측 방안 B `JUNCTION_SKIP_SHORT_OVERRIDE=50`, 양보 위반 감점 5, PPO 20000·3·2e-5)
- 지도: map6 + 진출 램프 수정, 신호 연동 패치 없음. SUMO·libsumo 1.28.0 (pip)
- 평가 환경변수: JUNCTION_SKIP_SHORT_OVERRIDE=50 YIELD_PENALTY_OVERRIDE=5 SPAWN_CLEAR_OVERRIDE=0 LANE_ENTROPY_OVERRIDE=0.02 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0
- 시드: 211523 100판 평가(`results/run_20261125_211523_tof_route_outcome_ft_s0/EVAL100.md`)와 같은 무작위 시드 100개. 판별 결과 `model_40000_eval100_random_seeds.csv`

## 결과 (211523과 같은 100판)

| 결과 | 211523 | B 4만 |
|---|---:|---:|
| **완주** | **82** | 68 |
| 신협 교차로 충돌 | 7 | 13 |
| 의왕역 회전교차로 충돌 | 3 | 8 |
| 회전교차로 앞뒤 신호 위반 | 2 | 3 |
| 동수원IC 출구 이탈 (377057231) | 2 | 4 |
| 합류 정체 충돌 (1307152438) | 3 | 1 |
| 기타 (동수원IC 진출로, 고속도로 합류, 부곡 뒤 갈림길, 11.5 km) | 1 | 4 |
| 평균 속도 | 50.7 km/h | 47.7 km/h |

판별: 둘 다 완주 60, 211523만 완주 22, B 4만만 완주 8.
같은 시드 20판(955703411~)에서는 B 4만 18 대 211523 16이었지만 100판에서는 반대. 방안 B가 노린 신협·회전교차로 실패가 오히려 늘어(10 → 21) 4만 스텝으로는 바뀐 관측에 적응하지 못한 것으로 보임. 최종 후보는 211523 유지.
