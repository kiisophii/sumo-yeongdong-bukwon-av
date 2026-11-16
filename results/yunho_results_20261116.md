# 조윤호 실험 결과 정리 (2026-11-14 ~ 11-16)

## yunho_ttc 모델 + 경로 차로 보조 (museum, seed 2026)

| 설정 | 판 | 완주 | 충돌 | 경로이탈 | 시간초과 | 파일 |
|---|---|---|---|---|---|---|
| 기본 | 20 | 40% | 15% | 25% | 20% | (549613e) |
| lane_end 속도 벌점 0.3 학습 | 20 | 20% | 20% | 60% | 0% | evaluation_laneend0.3.json |
| shield 400 m | 20 | 40% | 15% | 25% | 20% | evaluation_yunho_shield400.json |
| assist 800 m | 20 | 65% | 15% | 20% | 0% | evaluation_yunho_assist800.json |
| 요금소 연결 수정 | 20 | 5% | 85% | 5% | 5% | evaluation_yunho_tollfix.json |
| 요금소 수정 + assist | 20 | 15% | 45% | 15% | 25% | evaluation_yunho_tollfix_assist800.json |
| assist + 감속 (하한 없음) | 20 | 70% | 30% | 0% | 0% | evaluation_yunho_assist800_slow.json |
| assist + 감속 + 하한 | 20 | 85% | 15% | 0% | 0% | evaluation_yunho_assist800_slow2.json |
| assist + 감속 + 하한 | 100 | 34% | 66% | 0% | 0% | evaluation_yunho_assist800_slow2_100.json |
| assist 없음 | 100 | 15% | 46% | 14% | 25% | evaluation_yunho_noassist_100.json |

주의: 100판 평가는 시뮬레이션을 50판 동안 재사용(reuse_episodes=50)해서, 약 20판 이후
배경 교통이 막히며 두 조건 모두 같은 구간(17~51, 67~100판)에서 무너졌다.
교통이 정상인 같은 31판(1~16, 52~66)만 보면 assist 없음 완주 48%·경로이탈 35%,
assist + 감속 완주 90%·경로이탈 0%. → 판마다 SUMO를 새로 시작해 다시 평가 필요.

assist/감속 코드는 아직 커밋하지 않음 (env/sumo_env.py, ROUTE_ASSIST_M / ROUTE_ASSIST_DECEL).

## 79회 완주 모델 합류 판단 기록 (trace_merge_decisions_deadline79.json)

모델: route-lane-results 브랜치 run_20261114_153509_route_lane_deadline_600k,
시드 2026~2125, 판마다 SUMO 재시작, TEAM14_MERGE_GAP_OBS=0.
결과: 완주 76, 충돌 12, 경로이탈 11, 신호위반 1.

경로이탈 10판이 부곡IC 가속차로 끝(474882669#1-AddedOnRampEdge_0). 10판 모두 약 90 m 동안
매 스텝 왼쪽 변경을 요청했지만 안전한 틈이 한 번도 없었고(unsafe), 모델은 가감속으로
틈을 만들지 않았다 (본선 차와 나란히 주행, 뒤차 6 m 간격 유지 등).

## 기타 학습 결과 폴더
- run_20261113_173559_city_v5_ttc0.1, run_20261113_184054_city_v5_ttc0.1_part2
- run_20261114_144500_yunho_ttc_laneend0.3
