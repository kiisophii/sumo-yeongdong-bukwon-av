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

### 결과 (100판) — 완주 91, 충돌 2 (평균 53.0 km/h)

판별 csv: `.../checkpoints/model_40000_eval100C_noshin_rand_seeds.csv`

| 종료 | 판 수 | 위치 |
|---|---:|---|
| **완주** | **91** | |
| 경로 이탈 | 3 | 동수원IC `377057231_2` 2, 고속도로 합류 가속 차로 1 |
| 신호 위반 | 3 | 회전교차로 앞 신호 `496583281#0` 2, `#1` 1 |
| 차량 충돌 | 2 | `:12702213665` 1, 회전교차로 진입 `:4582364294_0` 1 |
| 순간이동 | 1 | 회전교차로 진입 `:4582364294_0_1` |

참고: 같은 모델(A·B·C, 4갈래)의 60k 체크포인트를 기존 경로로 돌린 100판은 완주 79(신협 충돌 5). 4만 기존 경로 100판은 돌리지 않아 같은 모델끼리 직접 비교는 아님.

- 신협 충돌은 경로에서 빠져 0.
- 회전교차로 앞 신호 위반이 새로 생김: 철도박물관로를 30~40 km/h로 직진하다 바로 신호에 닿음(기존 경로는 신협 좌회전으로 감속한 뒤 도착). 새 경로로 학습하지 않은 모델이라 생긴 것으로 보임.

## 회전교차로 안 충돌 추적 (300판 평가 중 `:4582364295_4` 충돌 시드 3개)

시드 1106095166, 1560878888, 658970132 모두 같은 원인:
- 회전교차로를 나가던 트럭(`f_bugok_central_straight.13`)이 동쪽 출구 `452597718#0`(길이 **5.3 m**, 끝에 신호 `4931777214`)에서 빨간불에 서면서 **꼬리가 링 위에 걸침**
- 우리 차(링 위, 우선)는 8.6~9.6 m/s로 가속 중 트럭 꼬리를 들이받음 (collider = ego, victim 속도 0.5~1.4 m/s, type junction)
- 관측: 앞차 칸 [1, 1](없음), 교차로 칸 [1, −1, −1]. ToF가 차를 **중심점 하나**로 차로에 배정하는데 트럭 중심은 출구 도로 위라 내 차로에서 빠짐

## 차체 기준 차로 판정 `TEAM14_TOF_BODY_LANES=1` (기본 0 꺼짐, `env/tof_observation.py`)

- 중심점이 들어가지 않은 차로라도 차체 점(앞뒤 끝 2개 + 모서리 4개, 폭 2.0 m 가정)이 그 차로 폭 안에 있으면 그 차로를 막는 차로 봄. 모서리는 경계에서 0.3 m 안쪽에 들어와야 침(옆 차로 차를 괜히 앞차로 잡지 않게)
- 거리 = 차로 안에 들어온 가장 가까운 점까지 − 내 길이/2. 관측 칸 수·뜻은 그대로(41칸)
- 실제 센서는 차체 표면을 보므로 센서 모델을 현실에 맞추는 변경
- 확인(학습 없음, A'+B+C 4만, 우회 경로, A·B·C + BODY 켬): 위 3개 시드 모두 회전교차로 통과. 1560878888·658970132는 완주, 1106095166은 4.0 km 고속도로 합류 가속 차로에서 이탈(다른 원인)
