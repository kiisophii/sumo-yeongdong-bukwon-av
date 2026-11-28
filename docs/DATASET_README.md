---
language:
  - ko
task_categories:
  - reinforcement-learning
tags:
  - sumo
  - autonomous-driving
  - traffic-simulation
  - ppo
  - offline-rl
  - pomdp
pretty_name: SUMO 철도박물관–수원광교박물관 PPO 주행 데이터 (ICE3052 14조)
size_categories:
  - 10M<n<100M
viewer: false
---

# SUMO 철도박물관 → 수원광교박물관 PPO 주행 데이터 (ICE3052 14조)

성균관대학교 ICE3052 14조(김동주, 김수아, 김준희, 조윤호)의 팀 프로젝트 데이터다. SUMO 교통 시뮬레이터에서 철도박물관부터 수원광교박물관까지 약 13.6~14.5 km 경로를 PPO로 학습한 정책 하나가 주행한 기록이며, 1스텝(0.5초)마다 POMDP 전이 `(o_t, a_t, r_t, o_{t+1}, terminated, truncated)`와 SUMO의 실제 상태 `s_t`, 정책 분포, 보상 구성 항, 사건 정보를 저장했다. 완주한 판뿐 아니라 실패한 판(차로 끝 이탈, 차량 충돌, 신호 위반 등)도 그대로 들어 있다. 판 수·스텝 수·종료 사유는 [3절](#3-통계)에 모아 두었다.

## 1. 한눈에 보기

| 항목 | 값 |
|---|---|
| 시뮬레이터 | SUMO 1.28.0 |
| 지도 | map6b (OpenStreetMap 기반, 철도박물관 → 수원광교박물관, 신협오거리를 지나는 경로) |
| 정책 | PPO 하이브리드 정책 체크포인트 `models/map5_ft_200704.pt` |
| 행동 선택 | 결정적 (가감속은 분포의 평균, 차선변경은 확률이 가장 큰 항목) |
| 주행 보조 규칙 | 없음 |
| 1스텝 | 0.5초 |
| 관측 | 실수 37칸 (`TEAM14_ROUTE_OBS=coarse`) |
| 행동 | 실수 2칸 `[가감속, 차선변경]` |
| 파일 형식 | 100판 묶음마다 JSONL(gzip) 1개, NPZ 1개, 검사 결과 TXT 1개 |

프로젝트 페이지: https://kiisophii.github.io/sumo-yeongdong-bukwon-av/

## 2. 폴더 구조

```
data/
  s70/                      시드 700000번대 수집분
    s700000.jsonl.gz        시드 700000~700099 (100판). 한 줄 = 1스텝. 모든 칼럼.
    s700000.npz             같은 100판의 고정 크기 배열. 학습에 바로 쓸 수 있다.
    s700000.check.txt       이 묶음의 수집 조건 검사 결과 (마지막 줄 PASS/FAIL)
    s700100.jsonl.gz        시드 700100~700199
    s700100.npz
    s700100.check.txt
    ...
  s71/                      시드 710000번대 수집분 (같은 수집 조건, 다른 PC)
    s710000.jsonl.gz        시드 710000~710099
    s710000.npz
    s710000.check.txt
    ...
  s73/                      시드 730000번대 수집분 (같은 수집 조건, 또 다른 PC)
    s730000.jsonl.gz        시드 730000~730099
    s730000.npz
    s730000.check.txt
    ...
```

- 폴더는 수집한 PC별로 나뉜다(PC 3대, 폴더 3개). 세 폴더의 수집 조건(정책, 지도, SUMO 버전, 환경변수, 보상 설정, 수집 코드 커밋)과 파일 형식은 같고, 시드 범위와 수집한 PC만 다르다. 폴더별 묶음 수와 시드 범위는 [3절](#3-통계)에 있다.
- 묶음 이름 `sNNNNNN`의 숫자는 그 묶음의 첫 판 시드다. 한 묶음은 연속한 시드 100개, 100판이다.
- 같은 이름의 `.jsonl.gz`와 `.npz`는 같은 스텝을 같은 순서로 담는다. JSONL의 i번째 줄(0부터)과 NPZ 배열의 i번째 행이 같은 스텝이다.

| 파일 | 내용 | 용도 |
|---|---|---|
| `*.jsonl.gz` | 스텝마다 관측, 행동, 보상, 정책 분포, SUMO 실제 상태(주변 차량 포함), 사건, 보상 구성 항. 판 첫 줄에 수집 조건, 판 마지막 줄에 판 요약 | 분석, 검증, 전체 칼럼이 필요한 학습 |
| `*.npz` | 관측·행동·보상·다음 관측 등 고정 크기 배열 24개 | 오프라인 강화학습, 모방학습 |
| `*.check.txt` | 수집 조건 15개 항목의 검사 결과 | 수집 조건 확인 |

## 3. 통계

이 절의 숫자는 `data/s70/`, `data/s71/`, `data/s73/` 전체(묶음 63개)를 기준으로 한다. NPZ 63개를 모두 열어 다시 센 값이다.

### 3-1. 폴더별 규모

| 항목 | `data/s70/` | `data/s71/` | `data/s73/` | 합계 |
|---|---|---|---|---|
| 묶음 수 | 42 (`s700000` ~ `s704100`) | 11 (`s710000` ~ `s711000`) | 10 (`s730000` ~ `s730900`) | 63 |
| 시드 범위 | 700000 ~ 704199 | 710000 ~ 711099 | 730000 ~ 730999 | |
| 판 수 | 4,200 | 1,100 | 1,000 | 6,300 |
| 스텝 수 | 10,258,086 | 2,683,020 | 2,437,246 | 15,378,352 |
| 시뮬레이션 시간 (스텝 수 × 0.5초) | 약 1,424.7시간 | 약 372.6시간 | 약 338.5시간 | 약 2,135.9시간 |
| 판 길이 최소 / 최대 (스텝) | 204 / 3,600 | 208 / 3,535 | 219 / 3,401 | 204 / 3,600 |
| 판 길이 평균 / 중앙값 (스텝) | 2,442.4 / 2,637 | 2,439.1 / 2,625.5 | 2,437.2 / 2,624.5 | 2,441.0 / 2,634 |
| 수집 조건 검사 | 42개 묶음 모두 PASS | 11개 묶음 모두 PASS | 10개 묶음 모두 PASS | 63개 묶음 모두 PASS |
| JSONL 용량 (묶음당) | 8.14 GB (179~204 MB) | 2.11 GB (184~201 MB) | 1.94 GB (187~202 MB) | 12.19 GB |
| NPZ 용량 (묶음당) | 1.19 GB (26~30 MB) | 0.31 GB (27~30 MB) | 0.28 GB (27~29 MB) | 1.79 GB |
| 수집 PC | PC A | PC B | PC C | PC 3대 |

- 세 폴더 모두 시드 범위 안에 빠진 시드와 중복된 시드가 없다. 폴더끼리 시드가 겹치지 않는다.
- 세 폴더는 서로 다른 PC 3대에서 수집했다. 수집 조건은 같다([11절](#11-주의-사항) 12번).

### 3-2. 종료 사유별 판 수

| `end_reason` | 이름 | 뜻 | `data/s70/` | `data/s71/` | `data/s73/` | 합계 | 합계 비율 |
|---|---|---|---|---|---|---|---|
| 1 | `arrival` | 도착 | 3,711 (88.36%) | 975 (88.64%) | 886 (88.60%) | 5,572 | 88.44% |
| 3 | `lane_end` | 차로 끝 이탈 | 279 (6.64%) | 62 (5.64%) | 59 (5.90%) | 400 | 6.35% |
| 2 | `collision` | 차량 충돌 | 110 (2.62%) | 29 (2.64%) | 23 (2.30%) | 162 | 2.57% |
| 4 | `red_light` | 신호 위반 | 95 (2.26%) | 33 (3.00%) | 31 (3.10%) | 159 | 2.52% |
| 5 | `teleport` | SUMO 텔레포트 | 4 (0.10%) | 1 (0.09%) | 1 (0.10%) | 6 | 0.10% |
| 6 | `timeout` | 시간 초과 (3,600스텝) | 1 (0.02%) | 0 | 0 | 1 | 0.02% |
| | 합계 | | 4,200 | 1,100 | 1,000 | 6,300 | 100% |

종료 사유별 마지막 스텝의 보상과 종료 표시는 세 폴더에서 같다.

| 이름 | 마지막 스텝 보상 | `terminated` / `truncated` |
|---|---|---|
| `arrival` | +30 | true / false |
| `lane_end`, `collision`, `teleport` | −30 | true / false |
| `red_light` | −5 | true / false |
| `timeout` | 그 스텝의 주행 보상 | false / true |

### 3-3. 차선변경 명령의 분포

| `lane_change` | `data/s70/` | `data/s71/` | `data/s73/` | 합계 | 합계 비율 |
|---|---|---|---|---|---|
| +1 (왼쪽) | 7,505,818 | 1,964,492 | 1,785,995 | 11,256,305 | 73.2% |
| 0 (유지) | 545,511 | 143,943 | 128,490 | 817,944 | 5.3% |
| −1 (오른쪽) | 2,206,757 | 574,585 | 522,761 | 3,304,103 | 21.5% |

이 중 대부분은 실행되지 않는다([11절](#11-주의-사항) 9번).

## 4. 수집 방법

### 4-1. 정책

- PPO로 학습한 하이브리드 정책이다. 가감속은 Normal 분포, 차선변경은 3-way Categorical 분포로 출력한다.
- 체크포인트: `models/map5_ft_200704.pt` (map5 지도에서 학습한 정책을 이어 학습한 20만 스텝 체크포인트).
  sha256 `6ebdc4f6462497299d03b0197e3c9086dd3e20d9c7af31871a63abaa22d36b36`
- 학습 설정 중 데이터에 기록된 값: `gamma` 0.995, `gae_lambda` 0.95.
- 행동은 결정적으로 골랐다. 가감속은 분포의 평균(`accel_mean`)을 [−1, 1]로 자른 값이고, 차선변경은 확률이 가장 큰 항목이다. 무작위 샘플링은 하지 않았다.
- 주행 중 보조 규칙(경로 보조, 합류 보조, 차선변경 되돌림 제한 등)은 모두 껐다. 환경변수 34개의 값이 판마다 `episode_meta.env_options`에 기록되어 있고, 켜진 것은 아래 7개뿐이다.

  `TEAM14_SCENARIO=museum`, `TEAM14_ROUTE_OBS=coarse`, `TEAM14_NO_SPEED_CAP=1`, `TEAM14_OVERSPEED_W=1.0`, `TEAM14_IDLE_PEN=0.3`, `TEAM14_ROUTE_NO_SHINHYUP=0`, `SIM_REUSE=1`

### 4-2. 환경

- SUMO 1.28.0 (`eclipse-sumo`, `traci`, `sumolib`, `libsumo` 1.28.0).
- 지도 map6b. ego 차량은 철도박물관에서 출발해 수원광교박물관에 도착한다. 경로 길이는 갈래에 따라 약 13.6 km(`blue` 갈래) 또는 약 14.5 km(`orange` 갈래)다.
- 경로는 중간의 한 구간에서 두 갈래(`blue`, `orange`)로 나뉜다. 두 갈래가 갈리는 구간은 의왕역 회전교차로 뒤부터 부곡 영업소 앞까지다. 환경이 출발 시점에 두 갈래의 예상 통행시간(`route_estimates`)을 계산해 더 짧은 쪽을 고른다. 환경 설정에 따라 판마다 확률 0.4로 두 갈래 중 한쪽의 일부 구간 제한속도를 낮춘다(`disrupted_route`). 정책이 갈래를 고르지 않는다.
- 도착한 판 5,572개의 마지막 스텝 주행 거리(NPZ `distance_m`)는 두 값 근처에만 모여 있다. 13,618.5~13,622.2 m가 4,616판, 14,471.3~14,477.5 m가 956판이고 그 사이의 값은 없다.
- ego가 출발하기 전에 배경 교통을 먼저 흘린다. 판의 첫 스텝 SUMO 시각(`sim_time_s`)은 243.0~332.5초다.
- 한 판은 최대 3,600스텝(1,800초)이다. 그 전에 도착, 차량 충돌, 차로 끝 이탈, 신호 위반, 텔레포트가 생기면 끝난다.

### 4-3. 시드 규칙

- 판 i의 시드 = 묶음 시작 시드 + i. 이 값이 SUMO 시드(`--seed`)이자 판의 전역 난수 시드다. `episode_meta.seed`와 `episode_meta.sumo_seed`가 같다.
- 판마다 SUMO를 새로 시작한다(`SIM_REUSE=1`). 행동이 결정적이므로 판마다 달라지는 것은 시드가 정하는 배경 교통과 경로 조건이다.
- 수집한 PC마다 시작 시드를 다르게 정했다. `data/s70/`은 700000번부터, `data/s71/`은 710000번부터, `data/s73/`은 730000번부터다. 폴더 이름의 숫자가 시드의 앞 두 자리다.
- 수집 시드(700000번대, 710000번대, 730000번대)는 정책 평가에 쓴 시드(2026~2325)와 겹치지 않는다.
- 같은 PC에서는 같은 시드가 같은 판을 만든다. PC가 다르면 같은 시드여도 결과가 똑같지 않을 수 있다. 이 데이터에는 같은 시드를 둘 이상의 PC에서 수집한 판이 없다.

### 4-4. 실행과 검사

- 수집은 `tools/collect_map6b.sh`로만 실행했다. 이 스크립트가 결과에 영향을 주는 환경변수를 모두 지운 뒤 표준값만 설정하고 `collect_pomdp_data.py`를 부른다. 수집 코드는 환경변수·보상 설정·모델 해시가 표준과 다르면 시작하지 않는다.
- 100판 묶음마다 `tools/check_collect_map6b.py`로 검사했고 결과를 `*.check.txt`에 저장했다. 검사 항목 15개:

  1. 모든 판의 수집 조건(모델 해시, SUMO 버전, 환경변수, 보상 설정, 코드 커밋)이 같음
  2. 모델 파일 해시가 위 sha256과 같음
  3. SUMO 1.28.0
  4. 환경변수 표준값
  5. 다른 환경변수가 꺼져 있음 (보조 규칙, 중간 출발 등)
  6. 보상 설정
  7. `standard_conditions = true`
  8. 결정적 행동, 신협오거리 우회 경로 아님
  9. 중간 출발(`hard_start`) 꺼짐
  10. 관측 37칸
  11. 모든 스텝에서 보상 구성 항의 합 = `reward`
  12. 차선변경 막힘 코드 4(route)·5(reverse) 없음
  13. 신협오거리를 통과한 판이 있음
  14. 시드 중복 없음, 평가 시드와 겹치지 않음
  15. SUMO 시드 = 판 시드

- 수집 코드 커밋은 판마다 `episode_meta.code_commit`에 기록되어 있다.

## 5. JSONL 필드

한 줄이 1스텝인 JSON 객체다. 실수는 `observation`, `state`, `detected_vehicles`, `next_observation`, `next_state`에서 소수 넷째 자리로 반올림되어 있다(NPZ는 float32 그대로).

### 5-1. 모든 줄에 있는 필드 (16개)

| 필드 | 형태 | 내용 |
|---|---|---|
| `episode` | 정수 | 묶음 안의 판 번호 (0~99). 묶음마다 0부터 다시 시작한다 |
| `t` | 정수 | 판 안의 스텝 번호 (0부터) |
| `observation` | 실수 37칸 | 정책이 받은 관측 o_t ([7절](#7-관측-37칸)) |
| `action_raw` | 실수 2칸 | 정책 출력 `[가감속, 차선변경]`. 가감속은 −1~1, 차선변경은 −1, 0, +1 중 하나 |
| `action` | 객체 | `accel_raw`(실수), `lane_change_raw`(실수), `lane_change`(정수 −1/0/+1), `lane_change_applied`(참/거짓) |
| `reward` | 실수 | 그 스텝의 보상 r_t |
| `value_pred` | 실수 | critic이 o_t에서 예측한 값 V(o_t) |
| `policy` | 객체 | `accel_mean`, `accel_std`(가감속 분포의 평균·표준편차), `lane_prob_left`, `lane_prob_keep`, `lane_prob_right`(차선변경 확률), `log_prob`(고른 행동의 log π(a\|o)) |
| `return_to_go` | 실수 | G_t = r_t + γ·G_{t+1}, γ = 0.995, 판의 마지막 스텝 뒤는 0 |
| `terminated` | 참/거짓 | 환경 종료 |
| `truncated` | 참/거짓 | 시간 제한 종료 |
| `state` | 객체 | SUMO의 실제 상태 s_t (5-3) |
| `detected_vehicles` | 목록 | 관측 범위 안에서 감지된 차량 (5-5) |
| `event` | 객체 | 그 스텝의 사건 15개 (5-6) |
| `reward_terms` | 객체 | 보상 구성 항 12개 ([9절](#9-보상)) |
| `derived` | 객체 | 관측 칸에서 단위를 되돌린 값 6개 (5-7) |

### 5-2. 일부 줄에만 있는 필드

| 필드 | 있는 줄 | 내용 |
|---|---|---|
| `episode_meta` | 판의 첫 줄 (`t` = 0) | 수집 조건 24개 (5-8) |
| `episode_summary` | 판의 마지막 줄 | 판 요약 7개 (5-9) |
| `next_observation` | 판의 마지막 줄 | o_{t+1}, 실수 37칸 |
| `next_state` | 판의 마지막 줄 | s_{t+1} |

판의 마지막 줄이 아닌 줄에서 `next_observation`·`next_state`는 바로 다음 줄의 `observation`·`state`다([11절](#11-주의-사항) 1번).

### 5-3. `state` (30개)

정책 입력이 아니라 SUMO에서 직접 읽은 값이다.

| 필드 | 형태·단위 | 내용 |
|---|---|---|
| `ego_alive` | 참/거짓 | ego가 시뮬레이션에 있는지 |
| `ego_x`, `ego_y` | m | SUMO 좌표 |
| `ego_speed` | m/s | |
| `ego_accel` | m/s² | |
| `ego_heading` | 도 | SUMO `getAngle` |
| `ego_lane` | 정수 | 차로 번호. 0이 가장 오른쪽 |
| `ego_lane_id`, `ego_road_id` | 문자열 | SUMO 차로 ID, 도로 ID |
| `ego_lane_pos` | m | 차로 시작점부터의 거리 |
| `ego_distance_m` | m | 출발 뒤 주행 거리 |
| `ego_route_edge_index` | 정수 | 경로에서 몇 번째 도로인지 |
| `ego_num_lanes` | 정수 | 현재 도로의 차로 수 |
| `ego_lane_remaining_m` | m | 현재 차로 끝까지의 거리 |
| `speed_limit_mps` | m/s | 현재 차로 제한속도 |
| `allowed_speed_mps` | m/s | SUMO `getAllowedSpeed` |
| `signal_distance_m` | m | 다음 신호까지의 거리. 없으면 −1 |
| `signal_green`, `signal_yellow`, `signal_red` | 0/1 | 다음 신호의 색. 신호가 없으면 셋 다 0 |
| `signal_remaining_s` | 초 | 현재 색이 바뀔 때까지 남은 시간. 없으면 −1 |
| `signal2_distance_m` | m | 그다음 신호까지의 거리. 없으면 −1 |
| `signal2_green`, `signal2_yellow`, `signal2_red` | 0/1 | 그다음 신호의 색 |
| `sim_time_s` | 초 | SUMO 시각 |
| `lane_route_remaining_m` | 실수 목록 | 현재 도로의 차로별(0번부터) 차선변경 없이 경로를 따라 더 갈 수 있는 거리. 교차로 안에서는 빈 목록 |
| `lead_gap_m` | m | 같은 차로 앞차까지의 간격. 없으면 −1 |
| `lead_speed_mps` | m/s | 같은 차로 앞차 속도. 없으면 −1 |
| `vehicles` | 목록 | ego 반경 150 m 안의 차량 (5-4) |

### 5-4. `state.vehicles` 원소 (13개)

`id`, `x`, `y`, `speed`, `lane`, `lane_id`, `road_id`, `lane_pos`, `accel`, `heading`, `length`, `flow_index`(배경 교통 흐름 번호. ego는 −1), `route_edge_number`(그 차가 있는 도로가 ego 경로의 몇 번째 도로인지. 경로 밖이면 −1)

- ego 자신도 이 목록에 들어 있다(`id`가 `"ego"`).
- `data/s70/`의 앞 3개 묶음(`s700000`~`s700200`)에서 스텝당 평균 17.8대, 최대 85대(ego 포함)였다.

### 5-5. `detected_vehicles` 원소 (6개)

`id`, `x`, `y`(SUMO 좌표), `rel_pos`(ego 기준 진행 방향 거리 m, 앞이 +), `speed`(m/s), `lane_offset`(ego 차로 기준 차로 차이, 왼쪽이 +)

- ego와 같은 도로의 ego 차로 ±2차로 안에서 진행 방향 거리 50 m 이내인 차량이다. ego가 교차로 안에 있으면 빈 목록이다.
- 같은 3개 묶음에서 스텝당 평균 2.4대, 최대 22대였다.

### 5-6. `event` (15개)

| 필드 | 형태 | 내용 |
|---|---|---|
| `collided` | 참/거짓 | 감점 종료가 일어났는지. 차량 충돌뿐 아니라 차로 끝 이탈, 신호 위반, 텔레포트로 끝난 스텝에서도 참이다 |
| `arrived` | 참/거짓 | 도착 |
| `lane_before`, `lane_after` | 정수 | 행동 전후의 ego 차로 번호. ego가 사라진 스텝의 `lane_after`는 null |
| `end_reason` | 정수 | 종료 사유 코드. 진행 중이면 0 ([10절](#10-코드표)) |
| `end_lane` | 문자열 | 판이 끝난 차로 ID. 진행 중이면 null |
| `vehicle_collision`, `red_light`, `lane_end`, `teleported` | 참/거짓 | 종료 종류별 표시 |
| `yield_violation` | 참/거짓 | 양보해야 하는 교차로에 교차 차량이 접근하는데 진입함 |
| `lane_change_blocked` | 문자열 | 차선변경이 실행되지 않은 이유. 없으면 null |
| `lane_change_blocked_code` | 정수 | 위 이유의 코드 ([10절](#10-코드표)) |
| `action_executed` | 실수 2칸 | 실제 속도 변화에서 되돌려 계산한 `[가감속, 차선변경 명령]` |
| `overspeed` | 참/거짓 | `ego_speed` > `allowed_speed_mps` × 1.02 |

### 5-7. `derived` (6개)

`lane_end_remaining_m`, `fork_distance_m`, `fork_direction`(−1/0/+1), `junction_distance_m`, `junction_must_yield`(0/1), `junction_cross_traffic`(0/1)

SUMO에서 읽은 값이 아니라 관측 21~23칸, 34~36칸을 단위만 되돌린 값이다. 관측값이 0.999 이상이면(해당 없음) 거리는 −1이다.

### 5-8. `episode_meta` (24개, 판의 첫 줄)

| 필드 | 내용 | 이 데이터의 값 |
|---|---|---|
| `seed` | 판 시드. **판의 고유 키** | 700000~704199, 710000~711099, 730000~730999 |
| `sumo_seed` | SUMO 시드 | `seed`와 같음 |
| `route_name` | 고른 갈래 | `blue` 또는 `orange` |
| `route_estimates` | 출발 시점 두 갈래의 예상 통행시간(초) | `{"orange": …, "blue": …}` |
| `disrupted_route` | 제한속도를 낮춘 갈래 | `blue`, `orange`, null |
| `hard_start` | 중간 출발 정보 | null (사용 안 함) |
| `route_edges` | 경로의 도로 수 | 81(`blue`), 75(`orange`) |
| `model`, `model_path` | 모델 파일 이름, 경로 | `map5_ft_200704.pt`, `models/map5_ft_200704.pt` |
| `model_sha256` | 모델 파일 해시 | 4-1절의 값 |
| `policy` | 정책 종류 | `ppo` |
| `stochastic` | 샘플링 여부 | false |
| `detour_no_shinhyup` | 신협오거리 우회 경로 여부 | false |
| `sim_reuse` | `SIM_REUSE` 값 | `"1"` |
| `sumo_version` | SUMO 버전 | `SUMO 1.28.0` |
| `code_commit` | 수집 코드 커밋 | `c00ba3dca52b43c938571b88565deceb6bffec3a` |
| `env_options` | 환경변수 34개의 값 (설정 안 한 것은 null) | 4-1절 |
| `standard_conditions` | 표준 조건으로 수집했는지 | true |
| `gamma`, `gae_lambda` | 할인율, GAE λ | 0.995, 0.95 |
| `map_version` | 지도 | `map6b` |
| `traffic_vehs_per_hour` | 교통량 설정 | null (이 지도 설정에는 이 값이 없다) |
| `step_seconds` | 1스텝 길이 | 0.5 |
| `reward_config` | 보상 설정 16개 | [9절](#9-보상) |

### 5-9. `episode_summary` (7개, 판의 마지막 줄)

| 필드 | 내용 |
|---|---|
| `end_reason`, `end_reason_name` | 종료 사유 코드와 이름 |
| `end_lane` | 판이 끝난 차로 ID |
| `steps` | 판의 스텝 수 |
| `return` | 판의 보상 합 (할인 없음) |
| `distance_m` | 주행 거리 |
| `collision` | 차량 충돌로 끝났으면 객체, 아니면 null |

`collision` 객체(9개): `type`, `type_code`([10절](#10-코드표)), `ego_is_collider`(ego가 들이받은 쪽인지), `ego_speed_mps`, `partner_id`, `partner_flow_index`, `partner_speed_mps`, `lane_id`, `lane_pos`

## 6. NPZ 배열

묶음 하나의 스텝 수를 N, 감지 차량 좌표의 총 개수를 M이라 한다. 63개 묶음 모두 키 24개와 dtype이 같다. `allow_pickle` 없이 읽을 수 있다.

| 키 | shape | dtype | 내용 |
|---|---|---|---|
| `observation` | (N, 37) | float32 | o_t |
| `action_raw` | (N, 2) | float32 | 정책 출력 `[가감속, 차선변경]` |
| `lane_change` | (N,) | int8 | 차선변경 명령 −1/0/+1. `action_raw[:, 1]`과 같은 값 |
| `reward` | (N,) | float32 | r_t |
| `next_observation` | (N, 37) | float32 | o_{t+1}. 모든 스텝에 들어 있다 |
| `terminated` | (N,) | bool | 환경 종료 |
| `truncated` | (N,) | bool | 시간 제한 종료 |
| `episode` | (N,) | int32 | 묶음 안의 판 번호 (0~99) |
| `t` | (N,) | int32 | 판 안의 스텝 번호 |
| `end_reason` | (N,) | int8 | 종료 사유 코드. 판의 마지막 스텝에만 0이 아닌 값 |
| `speed_mps` | (N,) | float32 | `state.ego_speed` |
| `allowed_speed_mps` | (N,) | float32 | `state.allowed_speed_mps` |
| `distance_m` | (N,) | float32 | `state.ego_distance_m` |
| `lead_gap_m` | (N,) | float32 | `state.lead_gap_m`. 앞차가 없으면 −1 |
| `signal_onehot` | (N, 3) | int8 | `state.signal_green`, `signal_yellow`, `signal_red`. 신호가 없으면 [0, 0, 0] |
| `seed` | (N,) | int64 | 판 시드. **판의 고유 키** |
| `value_pred` | (N,) | float32 | V(o_t) |
| `log_prob` | (N,) | float32 | `policy.log_prob` |
| `accel_mean` | (N,) | float32 | `policy.accel_mean` |
| `lane_probs` | (N, 3) | float32 | 차선변경 확률 `[왼쪽, 유지, 오른쪽]` |
| `sim_time_s` | (N,) | float32 | `state.sim_time_s` |
| `return_to_go` | (N,) | float32 | G_t (γ = 0.995) |
| `detected_xy` | (M, 2) | float32 | 모든 스텝의 감지 차량 좌표 (x, y)를 이어 붙인 배열 |
| `detected_offsets` | (N+1,) | int64 | 스텝 i의 감지 차량 좌표 = `detected_xy[detected_offsets[i]:detected_offsets[i+1]]` |

예: `s700000.npz`는 N = 227,180, M = 538,841이다.

NPZ에 없고 JSONL에만 있는 것: `state`의 나머지 필드와 주변 차량, `event`(종료 사유 외), `reward_terms`, `derived`, `policy.accel_std`, `episode_meta`, `episode_summary`.

## 7. 관측 37칸

조건: `TEAM14_ROUTE_OBS=coarse` 켬, `TEAM14_JUN_INSIDE`와 `TEAM14_TOF_OBS` 끔. 이 조건이 아닌 환경에서는 같은 37칸이어도 21~25칸의 의미가 다르다. 모든 값은 −1~1 범위다.

| 칸 | 내용 | 정규화와 값 |
|---|---|---|
| 0 | ego 속도 | ÷ 27.78 m/s |
| 1~4 | 왼쪽 2번째 차로: 앞차 거리, 앞차 상대속도, 뒤차 거리, 뒤차 상대속도 | 거리 ÷ 50 m(뒤차 거리는 음수), 상대속도 ÷ 27.78 m/s. 앞차가 없으면 [1, 1], 뒤차가 없으면 [−1, −1] |
| 5~8 | 왼쪽 1번째 차로: 같은 4개 | 위와 같음 |
| 9~12 | 현재 차로: 같은 4개 | 위와 같음 |
| 13~16 | 오른쪽 1번째 차로: 같은 4개 | 위와 같음 |
| 17~20 | 오른쪽 2번째 차로: 같은 4개 | 위와 같음 |
| 21 | 현재 차로가 끝나는 지점까지의 거리 (50 m 안일 때) | ÷ 50 m. 해당 없으면 1 |
| 22 | 다음 갈림길까지의 거리 | ÷ 600 m. 해당 없으면 1 |
| 23 | 그 갈림길에서 경로 방향 | 오른쪽 +1, 왼쪽 −1, 없음 0 |
| 24 | 허용속도 (`state.allowed_speed_mps`) | ÷ 27.78 m/s, 1을 넘으면 1 |
| 25 | ego 속도 − 허용속도 (비율이 아니라 차) | ÷ 27.78 m/s |
| 26~30 | 5개 차로(1~20칸과 같은 순서)의 앞쪽 50 m 구간 차량 밀도 | 0~1 |
| 31 | 다음 신호까지의 거리 | ÷ 150 m. 150 m 안에 신호가 없으면 1 |
| 32 | 신호 색 | 녹색 또는 없음 +1, 황색 0, 적색 −1 |
| 33 | 현재 색이 남은 시간 | ÷ 30초, 0~1. 신호가 없으면 1 |
| 34 | 양보 교차로까지의 거리 | ÷ 150 m. 없으면 1 |
| 35 | 양보 의무 | 있음 +1, 없음 −1 |
| 36 | 교차 차량 접근 | 있음 +1, 없음 −1 |

- 21~23칸은 ego가 교차로 안에 있는 동안 직전 값을 유지한다.
- 31~33칸은 150 m 안의 신호만 반영한다. `state.signal_*`은 거리와 관계없이 다음 신호를 기록하므로, `state.signal_red`가 1이어도 32칸이 +1인 스텝이 있다.
- 0, 24, 25, 32칸은 `s700000.npz`에서 `speed_mps`, `allowed_speed_mps`, `signal_onehot`과 대조해 위 정의와 맞는 것을 확인했다. 나머지 칸의 정의는 수집 코드 저장소의 칼럼 문서(`docs/DATA_COLUMNS_MAP6B.md`)를 따랐다.

## 8. 행동

| 성분 | 범위 | 뜻 |
|---|---|---|
| `action_raw[0]` 가감속 | −1 ~ 1 | 양수는 가속, 음수는 감속 |
| `action_raw[1]` 차선변경 | −1, 0, +1 | +1 왼쪽, 0 유지, −1 오른쪽 |

- SUMO에서 차로 번호는 왼쪽으로 갈수록 커지므로 +1이 왼쪽 차로로 가는 명령이다.
- 정책의 차선변경 출력은 3-way Categorical이다. 인덱스와 명령의 대응은 0 = 왼쪽(+1), 1 = 유지(0), 2 = 오른쪽(−1)이다. 즉 인덱스 = 1 − 명령이고, `lane_probs`와 `policy.lane_prob_left/keep/right`의 순서가 이 인덱스 순서다.
- 결정적 수집이므로 모든 스텝에서 `action_raw[0]`은 `accel_mean`과 같고, `action_raw[1]`은 `lane_probs`가 가장 큰 항목의 명령이다(`s700000.npz`와 `data/s71/`·`data/s73/`의 NPZ 21개에서 확인).
- 차선변경 명령이 실행됐는지는 `action.lane_change_applied`, 실행되지 않은 이유는 `event.lane_change_blocked_code`로 확인한다. 유지 명령(0)에서도 `lane_change_applied`는 대부분 true다(현재 차로 유지 명령이 실행된 것).

## 9. 보상

### 9-1. 보상 구성 항 (`reward_terms`, 12개)

매 스텝 12개 항을 고정 순서로 저장한다. 발생하지 않은 항은 0이고, 모든 스텝에서 12개 항의 합이 `reward`다.

| 항 | 값 | 조건 |
|---|---|---|
| `speed` | 0 ~ +0.1 | 0.1 × min(ego 속도 ÷ 현재 구간 제한속도, 1) |
| `overspeed` | ≤ 0 | −1.0 × max(0, ego 속도 ÷ 허용속도 − 1) |
| `idle` | −0.3 | 속도 1 m/s 미만이고, 같은 차로 앞차가 없거나 20 m 밖이고, 60 m 안의 다음 신호가 적색·황색이 아닐 때 |
| `stop_shaping` | 0 | 이 수집 조건에서는 꺼져 있어 항상 0 |
| `close_gap` | −0.1 | 같은 차로 앞차와의 간격이 6 m 미만일 때 |
| `blocked` | 0 | 가중치 0이라 항상 0 |
| `lane_change` | 0 | 가중치 0이라 항상 0 |
| `invalid_action` | 0 | 가중치 0이라 항상 0 |
| `yield` | −1.0 | 양보 위반(`event.yield_violation`). 판은 끝나지 않는다 |
| `red_light` | −5.0 | 신호 위반으로 종료 |
| `collision` | −30.0 | 차량 충돌, 차로 끝 이탈, 텔레포트로 종료 |
| `arrival` | +30.0 | 도착 |

종료 스텝(`red_light`, `collision`, `arrival`)에서는 그 항만 값이 있고 주행 항(`speed` 등)은 0이다.

### 9-2. 보상 설정값 (`episode_meta.reward_config`, 16개)

| 키 | 값 |
|---|---|
| `speed_reference` | `"lane"` |
| `speed_weight` | 0.1 |
| `close_gap_threshold` | 6.0 |
| `close_gap_penalty` | 0.1 |
| `collision_penalty` | 30.0 |
| `arrival_bonus` | 30.0 |
| `red_light_penalty` | 5.0 |
| `red_light_terminate` | true |
| `yield_penalty` | 1.0 |
| `blocked_penalty` | 0.0 |
| `blocked_gap` | 20.0 |
| `blocked_speed_frac` | 0.7 |
| `lane_change_penalty` | 0.0 |
| `invalid_action_penalty` | 0.0 |
| `idle_penalty` | 0.3 |
| `overspeed_weight` | 1.0 |

## 10. 코드표

`END_REASON` (`event.end_reason`, `episode_summary.end_reason`, NPZ `end_reason`)

| 코드 | 이름 | 뜻 |
|---|---|---|
| 0 | (없음) | 진행 중 |
| 1 | `arrival` | 도착 |
| 2 | `collision` | 차량 충돌 |
| 3 | `lane_end` | 차로 끝 이탈 |
| 4 | `red_light` | 신호 위반 |
| 5 | `teleport` | SUMO 텔레포트 |
| 6 | `timeout` | 시간 초과 |
| 7 | `stall` | 정체 (이 데이터에는 없음) |
| 8 | `vehicle_removed` | 차량 제거 (이 데이터에는 없음) |

`LC_BLOCK` (`event.lane_change_blocked_code`)

| 코드 | 이름 | 뜻 |
|---|---|---|
| 0 | (없음) | 막히지 않음 |
| 1 | `no_lane` | 옮겨 갈 차로가 없음 |
| 2 | `junction` | 교차로 안 |
| 3 | `unsafe` | 안전 간격 부족 |
| 4 | `route` | 경로 이탈 방향 (이 데이터에는 없음) |
| 5 | `reverse` | 직전 변경의 반대 방향 (이 데이터에는 없음) |

`COLLISION_TYPE` (`episode_summary.collision.type_code`, SUMO가 보고한 충돌 종류)

| 코드 | 이름 |
|---|---|
| 1 | `collision` |
| 2 | `junction` |
| 3 | `frontal` |
| 4 | `crossing` |
| 5 | `side` |

## 11. 주의 사항

1. **JSONL의 `next_observation`·`next_state`는 판의 마지막 스텝에만 있다.** 나머지 스텝에서는 바로 다음 줄의 `observation`·`state`가 그 값이다. 12-2절의 함수로 복원한다. NPZ의 `next_observation`은 모든 스텝에 들어 있다.
2. **`episode`는 묶음마다 0부터 다시 시작한다.** 판의 고유 키는 `seed`다(JSONL은 `episode_meta.seed`, NPZ는 `seed` 배열). 묶음을 합칠 때는 `seed`로 판을 구분한다.
3. **`log_prob`은 importance weight로 쓸 수 없다.** 결정적 수집이라 실제 행동 확률은 1이다. 저장된 `log_prob`은 가감속 분포의 평균과 확률이 가장 큰 차선 항목에서 계산한 log π 값이다.
4. **`return_to_go`는 `truncated`로 끝난 판에서 과소 추정된다.** 시간 제한 뒤의 보상이 빠져 있기 때문이다. 해당하는 판 수는 3절의 `timeout` 행에 있다.
5. **차로 끝 이탈의 −30은 `reward_terms.collision`에 들어 있다.** 텔레포트의 −30도 같은 항이다. 차량 충돌과 구분하려면 `event.end_reason`을 쓴다. `event.collided`도 차로 끝 이탈·신호 위반·텔레포트에서 참이므로 차량 충돌 여부는 `event.vehicle_collision`으로 본다.
6. **ego가 사라지며 끝난 판은 마지막 스텝의 `next_observation`이 전부 0이다.** 도착과 차량 충돌로 끝난 판이 모두 여기에 해당한다. 이때 JSONL의 `next_state`는 `{"ego_alive": false}`뿐이다. 차로 끝 이탈, 신호 위반, 텔레포트, 시간 초과로 끝난 판은 마지막 `next_observation`이 0이 아니고 `next_state`에 30개 필드가 모두 있다.
7. **관측 37칸의 의미는 `TEAM14_ROUTE_OBS=coarse` 조건의 것이다.** 다른 관측 설정으로 학습한 정책의 37칸과 섞어 쓰면 안 된다.
8. **코드 값은 10절의 표를 따른다.** `END_REASON`, `LC_BLOCK`, `COLLISION_TYPE`.
9. **차선변경 명령의 대부분은 실행되지 않는다.** `data/s70/`의 앞 3개 묶음(718,507스텝)에서 `no_lane` 639,000스텝(88.9%), `junction` 29,385스텝, `unsafe` 9,122스텝이었고, 유지가 아닌 명령이 실제로 실행된 것은 3,132스텝이었다. 행동을 쓸 때 `action.lane_change`와 `action.lane_change_applied`를 같이 본다.
10. **JSONL과 NPZ의 실수는 자릿수가 다르다.** JSONL의 관측은 소수 넷째 자리 반올림이라 NPZ와 최대 0.00005 차이가 난다. `reward`와 `return_to_go`는 JSONL이 배정밀도, NPZ가 float32다.
11. **`lead_gap_m`에 −1이 아닌 음수가 드물게 있다.** 전체에서 28스텝이다(`data/s70/` 21, `data/s71/` 6, `data/s73/` 1). SUMO가 돌려준 간격 값 그대로다.
12. **폴더마다 수집한 PC가 다르다.** 수집 조건은 같지만, PC가 다르면 같은 시드라도 결과가 달라질 수 있다. 그래서 이 데이터의 판을 시드로 다시 만들어 비교할 때는 실행 환경에 따라 결과가 일치하지 않을 수 있다. 세 폴더의 시드는 겹치지 않으므로 폴더를 합쳐 써도 `seed`는 판의 고유 키다.

## 12. 읽는 예시

아래 코드는 저장소를 내려받은 폴더(안에 `data/s70/`이 있는 폴더)에서 실행한다. Python 3과 NumPy만 있으면 된다.

### 12-1. NPZ 읽기

```python
import numpy as np

d = np.load("data/s70/s700000.npz")          # allow_pickle 필요 없음
obs, act, rew = d["observation"], d["action_raw"], d["reward"]
next_obs = d["next_observation"]              # 모든 스텝에 있음
done = d["terminated"] | d["truncated"]
print("스텝 수:", len(rew), "| 관측:", obs.shape, obs.dtype, "| 행동:", act.shape)

# 판 나누기: episode가 아니라 seed를 쓴다
seeds, starts, lengths = np.unique(d["seed"], return_index=True, return_counts=True)
print("판 수:", len(seeds), "| 시드:", seeds[0], "~", seeds[-1])

# 판별 종료 사유 (판의 마지막 스텝에만 0이 아닌 값)
END_REASON = {1: "arrival", 2: "collision", 3: "lane_end", 4: "red_light",
              5: "teleport", 6: "timeout", 7: "stall", 8: "vehicle_removed"}
names, counts = np.unique(d["end_reason"][done], return_counts=True)
print({END_REASON[int(k)]: int(v) for k, v in zip(names, counts)})

# 판 하나 꺼내기
i = 0
ep = slice(starts[i], starts[i] + lengths[i])
print("시드", seeds[i], "| 길이", lengths[i], "| 보상 합", float(rew[ep].sum()))

# 스텝 k에서 감지된 차량의 좌표 (개수는 스텝마다 다름)
k = 1000
off = d["detected_offsets"]
print("스텝", k, "감지 차량 좌표:", d["detected_xy"][off[k]:off[k + 1]].shape)
```

### 12-2. JSONL에서 전이 복원하기

```python
import gzip
import json


def iter_transitions(path):
    """JSONL(.gz)을 읽어 next_observation·next_state가 채워진 전이를 차례로 돌려준다.

    판의 마지막 줄에는 next_*가 이미 있고, 나머지 줄은 다음 줄의 observation·state로 채운다.
    """
    prev = None
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if prev is not None:
                prev.setdefault("next_observation", rec["observation"])
                prev.setdefault("next_state", rec["state"])
                yield prev
            prev = rec
    if prev is not None:
        yield prev


seed = None
for tr in iter_transitions("data/s70/s700000.jsonl.gz"):
    if "episode_meta" in tr:                  # 판의 첫 줄: 수집 조건
        seed = tr["episode_meta"]["seed"]     # 판의 고유 키
    o, a, r = tr["observation"], tr["action_raw"], tr["reward"]
    o_next = tr["next_observation"]
    done = tr["terminated"] or tr["truncated"]
    if done:                                  # 판의 마지막 줄: 판 요약
        s = tr["episode_summary"]
        print(seed, s["end_reason_name"], s["steps"], round(s["return"], 2))
        break                                 # 첫 판만 보고 멈춘다. 전체를 보려면 이 줄을 지운다
```

묶음 하나의 JSONL은 압축을 풀면 1.5 GB가 넘는다. 위처럼 한 줄씩 읽으면 메모리에 한 번에 올리지 않는다.

### 12-3. Hugging Face에서 묶음 하나만 받기

```python
from huggingface_hub import hf_hub_download

path = hf_hub_download(repo_id="kimsua/team14-sumo-driving-data", repo_type="dataset",
                       filename="data/s70/s700000.npz")
```

## 13. 링크

- 프로젝트 페이지: https://kiisophii.github.io/sumo-yeongdong-bukwon-av/ (결과 요약, 실험 흐름, 주행 영상)
- 데이터셋: https://huggingface.co/datasets/kimsua/team14-sumo-driving-data
- 코드 저장소: https://github.com/kiisophii/sumo-yeongdong-bukwon-av (수집 코드는 `share/map6b-collect` 브랜치)
  - `collect_pomdp_data.py`: 수집 코드
  - `tools/collect_map6b.sh`: 표준 조건으로 수집을 실행하는 스크립트
  - `tools/check_collect_map6b.py`: 묶음 검사 스크립트
  - `docs/DATA_COLUMNS_MAP6B.md`, `docs/DATA_COLLECT_MAP6B.md`: 칼럼 문서, 수집 방법 문서
- 과목: 성균관대학교 ICE3052, 14조
