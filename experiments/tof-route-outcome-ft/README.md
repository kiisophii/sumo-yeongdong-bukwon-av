# Team 14 ToF PPO 이어학습

이 패키지는 이전에 사용한 `sumo-tof-progress-clean` 소스에 적용한다. 초기값은 [팀의 기존 ToF PPO 600k 체크포인트](https://github.com/kiisophii/sumo-yeongdong-bukwon-av/blob/de2cdcfcfe8e23371c06b531fe03e0402176ebb3/results/run_20261120_202557_tof_multi_lane_bonus_600k/model.pt)에서 변환했다.

## Windows CMD

ZIP을 다운로드 폴더에 풀면 `tof_route_outcome_ft` 폴더가 생긴다. 아래 명령어를 한 줄씩 실행한다.

```bat
cd /d "%USERPROFILE%\sumo-tof-progress-clean"
git apply --check "%USERPROFILE%\Downloads\tof_route_outcome_ft\tof_route_outcome_ft.patch" && git apply "%USERPROFILE%\Downloads\tof_route_outcome_ft\tof_route_outcome_ft.patch"
.venv\Scripts\python.exe -u "%USERPROFILE%\Downloads\tof_route_outcome_ft\run_tof_route_outcome_ft.py" train --steps 102400 --hard-start-prob 0.5
```

학습 첫 로그에 `obs_dim=41`과 `이어서 학습`이 표시된다. 학습 결과는 `results\run_*_tof_route_outcome_ft_s0`에 저장된다. 이전처럼 전 구간 출발만 쓰려면 학습 명령의 `--hard-start-prob 0.5`를 `--hard-start-prob 0`으로 바꾼다.

## 관측과 초기 가중치

- 현재 ToF 39칸의 순서를 유지하고 마지막에 갈림길 거리와 방향을 추가한다. 거리 단위는 600 m 대비 비율이고 방향은 왼쪽 −1, 직진 0, 오른쪽 +1이다. 600 m 안에 분기가 없으면 `[1, 0]`을 넣는다.
- 갈림길은 출발 시 선택한 도로 경로에서 찾는다. 방향은 들어오는 도로와 나가는 도로의 중심선 각도로 계산한다. 물리적 차로 끝 5칸은 기존대로 경로와 무관한 50 m 관측이다.
- 600k 체크포인트에서 의미가 같은 33개 입력의 가중치를 옮겼다. 제한속도, 50 m 차로 끝 5칸, 갈림길 2칸의 입력 가중치는 0으로 초기화했다.
- 삭제한 차로 점수 5칸에 모두 같은 기준값 1을 넣었을 때의 기여분을 첫 층 편향에 한 번 더했다. 새 모델의 입력에는 차로 점수와 신호 남은 시간이 없다. 나머지 신경망 가중치는 기존 체크포인트와 같다.
- 기본 차선변경 안전 검사는 기존 코드의 설정을 사용한다. 제한속도를 넘으면 주행 보상에서 감점한다. 차량 자체 최대 속도는 그대로 적용한다.

## 보상과 출발점

| 기준 | 값 |
| --- | --- |
| 예정 경로를 따라 실제 전진한 거리 | 스텝마다 `150 × 전진 거리 / 전체 경로 길이` |
| 완주 | +10 |
| 차량 충돌·경로 이탈·순간이동·신호 위반 | −10 |
| 과속 | 스텝마다 `−0.1 × max(0, 속도 / 제한속도 − 1)` |
| 양보 의무가 있고 교차 차량이 접근 중일 때 실제 진입 | −2 |

학습에서 어려운 구간 출발을 선택하는 확률은 기본 50%다. 대상은 의왕역 회전교차로, 부곡IC 진입, 영동고속도로 차로 감소 구간이다. 기존 SUMO 환경의 출발점 선택 함수를 사용한다. 선택된 구간에 차량을 삽입하기 어렵거나 경로상 적절한 시작점이 없으면 원래 출발점을 사용한다. 중간 평가, 별도 평가, GUI는 원래 출발점에서 시작한다.

## 평가와 GUI

아래 명령들은 가장 최근에 저장한 이 실험의 모델을 사용한다. 다른 체크포인트를 선택하려면 명령 끝에 `--model "results\<폴더>\model.pt"`를 추가한다.

```bat
.venv\Scripts\python.exe -u "%USERPROFILE%\Downloads\tof_route_outcome_ft\run_tof_route_outcome_ft.py" evaluate --episodes 20 --seed 2326
.venv\Scripts\python.exe -u "%USERPROFILE%\Downloads\tof_route_outcome_ft\run_tof_route_outcome_ft.py" gui --episodes 5
```

GUI 창이 뜰 때마다 ▶ 버튼을 누른다.

## 검증 범위

기존 저장소 사본에서 패치 적용, 41칸 체크포인트 로드, 2,048스텝 학습과 평가 1판을 확인했다. 원래 출발점과 어려운 구간 출발이 각각 적용되는 것도 확인했다. 평가 1판은 신협오거리 진입로에서 차량 충돌로 끝났다. 전체 학습 후 성능은 별도로 평가한다.

## 40칸 관측 (11/25, 양보 의무 칸 제거)

`DROP_MUST_YIELD_OVERRIDE=1`이면 41칸 관측에서 35번 칸(양보 의무, 표지판·지도 수준 정보)을 뺀 40칸으로 학습·평가한다.
교차로 거리(34번)와 ToF로 본 교차 차량(36번)은 남고, 양보는 충돌 −20·양보 위반 −2(SUMO 실제 상태로 판정)로 배운다.
41칸 모델을 `--init-model`로 주면 첫 층에서 35번 열만 지운 `<모델 이름>_obs40.pt`를 같은 폴더에 만들고 그걸로 이어 학습한다.
40칸 모델을 평가·GUI로 볼 때도 `DROP_MUST_YIELD_OVERRIDE=1`을 같이 켠다.

Windows 명령 프롬프트, 저장소 루트에서 (60만 스텝 모델에서 이어 20만 스텝, 11/25 차간 거리 학습과 같은 보상·출발 설정):

```bat
set DROP_MUST_YIELD_OVERRIDE=1
set COLLISION_PENALTY_OVERRIDE=20
set PROGRESS_OVERSPEED_W_OVERRIDE=0.3
set PROGRESS_SPEED_W_OVERRIDE=0.1
set PROGRESS_SPEED_OFFSET_OVERRIDE=0.05
set PROGRESS_GAP_PENALTY_OVERRIDE=0.1
set HARD_START_TARGETS_OVERRIDE=377057231,377057231,1307152438,50981265,568664967#4,51066582#1
set PYTHONIOENCODING=utf-8
.venv\Scripts\python.exe -u experiments\tof-route-outcome-ft\run_tof_route_outcome_ft.py train --steps 200704 --hard-start-prob 0.5 --init-model results\run_20261124_184657_tof_route_outcome_ft_s0\model.pt
```

평가 (위 `set` 줄을 같은 창에서 먼저 실행한 상태):

```bat
.venv\Scripts\python.exe -u experiments\tof-route-outcome-ft\run_tof_route_outcome_ft.py evaluate --model results\<새 결과 폴더>\model.pt --episodes 10 --seed 2026
```

- 차간 거리 감점(`PROGRESS_GAP_PENALTY_OVERRIDE`): 같은 차로 앞차 거리 < 2 m + 내 속도 × 1초 이면 매 스텝 −0.1. 0이면 꺼짐.
- 11/25 평가에서 덕영대로 `491135704#3`(부곡IC 직전 79 m) 1번 차선 이탈이 9판 나왔다. 이 구간을 직접 연습하려면 `HARD_START_TARGETS_OVERRIDE`에 `491135704#3`을 추가한다.
