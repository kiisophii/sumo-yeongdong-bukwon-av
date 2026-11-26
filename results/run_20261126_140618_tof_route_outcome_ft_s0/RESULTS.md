# model_2222 (= checkpoints/model_20000.pt)

- 시작: A'+B+C 순차 4만 (`run_20261126_090857/checkpoints/model_40000.pt`) → 2만 이어 학습
- 신협 우회 경로, 4갈래 지도, 관측 A·B·C + 차체 판정. 집중 출발 50%: 동수원IC 앞 30, 회전교차로 7.5, 부곡 뒤 5, 출구 직후 5, 고속도로 합류 2.5
- 같은 20판(955703411~): 완주 18 (고속도로 합류 충돌 1·이탈 1)
- 평가 환경변수 (A RESULTS.md 공통 설정에 추가):
  `TEAM14_ROUTE_NO_SHINHYUP=1 TEAM14_TOF_BODY_LANES=1 TEAM14_TOF_JUN_INSIDE=1 JUNCTION_SKIP_SHORT_OVERRIDE=50 TEAM14_FOE_UPSTREAM_M=40`
