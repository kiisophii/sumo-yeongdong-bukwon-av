# 데이터 칼럼 검토 요청 — 14조 (2026-11-27)

수집 조건(확정): map5 이어 학습 20만 체크포인트 · 지도 map6b · 신협오거리 지나는 기존 경로 · SUMO 1.28.0 · 관측 coarse 37칸.
아래는 구성안이 아니라 **시험 수집 3판(기존 경로, 7,216스텝) 파일에 실제로 저장된 칼럼**이다. 1스텝 = 0.5초.
11/27 갱신: 5절의 2~4번과 값 칼럼 2개(`value_pred`, `return_to_go`)를 수집 코드에 반영했다.

검토해 줄 것: (1) 빠진 칼럼, (2) 빼도 되는 칼럼, (3) 5절의 남은 결정 2개.
수집 뒤에 칼럼을 빼는 것은 가능하고, 추가하는 것은 재수집이 필요하다.

---

## 1. 스텝마다 저장되는 것 (JSONL 한 줄 = 1스텝)

### 1-1. 과제 필수 항목

| 칼럼 | 형태 | 내용 |
|---|---|---|
| `episode`, `t` | 정수 | 판 번호, 판 안의 스텝 번호 |
| `observation` | 실수 37칸 | 모델이 받은 관측 (2절) |
| `action_raw` | 실수 2칸 | 모델 출력 [가감속, 차선변경], 각 −1~1 |
| `action.accel_raw`, `action.lane_change_raw` | 실수 | 환경에 전달된 값 |
| `action.lane_change` | 정수 | 차선변경 명령 {−1, 0, +1} |
| `action.lane_change_applied` | 참/거짓 | 차선변경이 실제로 실행됐는지 |
| `reward` | 실수 | 그 스텝의 보상 합계 (학습과 같은 설정: 충돌 −30, 완주 +30, 정지 −0.3) |
| `value_pred` | 실수 | 모델 critic이 그 스텝 관측에서 예측한 값 V(o_t) |
| `return_to_go` | 실수 | 그 스텝부터 판 끝까지 실제 보상의 할인 합, G_t = r_t + γ·G_{t+1}, γ = 0.995 |
| `terminated`, `truncated` | 참/거짓 | 환경 종료 / 시간 제한 종료 |
| `state` | 묶음 | SUMO 실제 상태 (1-2, 1-3) |
| `detected_vehicles` | 목록 | 감지 범위 50 m 안 차량 (1-4) |
| `event.collided`, `event.arrived` | 참/거짓 | 충돌, 도착 |
| `event.lane_before`, `event.lane_after` | 정수 | 행동 전후 ego 차로 번호 |
| `next_observation`, `next_state` | — | **판의 마지막 스텝에만 저장** (5절 결정 1) |

### 1-2. `state` — ego (21개)

| 칼럼 | 단위 | 비고 |
|---|---|---|
| `ego_alive` | 참/거짓 | |
| `ego_x`, `ego_y` | m | SUMO 좌표 |
| `ego_speed`, `ego_accel` | m/s, m/s² | |
| `ego_heading` | 도 | |
| `ego_lane` | 정수 | 차로 번호 |
| `ego_lane_id`, `ego_road_id` | 문자열 | SUMO ID |
| `ego_lane_pos` | m | 차로 시작점부터 거리 |
| `ego_distance_m` | m | 출발 후 주행 거리 |
| `ego_route_edge_index` | 정수 | 경로상 몇 번째 도로 |
| `ego_num_lanes` | 정수 | 현재 도로 차로 수 |
| `ego_lane_remaining_m` | m | 내 차로 끝까지 |
| `speed_limit_mps` | m/s | 구간 제한속도 |
| `allowed_speed_mps` | m/s | SUMO가 그 순간 허용한 속도 |
| `signal_distance_m` | m | 앞 신호까지. 없으면 −1 |
| `signal_green`, `signal_yellow`, `signal_red` | 0/1 | 신호 색을 칸으로 나눔 (조교님 답변 반영) |
| `signal_remaining_s` | 초 | 현재 색이 남은 시간 |
| `lead_gap_m`, `lead_speed_mps` | m, m/s | 같은 차로 앞차. 없으면 −1 |

### 1-3. `state.vehicles` — ego 주변 다른 차량 (스텝당 평균 18대, 최대 58대)

`id`, `x`, `y`, `speed`, `lane`, `lane_id`, `road_id`, `lane_pos`, `accel`, `heading`, `length`, `flow_index`(어느 교통 흐름인지 번호), `route_edge_number`(ego 경로 위면 그 번호, 아니면 −1)

### 1-4. `detected_vehicles` — 감지된 차량 (스텝당 평균 2.4대, 최대 14대)

`id`, `x`, `y`, `rel_pos`(ego 기준 앞뒤 거리), `speed`, `lane_offset`(ego 차로 기준 차로 차이)

### 1-5. `event` 확장 (11개)

| 칼럼 | 형태 | 내용 |
|---|---|---|
| `end_reason` | 정수 | 0 진행 중, 1 도착, 2 차량 충돌, 3 경로 이탈, 4 신호 위반, 5 순간이동, 6 시간 초과, 7 정체, 8 차량 제거 |
| `end_lane` | 문자열 | 끝난 차로. 진행 중이면 null |
| `vehicle_collision`, `red_light`, `lane_end`, `teleported` | 참/거짓 | 종료 종류별 |
| `yield_violation` | 참/거짓 | 양보해야 하는데 교차 차량이 올 때 진입 |
| `lane_change_blocked` | 문자열 | 차선변경이 실행되지 않은 이유. 없으면 null |
| `lane_change_blocked_code` | 정수 | 0 없음, 1 no_lane(옮길 차로 없음), 2 junction(교차로 안), 3 unsafe(안전 간격 부족), 4 route(경로 이탈 방향), 5 reverse |
| `action_executed` | 실수 2칸 | 실제 실행된 [가감속, 차선변경] |
| `overspeed` | 참/거짓 | 제한속도 초과 |

### 1-6. `reward_terms` — 보상 구성 항

매 스텝 12개 고정 칸으로 저장한다. 발생하지 않은 항은 0. 전 스텝에서 항의 합 = `reward` 확인함.

`speed`, `overspeed`, `idle`, `stop_shaping`, `close_gap`, `blocked`, `lane_change`, `invalid_action`, `yield`, `red_light`, `collision`, `arrival`

- 경로 이탈로 끝난 스텝의 −30은 `collision` 칸에 들어간다(환경 코드가 차량 충돌과 같은 항으로 처리). 구분은 `event.end_reason`으로 한다.
- `stop_shaping`, `blocked`, `lane_change`, `invalid_action`은 이 모델의 학습 설정에서 가중치가 0이라 항상 0이다.

### 1-7. `derived` — 관측에서 계산한 값 (6개)

`lane_end_remaining_m`, `fork_distance_m`, `fork_direction`(−1/0/+1), `junction_distance_m`, `junction_must_yield`, `junction_cross_traffic`
주의: SUMO 실제 값이 아니라 모델 관측 칸(21~23, 34~36)을 단위만 되돌린 값이다. 갈림길·양보 교차로 정보는 `state`에는 없고 여기에만 있다.

## 2. 관측 37칸

조건: `TEAM14_ROUTE_OBS=coarse` 켬, `TEAM14_JUN_INSIDE`·`TEAM14_TOF_OBS` 끔. 이 조건이 아니면 같은 37칸이어도 21~25칸의 의미가 달라진다. 칸 순서는 윤호님이 코드와 대조해 확인했다.

| 칸 | 내용 | 단위·값 |
|---|---|---|
| 0 | 내 속도 | / 27.78 m/s |
| 1~20 | 5개 차로(좌2 → 좌1 → 현재 → 우1 → 우2) × (앞차 거리, 앞차 상대속도, 뒤차 거리, 뒤차 상대속도) | 거리 / 50 m (뒤차 거리는 음수), 상대속도 / 27.78 m/s. 앞차 없으면 [1, 1], 뒤차 없으면 [−1, −1] |
| 21 | 내 차로가 50 m 안에 끝나는지 | 남은 거리 / 50 m |
| 22, 23 | 다음 갈림길까지 거리, 방향 | / 600 m, 오른쪽 +1 · 왼쪽 −1 · 없음 0 |
| 24 | 허용속도 (SUMO `getAllowedSpeed`, `state.allowed_speed_mps`와 같음) | / 27.78 m/s |
| 25 | 내 속도 − 허용속도 (비율이 아니라 차이) | / 27.78 m/s |
| 26~30 | 5개 차로 앞쪽 차량 밀도 | 50 m 구간 |
| 31~33 | 신호까지 거리, 색, 남은 시간 | / 150 m, 녹색·없음 +1 · 황색 0 · 적색 −1, / 30초 (0~1로 잘림, 신호 없으면 1) |
| 34~36 | 양보 교차로까지 거리, 양보 의무, 교차 차량 접근 | / 150 m, ±1, ±1. 교차로 없으면 [1, −1, −1] |

- 21~23칸은 교차로 안에서는 직전 값을 유지한다.
- ego가 사라지며 끝난 판은 마지막 스텝의 `next_observation`이 전부 0이다.

## 3. 판마다 한 번 저장되는 것

- `episode_meta` (첫 스텝): `seed`, `route_name`(orange/blue), `route_estimates`(출발 전 두 경로 예상 시간), `disrupted_route`, `hard_start`, `route_edges`(경로 도로 수), `model`, `policy`, `stochastic`, `detour_no_shinhyup`
- `episode_summary` (마지막 스텝): `end_reason`, `end_reason_name`, `end_lane`, `steps`, `return`, `distance_m`
- 11/27 추가: `sumo_version`, `map_version`, `traffic_vehs_per_hour`, `step_seconds`, `gamma`, `reward_config`(충돌 30, 완주 30, 막힘 0, 정지 0.3, 과속 가중치 1.0)

## 4. NPZ (학습에 바로 쓰는 배열)

`observation`(N×37), `action_raw`(N×2), `lane_change`, `reward`, `next_observation`(N×37), `terminated`, `truncated`, `episode`, `t`, `end_reason`, `speed_mps`, `allowed_speed_mps`, `distance_m`, `lead_gap_m`, `signal_onehot`(N×3), `seed`, `value_pred`, `return_to_go`, `detected_xy`, `detected_offsets`

NPZ에는 `next_observation`이 전 스텝에 들어 있다.

## 5. 결정이 필요한 것

| # | 지금 상태 | 제안 |
|---|---|---|
| 1 | JSONL의 `next_observation`·`next_state`는 판의 마지막 스텝에만 저장. 다음 줄의 `observation`·`state`와 같아서 생략했고, 복원 함수(`iter_transitions`)가 수집 코드에 있음 | 그대로 두고 README에 명시 (전 스텝에 넣으면 용량이 약 2배). 필수 항목이라 감점이 걱정되면 전 스텝 저장으로 변경 |
| 2 | 행동이 결정적(6절) | 그대로 수집할지, 무작위성을 넣을지 팀 결정 |

반영 완료(11/27): 보상 항 고정 칸, 차선변경 막힘 숫자 코드, 판 정보에 SUMO·지도·교통량 추가, ego 중복 번호 삭제, `value_pred`·`return_to_go` 추가.

## 6. 수집 중 알아둘 사실

- **행동은 결정적(stochastic = false)**: 평가와 같은 방식으로, 모델 출력의 평균값을 그대로 쓴다. 판마다 다른 것은 시드(교통 흐름)뿐이다. 행동에 무작위성을 넣어 수집할지는 팀 결정.
- **차선변경 명령의 90%가 실행 불가**: 7,216스텝 중 6,493스텝에서 `lane_change_blocked = no_lane`(옮겨 갈 차로가 없는데 차선변경 출력). `action.lane_change`와 `action.lane_change_applied`를 같이 봐야 한다.
- **용량**: 압축 전 1스텝 약 6.5 KB 중 `state`가 5.3 KB(대부분 `state.vehicles`). 압축 후 1스텝 705 B → 10⁷개면 JSONL 약 7 GB + NPZ 약 1 GB. LMS(700 MB)에는 일부만, 전체는 Hugging Face.
- **시험 조건**: 기존 경로(신협 통과 확인) 3판, 시드 700000~700002. 결과는 완주 2판, 경로 이탈 1판.
- **`return_to_go` 주의**: 시간 제한(`truncated`)으로 끝난 판은 그 뒤 보상이 빠져 실제보다 작다. 3판에서 `value_pred`와 `return_to_go`의 상관계수는 0.39였다.
- **보상 설정**: 수집 코드는 기본값(충돌 −5, 완주 +2)으로 보상을 기록하고 있었다. 학습 명령과 같은 값(−30, +30, 정지 −0.3)을 옵션으로 주도록 고쳤다. 수집 명령에 이 옵션을 빼면 안 된다.
- **미확인**: 11/24에 낸 "데이터 칼럼 제출" 내용과 이 구성이 맞는지 대조하지 않았다.

---

## 7. 팀원 검토 반영 (11/27, 윤호님·준희님 의견)

기존 경로 3판(7,216스텝)과 무작위 정책 12판으로 저장을 확인했다.

### 7-1. 추가한 칼럼

| 칼럼 | 위치 | 내용 | 제안 |
|---|---|---|---|
| `policy.accel_mean`, `policy.accel_std` | 스텝 | 가감속 분포의 평균·표준편차 | 준희 |
| `policy.lane_prob_left` / `keep` / `right` | 스텝 | 차선 3개 확률 | 준희 |
| `policy.log_prob` | 스텝 | 실제로 고른 행동의 log π(a\|o) | 준희, 윤호 |
| `value_pred`, `return_to_go` | 스텝 | critic 예측값, 실제 할인 보상 합 (γ = 0.995) | 준희 |
| `state.sim_time_s` | 스텝 | SUMO 시각(초) | 윤호 |
| `state.signal2_distance_m`, `signal2_green/yellow/red` | 스텝 | 앞 신호 다음 신호. 없으면 −1 / 0 | 준희 |
| `state.lane_route_remaining_m` | 스텝 | 현재 도로의 차로별(0번부터) "차선변경 없이 경로를 따라 더 갈 수 있는 거리". 목적지까지 이어지면 99999, 교차로 안이면 빈 목록 | 준희 |
| `episode_summary.collision` | 판 끝 | 차량 충돌이면 종류(`type`, `type_code`), ego가 들이받은 쪽인지, 상대 차 id·흐름 번호·속도, 충돌 차로·위치. 아니면 null | 준희 |
| `episode_meta.env_options` | 판 처음 | `TEAM14_*` 환경변수 전체 | 윤호, 준희 |
| `episode_meta.model_path`, `model_sha256`, `code_commit` | 판 처음 | 모델 경로·해시, 코드 커밋 해시 | 윤호, 준희 |
| `episode_meta.gamma`, `gae_lambda`, `reward_config`, `step_seconds`, `sumo_version`, `map_version`, `traffic_vehs_per_hour` | 판 처음 | 수집 조건 | 윤호, 준희 |

NPZ 추가: `value_pred`, `return_to_go`, `log_prob`, `accel_mean`, `lane_probs`(N×3), `sim_time_s`.

예: 고속도로 진입 가속 차로(`474882669#1-AddedOnRampEdge`) 0번 차로에서 `lane_route_remaining_m = [94.2, 3546.2, 3546.2, 3546.2]`. 지금 차로가 94 m 뒤에 끊기고 옆 차로는 이어진다는 뜻이다.

### 7-2. 넣지 않은 것과 이유

| 제안 | 이유 |
|---|---|
| `advantage`, `entropy`, `dilemma_zone`, `steps_since_lane_change`, `route_km`, `segment`, `max_route_km`, `fail_segment` | 저장된 값으로 수집 뒤에 계산할 수 있다. `route_km`은 `state.ego_distance_m`, `segment`는 `ego_route_edge_index`와 README의 구간 표로 구한다 |
| `lc_gate_tof` / `lc_gate_sumo` | ToF 관측 전용. 이 모델(coarse)은 ToF를 쓰지 않는다. 옆 차로 앞뒤 간격은 관측 1~20칸에 있다 |
| `junction_truth`, `junction_next2_m` | 넣지 않음. coarse 관측의 34~36칸이 SUMO 값으로 계산되는지, 실제 교차 차량과 얼마나 다른지는 확인하지 않았다. 교차 차량의 실제 위치·속도는 `state.vehicles`에 있어 수집 뒤에 계산할 수 있다 |
| `fork_truth` | `lane_route_remaining_m`으로 "지금 차로가 경로로 이어지는지"를 대신한다 |
| `speed_limit_ahead` | 지도에서 고정된 값이라 `ego_route_edge_index`와 위치로 구할 수 있다 |
| `partner_track` | 상대 차 id가 `episode_summary.collision`에 있고, 그 차의 직전 위치는 앞 스텝들의 `state.vehicles`에 있다 |
| `traffic_seed` | `episode_meta.seed`가 SUMO 시드다 |

### 7-3. 윤호님 확인 사항에 대한 답

- 수집 환경: `TEAM14_ROUTE_OBS=coarse` 켬, `TEAM14_JUN_INSIDE`·`TEAM14_TOF_OBS` 끔, `TEAM14_NO_SPEED_CAP=1 TEAM14_OVERSPEED_W=1.0 TEAM14_IDLE_PEN=0.3`. 판마다 `env_options`에 기록된다.
- SUMO 1.28.0 평가: 이미 공식 300판을 돌렸다. 완주 262 (87.3%), 차량 충돌 6 (2.0%).
- `derived`의 "없음": 이미 −1로 저장한다 (관측값이 0.999 이상이면 −1). 시험 3판에서 최댓값은 교차로 68.7 m, 갈림길 599.2 m, 차로 끝 48.5 m.
- 마지막 스텝: ego가 사라진 판은 마지막 `next_observation`이 전부 0이고 `next_state.ego_alive = false`다. README에 적는다.
- 관측 2절에 추가할 설명(차로 순서 좌2→좌1→현재→우1→우2, 뒤차 거리는 음수, 상대속도는 27.78로 나눔, 24칸은 `getAllowedSpeed`, 25칸은 차이, 21~23칸은 교차로 안에서 직전 값 유지, 33칸은 0~1로 잘림, 34~36칸은 교차로 없으면 [1, −1, −1])은 README에 그대로 넣는다.

### 7-4. 결정

- `next_*`: 마지막 스텝에만 저장하고 README에 명시 (윤호님 확인: 과목 문서가 이 방식을 허용).
- 행동: 결정적으로 수집 (윤호님 추천). 결정적 수집에서 `log_prob`는 "평균 가감속과 가장 확률 높은 차선"의 확률이다.

### 7-5. 용량

압축 후 1스텝 705 B → 859 B. 10⁷개면 JSONL 약 8.6 GB + NPZ 약 1.2 GB. 수집 속도 144 step/s (칼럼 추가 전 150).

### 7-6. 수집 조건 고정 (11/27, 윤호님 2차 의견)

- `env_options`: `TEAM14_*`뿐 아니라 코드가 읽는 환경변수 34개 전부를 값(없으면 null)으로 기록한다. 보조 규칙(`ROUTE_ASSIST_M`, `MERGE_SUMO`, `MERGE_STOP`, `LC_REVERSE_COOLDOWN` 등), 중간 출발(`HARD_START_*`), `JUNCTION_ROW`, `SIM_REUSE`, `SPAWN_CLEAR_OVERRIDE` 포함.
- `reward_config`: 보상 설정 전체(속도 가중치 0.1, 차간 6 m / 0.1, 양보 위반 1.0, 차선변경·실행 불가 0 등)를 기록한다.
- 보상 기본값을 학습과 같은 −30 / +30 / 막힘 0으로 바꿨다. 환경변수·보상·모델 해시가 표준과 다르면 수집이 시작되지 않는다 (`--allow-nonstandard`를 붙여야 실행되고, 판 정보에 `standard_conditions = false`로 남는다).
- 판 시드 = SUMO 시드(`sumo_seed`). 판마다 SUMO를 새로 시작한다(`SIM_REUSE=1`, 평가와 같은 방식). 같은 PC에서 같은 시드는 병렬 수와 무관하게 같은 판이 나온다 (시드 700001로 확인).
- 시험 3판: 차선변경 막힘 코드 4(route)·5(reverse)는 0회, `hard_start`는 꺼짐.
- 수집 시드는 700000번대부터라 평가 시드(2026~2325)와 겹치지 않는다.
- 병렬 수집 버그 수정: `--workers`가 2 이상이면 보상 옵션이 작업 프로세스에 전달되지 않아 기본값(−5 / +2 / 0.05)으로 기록되던 것을 고쳤다. 검사 스크립트(`tools/check_collect_map6b.py`)가 잡았다.
- README에 적을 것: 결정적 수집의 `log_prob`는 실제 행동 확률이 아니라 "평균 가감속과 가장 확률 높은 차선"에서의 값이라 importance weight로 쓰면 안 된다.
