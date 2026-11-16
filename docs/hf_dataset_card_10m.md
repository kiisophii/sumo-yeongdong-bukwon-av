---
license: odbl
task_categories:
  - reinforcement-learning
tags:
  - autonomous-driving
  - sumo
  - offline-rl
  - imitation-learning
  - pomdp
language:
  - ko
pretty_name: SUMO 철도박물관→수원광교박물관 자율주행 주행 데이터셋 10M (Team 14)
size_categories:
  - 10M<n<100M
---

# SUMO 철도박물관 → 수원광교박물관 자율주행 주행 데이터셋 (10M transitions)

> **초안**: 아래 `{{...}}` 값은 수집이 끝난 뒤 `python tools/collect_data.py --out-dir <폴더> --summarize`가
> 만든 `stats.json`으로 채운다.

성균관대학교 「자율주행 인공지능 및 제어」(ICE3052, 2026-2) 팀 프로젝트 14팀
(김동주·김수아·김준희·조윤호)의 결과 데이터셋입니다.

OpenStreetMap 기반 **의왕 철도박물관 주차장 → 수원광교박물관 주차장 (약 14.4 km)** 경로를 SUMO로
구축하고, PPO로 학습한 자율주행 차량(ego)이 주행하며 남긴 POMDP transition
(o_t, a_t, r_t, o_{t+1}, done)을 **{{transitions}}개** 담았습니다.

## 경로 / 교통 환경
- 일반도로(신협오거리·의왕역 회전교차로, 신호교차로) → 부곡IC 진입 → 영동고속도로 북수원 합류부
  → 동수원IC 진출 → 광교 일반도로
- 배경 차량: Krauss / IDM / EIDM / ACC 4종 혼합
- 시뮬레이션 1 step = 0.5 초, 에피소드 최대 3,600 step(1,800 초)
- 에피소드마다 SUMO를 새로 시작(`SIM_REUSE=1`)하고 시드를 고정해, 같은 시드로 다시 돌리면 같은
  에피소드가 재현됩니다 (시드는 샤드 메타 json의 `episodes_detail[].seed`).

## 수집 정책
| 항목 | 값 |
|---|---|
| 정책 | PPO (hybrid: 연속 가감속 + 이산 차선변경), 은닉층 256×256, 결정적 행동(μ, argmax 차선) |
| 모델 | `{{model}}` |
| 보조 규칙 (환경변수) | `ROUTE_ASSIST_M=600` 경로 차로 보조, `MERGE_SUMO=1` 막힌 합류 시 SUMO 차선변경 위임, `MERGE_STOP=1` 합류 불가 시 차로 끝 전 정지, `LC_REVERSE_COOLDOWN=3` 3초 내 반대 방향 재변경(핑퐁) 금지 |

## 통계
| 항목 | 값 |
|---|---:|
| transition | {{transitions}} |
| 에피소드 | {{episodes}} |
| 완주율 | {{arrival_rate}} |
| 충돌률 | {{collision_rate}} |
| 경로 이탈률 | {{lane_end_rate}} |
| 평균 에피소드 길이 (step) | {{mean_episode_steps}} |

## 파일 구성
```
shards/wWW_sSSSSS.npz    샤드 (워커 WW의 SSSSS번째 묶음, 에피소드 20개)
shards/wWW_sSSSSS.json   샤드 메타 (스텝 수, 에피소드별 시드·결과·리턴, 환경변수)
stats.json               전체 통계
```
샤드 npz의 배열 (N = 그 샤드의 transition 수):

| 키 | shape / dtype | 내용 |
|---|---|---|
| `observation` | (N, 37) float32 | 부분관측 o_t (아래 참고), [-1, 1] |
| `action_raw` | (N, 2) float32 | 정책 출력 [가감속, 차선변경 raw] ∈ [-1, 1] |
| `lane_change` | (N,) int8 | 보조 규칙까지 거친 차선 명령 {-1 우, 0 유지, +1 좌} |
| `lane_change_applied` | (N,) bool | 명령이 실제로 실행됐는지 |
| `reward` | (N,) float32 | r_t |
| `next_observation` | (N, 37) float32 | o_{t+1} |
| `terminated` / `truncated` | (N,) bool | 종료(충돌·완주·경로이탈) / 시간 초과 |
| `collided` / `arrived` / `lane_end` | (N,) bool | 종료 원인 |
| `speed` / `gap` | (N,) float32 | ego 속도(m/s) / 앞차 거리(m, 없으면 NaN) |
| `episode` / `t` | (N,) int64 / int32 | 전역 에피소드 번호 / 에피소드 내 step |
| `detected_xy`, `detected_offsets` | (M, 2) float32, (N+1,) int64 | 시야 50 m 안 차량 좌표. 스텝 i: `detected_xy[off[i]:off[i+1]]` |

앞 9개 키는 기존 팀 데이터셋(`collect_pomdp_data.py`)과 이름·의미가 같습니다.

### Observation (37차원)
- `[0]` 내 속도 / vmax
- `[1..20]` 5개 차선(좌2·좌1·현재·우1·우2)의 선행/후행 차량 상대거리(÷50 m)·상대속도
- `[21..25]` 경로 기준 차선 연결성 (600 m 앞까지 이 차선으로 경로를 따라갈 수 있는지)
- `[26..30]` 차선별 전방 밀도
- `[31..33]` 앞 신호등: 거리, 색(초록 1 / 노랑 0 / 빨강 −1), 다음 전환까지 남은 시간
- `[34..36]` 앞 비신호 교차로: 거리, 양보 필요 여부, 엇갈리는 차 존재

### Action (2차원)
`action_raw[0]` 가감속 ∈ [−1, 1] (양수 × 최대가속, 음수 × 최대감속),
`action_raw[1]` 차선변경 raw → `lane_change` ∈ {−1, 0, +1}

### Reward
`0.1 × v / 구간 제한속도` − 근접(6 m 미만) 0.1 − 막힘 0.05, 충돌/경로이탈 −5, 완주 +2

## 읽는 법
```python
import glob, numpy as np
for p in sorted(glob.glob("shards/*.npz")):
    d = np.load(p)
    obs, act, rew, nxt = d["observation"], d["action_raw"], d["reward"], d["next_observation"]
    done = d["terminated"] | d["truncated"]
```

## 재현
```bash
set SIM_REUSE=1 & set ROUTE_ASSIST_M=600 & set MERGE_SUMO=1 & set MERGE_STOP=1
set LC_REVERSE_COOLDOWN=3 & set TEAM14_SCENARIO=museum
python tools/collect_data.py --model <model.pt> --out-dir <폴더> --launch 12 --total-steps 10000000
```
코드: GitHub `kiisophii/sumo-yeongdong-bukwon-av` (`sua-assist` 브랜치, `tools/collect_data.py`)

## 한계
- 단일 정책(결정적)으로 모은 on-policy 데이터라 행동 분포가 좁습니다. 오프라인 RL에 쓸 때는
  분포 밖 행동에 주의하세요.
- 보조 규칙이 행동을 바꾼 경우(경로 차로 보조 등) `action_raw`는 정책 원래 출력이고, `lane_change`는
  보조 규칙을 거친 뒤의 명령, `lane_change_applied`는 실제 실행 여부입니다. 둘이 다르면 보조가 개입한 스텝입니다.
- 시뮬레이션 데이터이며 실제 차량 주행 기록이 아닙니다.

## 출처 / 라이선스
- 도로 데이터: © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/)
- 시뮬레이터: [Eclipse SUMO](https://eclipse.dev/sumo/)
- 기반 코드: [bmil-ssu/Artificial-Intelligence-and-Control-for-Autonomous-Driving](https://github.com/bmil-ssu/Artificial-Intelligence-and-Control-for-Autonomous-Driving)
