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
pretty_name: SUMO 영동고속도로 북수원IC 자율주행 주행 데이터셋 (Team 14)
size_categories:
  - 100K<n<1M
---

# SUMO 영동고속도로 북수원IC 자율주행 주행 데이터셋

성균관대학교 「자율주행 인공지능 및 제어」(2026-2) 팀 프로젝트 14팀의 결과 데이터셋입니다.

OpenStreetMap에서 가져온 **영동고속도로 북수원IC 일대(강릉 방향, 약 7.1 km)** 를 SUMO로 구축하고,
그 위에서 PPO로 학습한 자율주행 차량(AV)이 주행하며 남긴 POMDP transition을 담고 있습니다.

## 도로 / 교통 환경
- 3차로 본선(80 km/h) → 북수원IC 진출 → 북수원IC 진입 2차로 합류(5차로) → 차로 감소(5→4→3)
  → 차로 추가 → 분기 → 본선 3차로(100 km/h)
- 배경 차량: Krauss / IDM / EIDM / ACC 4종 혼합, 경로 9개(양방향 본선 + 램프), 총 4,800 대/시간
- 시뮬레이션 1 step = 0.5 초

## 파일
| 파일 | 내용 |
|---|---|
| `*.npz` | 학습용 고정 크기 배열: `observation`(N,31), `action_raw`(N,2), `lane_change`(N,), `reward`, `next_observation`, `terminated`, `truncated`, `episode`, `t`, 감지 차량 좌표(`detected_xy`, `detected_offsets`) |
| `*.jsonl.gz` | 전체 POMDP transition + privileged state(ego 주변 150 m 차량의 위치/속도/차선) |

### Observation (31차원, [-1, 1])
`[0]` 내 속도/vmax, `[1..20]` 5개 차선(좌2·좌1·현재·우1·우2)의 선행/후행 차량 상대거리·상대속도,
`[21..25]` 경로 기준 차선 연결성(200 m 내 차선 종료/경로 이탈 예고), `[26..30]` 차선별 전방 밀도

### Action (2차원)
`action_raw[0]` 가감속 ∈ [-1,1] (±5.4 m/s²), `action_raw[1]` 차선변경 raw → `lane_change` ∈ {-1(우), 0, +1(좌)}

### Reward
`0.1 × v / 구간제한속도` − 근접(6 m 미만) 0.1 − 막힘 0.05, 충돌/경로이탈 −5, 완주 +2

## 읽는 법
```python
import numpy as np
d = np.load("pomdp_xxx.npz")
obs, act, rew, nxt = d["observation"], d["action_raw"], d["reward"], d["next_observation"]
done = d["terminated"] | d["truncated"]
```

## 출처 / 라이선스
- 도로 데이터: © OpenStreetMap contributors, [ODbL](https://opendatacommons.org/licenses/odbl/)
- 시뮬레이터: [Eclipse SUMO](https://eclipse.dev/sumo/)
- 기반 코드: [bmil-ssu/Artificial-Intelligence-and-Control-for-Autonomous-Driving](https://github.com/bmil-ssu/Artificial-Intelligence-and-Control-for-Autonomous-Driving)
