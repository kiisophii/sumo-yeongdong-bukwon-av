# model.pt 100판 평가 (무작위 시드, SUMO 1.28.0)

- 모델: `results/run_20261125_211523_tof_route_outcome_ft_s0/model.pt` (망각 완화 16만, 커밋 5a379e8)
- 지도: map6 + 진출 램프 수정 (5b867b8, 4d87133). 도로망을 SUMO 1.28.0 netconvert로 다시 빌드, `468241513.180` 확인
- SUMO: eclipse-sumo · libsumo 1.28.0 (pip)
- 평가 환경변수: SPAWN_CLEAR_OVERRIDE=0 LANE_ENTROPY_OVERRIDE=0.02 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0
- 시드: 무작위 100개 (연속 시드 아님). 판마다 `np.random.seed(시드)` 후 reset, 결정적 정책 = `tools/evaluate.py --independent-seeds`로 그 시드 한 판을 돌린 것과 같은 방식
- 판별 결과: `model_eval100_random_seeds.csv` (seed, steps, return, end_reason, end_lane, end_route_km, mean_speed_mps)

## 결과

| 결과 | 위치 | 차로 | 판 수 |
|---|---|---|---:|
| **완주** | 광교박물관 주차장 | | **82** |
| 충돌 | 0.7 km 신협 교차로 `:1681517542` | 0번 | 7 |
| 충돌 | 7.5~9.6 km 합류 정체 `1307152438` | 3번 | 3 |
| 충돌 | 0.8 km 의왕역 회전교차로 (`:4582364294` 2, `568664967#0` 1) | 0번 | 3 |
| 신호 위반 | 0.8 km 회전교차로 앞 신호 `496583281#1` | 0번 | 2 |
| 경로 이탈 | 11.7 km 동수원IC `377057231` | 2번 | 2 |
| 충돌 | 11.9 km 동수원IC 진출로 `50981102` | 1번 | 1 |

평균 속도 50.7 km/h. 진출 램프·출구 직후 합류·부곡 영업소 실패 0.
남은 실패 18판 중 12판이 출발 직후 0.7~0.8 km (신협 7, 회전교차로 3, 신호 위반 2).

## 신호 위반 원인 (참고, 191050 모델로 확인)
회전교차로 앞 신호(`496583281#0` 끝)와 뒤 신호(`488779086#0` 끝, 약 44 m 뒤)가 둘 다 초록 84 s · 노랑 5 s · 빨강 1 s, 오프셋 0으로 동시에 바뀜.
앞 신호를 초록 끝에 통과하면 뒤 신호는 이미 노랑이고, 약 68 m 앞 노랑(정지거리 약 13 m)에서 정책이 가속해 도착 때 빨강이 됨.
