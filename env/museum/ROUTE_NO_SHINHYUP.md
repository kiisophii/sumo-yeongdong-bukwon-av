# 신협오거리 우회 경로 (no 신협, 11/26)

켜는 법: `TEAM14_ROUTE_NO_SHINHYUP=1` (기본 0 = 기존 경로 `route_check.json`). 켜면 `env/road_config.py`가 `ego_edges_file`을 `env/museum/route_no_shinhyup.json`으로 바꾼다. 도로망은 처음 실행 때 자동으로 다시 만들어진다(`env/sumo/museum`, build.stamp).

## 어떤 길로 가나

- 기존: 주차장 → 철도박물관로 **남쪽**(우회전) → 부곡초등길 → 부곡중앙남1길 → **신협오거리 좌회전** → 부곡시장길 → 회전교차로 앞 신호 → 의왕역 회전교차로
- 우회: 주차장 → 철도박물관로 **북쪽**(좌회전) 직진 0.71 km → 회전교차로 앞 신호 → 의왕역 회전교차로 → 이후 기존과 같음

| edge | 이름 | 길이 | 누적 | 끝 교차로 |
|---|---|---:|---:|---|
| `-156791015` | 주차장 | 131 m | 0 | priority |
| `-496583280#5` | 철도박물관로 | 254 m | 131 | priority |
| `-496583280#4` | 철도박물관로 | 144 m | 385 | priority |
| `-496583280#3` | 철도박물관로 | 182 m | 529 | priority |
| `-496583280#1` | 철도박물관로 | 13 m | 711 | priority (부곡시장길 합류점, 우리가 주도로) |
| `496583281#0` | 철도박물관로 | 24 m | 724 | 신호 `4931777208` |
| `496583281#1` | 철도박물관로 | 10 m | 748 | 회전교차로 진입 양보 |

- 기존 72개 edge 중 앞 17개(신협 구간)를 철도박물관로 4개로 바꿈. 경로 60개 edge.
- 회전교차로까지 805 m → 759 m, 전체 13.53 km 그대로.
- 신협오거리는 배경 교통이 계속 지나므로 지도에 남아 있음. 우리 차만 안 지남.
- 주의: 철도박물관로 북쪽 0.7 km는 배경 교통 0대(옆길도 도로 정리로 빠짐) → 회전교차로 앞 신호 전까지 상호작용 없음. 배경 흐름 추가 여부 미정.
- 주의: OSM 기준. 주차장 → 북쪽 좌회전 가능 여부·양방향 1차로 여부는 로드뷰 확인 필요.
- 집중 출발 목록의 신협 항목(`-40839116#4@150`)은 이 경로에 없으므로 학습 때 빼야 함.

## 평가: A'+B+C sequence 4만, 우회 경로 100판 (`rand100_seeds.txt`)

- 모델: `results/run_20261126_090857_tof_route_outcome_ft_s0/checkpoints/model_40000.pt` (새 경로 학습 없음)
- 판별 json: `.../checkpoints/model_40000_eval100C_noshin_runs/seed<시드>.json` (판마다 `evaluate --episodes 1 --seed <시드>`, `--independent-seeds`)
- 환경변수:

```bash
TEAM14_ROUTE_NO_SHINHYUP=1 TEAM14_TOF_JUN_INSIDE=1 JUNCTION_SKIP_SHORT_OVERRIDE=50 TEAM14_FOE_UPSTREAM_M=40 \
SUMO_USE_LIBSUMO=1 PYTHONIOENCODING=utf-8 YIELD_PENALTY_OVERRIDE=2 \
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 \
python3 -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py evaluate \
  --model results/run_20261126_090857_tof_route_outcome_ft_s0/checkpoints/model_40000.pt --episodes 1 --seed <시드>
```

(D `TEAM14_CROSS_GAP_W`는 끔. 4갈래 신협 지도, SUMO 1.28.0)

### 중간 결과 (63/100판, 진행 중)

| 종료 | 판 수 | 위치 |
|---|---:|---|
| 완주 | 55 | |
| 경로 이탈 | 3 | 동수원IC `377057231_2` 2, 고속도로 합류 가속 차로 1 |
| 신호 위반 | 3 | 회전교차로 앞 신호 `496583281#0` 2, `#1` 1 |
| 충돌 | 2 | `:12702213665` 1, 회전교차로 진입 `:4582364294_0` 1 |

- 신협 충돌은 경로에서 빠져 0.
- 회전교차로 앞 신호 위반이 새로 생김: 철도박물관로를 30~40 km/h로 직진하다 바로 신호에 닿음(기존 경로는 신협 좌회전으로 감속한 뒤 도착). 새 경로로 학습하지 않은 모델이라 생긴 것으로 보임.
