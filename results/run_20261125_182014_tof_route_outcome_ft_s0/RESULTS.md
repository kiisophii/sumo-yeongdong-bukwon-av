# 차간 감점 강화 10만 스텝 (11/25, map6)

- 시작 모델: 실험 ① 최종 모델 `tof-progress-1123-entropy` 커밋 `deed142`의 `results/run_20261125_165520_tof_route_outcome_ft_s0/model.pt`
- 지도: map6 (`yunho-forkfix-map6` 커밋 `6a66e55`·`fbea463`·`98959f5`의 지도 파일 변경을 `6bd1285` 도로 위에 적용). 학습 때 쓴 설정은 이 폴더의 `road_config.py`
- 비교 실험: "New session" 쪽이 같은 설정에 차간 감점 기존값(0.1, RSS b=5)으로 학습

## 설정

```bash
LANE_ENTROPY_OVERRIDE=0.02 SPAWN_CLEAR_OVERRIDE=0 COLLISION_PENALTY_OVERRIDE=20 PROGRESS_TOTAL_OVERRIDE=150 \
PROGRESS_OVERSPEED_W_OVERRIDE=0.3 PROGRESS_SPEED_W_OVERRIDE=0.1 PROGRESS_SPEED_OFFSET_OVERRIDE=0.1 \
PROGRESS_GAP_PENALTY_OVERRIDE=0.2 GAP_RSS_DECEL_OVERRIDE=3 FORK_RELATIVE_OVERRIDE=1 FORK_SUMO_DIR_OVERRIDE=1 \
EGO_STALL_S_OVERRIDE=0 DROP_MUST_YIELD_OVERRIDE=0 CKPT_EVERY_OVERRIDE=20480 \
HARD_START_TARGETS_OVERRIDE='1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,1116479399@300,51066582#1@300,51066582#1@300,51066582#1@300,51066582#1@300,51066582#1@300,51066582#1@300,667354422#1@300,667354422#1@300,1235185544@300,1235185544@300,-40839116#4@150,568664967#4@100' \
python3 -u experiments/tof-route-outcome-ft/run_tof_route_outcome_ft.py train --steps 102400 --hard-start-prob 0.5 \
  --init-model results/run_20261125_165520_tof_route_outcome_ft_s0/model.pt
```

| 항목 | 값 |
|---|---|
| 차간 감점 | **0.2** (기존 0.1), 2 m + 1초 + **RSS b=3** (기존 5) |
| 속도 보상 | 0.1 × (속도/제한속도) − 0.1 (OFFSET 0.1) |
| 차선 엔트로피 | 0.02 |
| 정지 실패 / 근처 생성 차 지우기 | 끔 / 끔 |
| 집중 출발 50% | 동수원IC 출구 20%, 부곡 영업소 15%, 창룡대로 5%, 동수원 요금소 뒤 5%, 신협 2.5%, 회전교차로 2.5% |

## 학습 보상

| 구간 | 평균 학습 보상 | 학습 중 평가 속도 (m/s) |
|---|---:|---|
| 0~2.5만 | −4.3 | 12.5 / 11.7 |
| 2.5~5만 | −20.0 | 9.4 / 8.7 / 9.6 |
| 5~7.5만 | −27.1 | 13.2 / 12.9 |
| 7.5~10만 | −8.7 | 10.7 / 11.9 |

학습 중 평가(5판) 완주: @81920 1/5, @92160 3/5 (체크포인트 없음), @102400 0/5

## 최종 `model.pt` 20판 (시드 955703411~955703430, map6, 근처 생성 차 지우기 끔)

결과 파일: `model_eval10_seed955703411.json`, `model_eval10_seed955703421.json` (10판씩, 시드 = 시작 시드 + 회차라 같은 20판)

| 결과 | 위치 | 차선 | 판 수 |
|---|---|---|---:|
| **완주** | 광교박물관 주차장 `611808767` | | **5** |
| 경로 이탈 | 부곡 영업소 뒤 갈림길 `468211809#1` (인천 방향) | 0번 | 9 |
| 충돌 | 동수원IC 진출 램프 `468241513` | 1번 | 5 |
| 충돌 | 신협오거리 `:1681517542` | 0번 | 1 |

평균 속도 약 41 km/h. 동수원IC 출구 놓침 0, 합류 정체 충돌 0.

### 시작 모델(실험 ①)과 비교 (같은 시드 20판, map6)

| | 실험 ① 모델 | 이번 |
|---|---:|---:|
| 완주 | 1 | **5** |
| 부곡 영업소 뒤 갈림길 이탈 | 12 | 9 |
| 램프 추돌 | 2 | 5 |
| 신협오거리·회전교차로 | 3 | 1 |
| 영업소 부스·합류 정체 | 2 | 0 |
