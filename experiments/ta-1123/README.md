# 11/23 조교 답변 반영 (경로 관측 교체 + 제한속도 자르기 제거)

조교 답변: 차선변경 안전 검사·경로 선택은 지금처럼 OK. "경로 따라가려면 차선 몇 번 바꿔야 하는지" 관측은 빼야 함
(대신 "앞 50 m 안에 내 차로가 끝나는지", "다음 갈림길까지 거리·방향"은 OK). 제한속도에서 속도를 자르는 건 수정 필요.

두 환경변수로 켠다. 기본은 꺼짐이라 기존 B 평가는 그대로 재현된다. **학습과 평가 모두 켜야 한다.**

| 변수 | 내용 |
|---|---|
| `TEAM14_ROUTE_OBS=coarse` | 관측 [21..25] 5칸 = 내 차로 끝(남은 거리/50, 안 끝나면 1), 다음 갈림길 거리/600, 갈림길 방향(오른쪽 +1/왼쪽 -1/없음 0), 구간 제한속도/vmax, (내 속도-제한속도)/vmax |
| `TEAM14_NO_SPEED_CAP=1` | 제한속도에서 자르지 않음(차량 물리 최고속도 120 km/h만). 대신 매 스텝 `TEAM14_OVERSPEED_W × max(0, 속도/제한속도 - 1)` 감점 |
| `TEAM14_OVERSPEED_W` | 과속 감점 가중치 (기본 1.0). PC별로 0.5 / 1 / 2 나눠 시험 |

칸 수는 37로 같아서 B(run_20261117_150124_norule_B)에서 이어서 학습할 수 있다.
B에 새 관측을 그냥 넣으면 출발을 안 함(관측 의미가 바뀜) → 이어서 학습 필수.

## 학습 (Git Bash, 저장소 루트)

```bash
B=<B model.pt 경로>
env -u TEAM14_JUN_INSIDE PYTHONIOENCODING=utf-8 TEAM14_SCENARIO=museum \
  TEAM14_ROUTE_OBS=coarse TEAM14_NO_SPEED_CAP=1 TEAM14_OVERSPEED_W=1.0 \
  SIM_REUSE=5 HARD_START_PROB=0.5 STOP_SHAPING=0.2 \
  python -u train.py --lr 3e-5 --gamma 0.995 --collision-penalty 30 --arrival-bonus 30 --blocked-penalty 0 \
  --timesteps 400000 --ckpt-every 40960 --tag coarse_w1 --init-model "$B"
```

## 공식 평가 (시드 2026/2086/2146/2206/2266 × 60)

```bash
env -u HARD_START_PROB -u STOP_SHAPING -u TEAM14_JUN_INSIDE PYTHONIOENCODING=utf-8 TEAM14_SCENARIO=museum SIM_REUSE=1 \
  TEAM14_ROUTE_OBS=coarse TEAM14_NO_SPEED_CAP=1 \
  python -u tools/evaluate.py --episodes 60 --seed 2026 --independent-seeds --no-baseline --model <model.pt> --out results/coarse_2026.json
```

## 11/24 추가: 정지 local optimum 대응

11/23 D(B에서 그대로 이어서, W=1, 40만): 300판 전부 출발점에서 정지 → teleport, 완주 0.
- B의 첫 층이 바뀐 5칸을 예전 의미로 읽어 가속 출력이 음수로 포화 → 출발 안 함.
- 정지하면 600스텝 뒤 teleport(-30)가 γ=0.995로 할인돼 약 -1.5 → "출발 안 하기"가 local optimum.

대응 (둘 다 쓴다):
1. `python tools/zero_route_inputs.py <B model.pt> B_zero5.pt` 로 만든 B_zero5.pt를 `--init-model`로 쓴다 (5칸 가중치 0 + bias 보정 → 바로 다시 달림).
2. `TEAM14_IDLE_PEN=0.1`: 앞이 비어 있고(앞차 20 m 밖) 앞 60 m 신호가 빨강·노랑이 아닌데 1 m/s 미만이면 매 스텝 -0.1 (reward shaping). 처음부터 학습에도 켠다.
3. (선택) `TEAM14_RESET_LOGSTD=-0.5`: 이어서 학습할 때 탐색 폭을 다시 키운다.

정지 감점은 학습 때만 켜면 된다(평가 결과에는 영향 없음). TEAM14_ROUTE_OBS, TEAM14_NO_SPEED_CAP는 평가 때도 켠다.
