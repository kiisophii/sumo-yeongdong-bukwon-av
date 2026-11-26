# model_2222 (= checkpoints/model_20000.pt)

- 시작: A'+B+C 순차 4만 (`run_20261126_090857/checkpoints/model_40000.pt`) → 2만 이어 학습
- 신협 우회 경로, 4갈래 지도, 관측 A·B·C + 차체 판정. 집중 출발 50%: 동수원IC 앞 30, 회전교차로 7.5, 부곡 뒤 5, 출구 직후 5, 고속도로 합류 2.5
- 같은 20판(955703411~): 완주 18 (고속도로 합류 충돌 1·이탈 1)
- 평가 환경변수 (A RESULTS.md 공통 설정에 추가):
  `TEAM14_ROUTE_NO_SHINHYUP=1 TEAM14_TOF_BODY_LANES=1 TEAM14_TOF_JUN_INSIDE=1 JUNCTION_SKIP_SHORT_OVERRIDE=50 TEAM14_FOE_UPSTREAM_M=40`

## 무작위 100판 (세션 2, `random.Random(2222)` 시드 100개 — 이전 100판·300판·20판 시드와 겹치지 않음)

- 조건: 우회 경로, A·B·C + 차체 판정 (위 평가 환경변수), 신호 연동 끔, SUMO 1.28.0
- 판별: `model_2222_eval100C_noshin_r2222_rand_seeds.csv`, json `model_2222_eval100C_noshin_r2222_runs/`
- 결과: **완주 87**, 충돌 6, 신호 위반 4 (회전교차로 앞), 이탈 3 (고속도로 합류 2, 부곡 부스 출구 1). 평균 50.8 km/h
- 충돌 6판 추적: 차로 변경 3 (진출 램프 고리 옆면, 동수원IC 뒤 끼어들기, 부곡 부스 출구 옆 트럭), 브레이크 약함 2 (합류 정체, 회전교차로 앞 대기열), 회전교차로 진입 늦은 인지 1
- 같은 판으로 제동 강화 6만(`../run_20261126_151417_tof_route_outcome_ft_s0`)은 완주 91, 충돌 4 — 이 6판 모두 완주
