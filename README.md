# 14조 최종 코드 — 철도박물관 → 수원광교박물관 자율주행 (SUMO × PPO)

자율주행 인공지능 및 제어 (ICE3052, 2026-2) 팀 프로젝트의 최종 제출 코드다.
팀원: 김동주(팀장), 김수아, 김준희, 조윤호

- 프로젝트 페이지: https://kiisophii.github.io/sumo-yeongdong-bukwon-av/
- 데이터(Hugging Face): https://huggingface.co/datasets/kimsua/team14-sumo-driving-data
- 코드 저장소: https://github.com/kiisophii/sumo-yeongdong-bukwon-av (이 제출본은 `share/map6b-collect` 브랜치, 커밋 `c00ba3d` 기준)

이 제출본은 최종 모델의 평가, 데이터 수집, 주행 영상 녹화에 실제로 쓴 코드다.
외부 저장소는 제출 뒤에도 바뀔 수 있으므로 이 압축 파일을 최종본으로 본다.

## 1. 결과 요약

의왕 철도박물관 주차장에서 수원광교박물관 주차장까지 약 13.6 km를, 주행 중 보조 규칙 없이 PPO 정책 하나가 주행한다.

| 평가 | 판 수 | 완주 | 차량 충돌 | 차로 끝 이탈 | 신호 위반 |
|---|---|---|---|---|---|
| 같은 시드 300판, SUMO 1.28.0 | 300 | 262 (87.3%) | 6 (2.0%) | 23 | 9 |
| 같은 시드 300판, SUMO 1.27.1 (다른 PC) | 300 | 268 (89.3%) | 12 (4.0%) | 16 | 4 |
| 데이터 수집 주행, SUMO 1.28.0 (PC 3대) | 6,300 | 5,572 (88.4%) | 162 (2.6%) | 400 | 159 |

- 같은 시드 = 2026, 2086, 2146, 2206, 2266에서 각 60판, 판마다 SUMO를 새로 시작.
- 같은 시드여도 SUMO 버전과 PC가 다르면 판별 결과가 달라진다. 같은 PC에서는 같은 시드가 같은 결과로 재현된다.
- 판별 결과 파일: `results/eval300_map6b_shinhyup_vs_detour/shinhyup/orig_*.json`, 설명은 같은 폴더의 `EVAL300.md`.

## 2. 최종 모델

| 항목 | 값 |
|---|---|
| 파일 | `models/map5_ft_200704.pt` |
| sha256 | `6ebdc4f6462497299d03b0197e3c9086dd3e20d9c7af31871a63abaa22d36b36` |
| 정책 | PPO 하이브리드 정책. 가감속은 Normal 분포, 차선변경은 3-way Categorical 분포(왼쪽·유지·오른쪽) |
| 네트워크 | 은닉층 256 × 256 |
| 관측 | 실수 37칸 (`TEAM14_ROUTE_OBS=coarse`) |
| 학습 | 갈림길 판정 수정 후 처음부터 100만 스텝(learning rate 1e-4) → 고친 지도(map5)에서 learning rate 5e-5로 이어 학습 → 10만 스텝마다 저장한 체크포인트를 같은 시드 300판으로 평가해 20만 스텝 체크포인트를 고름 |
| PPO 설정 | n_steps 2048, n_epochs 10, minibatch 64, clip 0.2, gamma 0.995, GAE lambda 0.95 |
| 보상 설정 | 충돌·차로 끝 −30, 도착 +30, 빨간불 통과 −5, 양보 위반 −1, 정지 −0.3, 앞차 6 m 미만 −0.1, 속도 +0.1 × (속도 ÷ 차로 제한속도), 과속 감점 가중치 1.0 |

이어 학습을 실행한 정확한 명령 줄은 기록이 남아 있지 않다. 위 값은 학습 로그의 하이퍼파라미터와 평가 기록에서 확인한 것이다.

## 3. 실행 환경

**압축은 영문 경로에 풀 것.** 폴더 경로에 한글이 들어 있으면 SUMO의 `netconvert`가 도로망을 만들다 실패한다(Windows에서 확인). 영문과 숫자로만 된 폴더에 풀면 된다.

- Python 3 + `requirements.txt`의 패키지 (numpy, torch, gymnasium, sumolib, traci 등)
- SUMO **1.28.0** (`SUMO_HOME` 설정). 위 결과는 `eclipse-sumo` 1.28.0과 `libsumo` 1.28.0에서 얻었다.
- GPU는 필요 없다(CPU로 학습·평가).

```bash
pip install -r requirements.txt
pip install eclipse-sumo==1.28.0 libsumo==1.28.0 traci==1.28.0 sumolib==1.28.0
```

## 4. 꼭 맞춰야 하는 환경변수

최종 모델은 아래 조건에서 학습·평가했다. 이 값이 아니면 같은 37칸이어도 일부 칸의 의미가 달라져 모델이 제대로 주행하지 못한다.

```bash
export TEAM14_SCENARIO=museum          # 철도박물관 → 광교 시나리오
export TEAM14_ROUTE_OBS=coarse         # 경로 관측 3칸(차로 끝, 갈림길 거리·방향)
export TEAM14_NO_SPEED_CAP=1           # 속도 상한으로 행동을 자르지 않음
export TEAM14_OVERSPEED_W=1.0          # 과속 감점 가중치 (보상)
export TEAM14_IDLE_PEN=0.3             # 정지 감점 (보상)
export TEAM14_ROUTE_NO_SHINHYUP=0      # 신협오거리를 지나는 기존 경로
export SIM_REUSE=1                     # 판마다 SUMO를 새로 시작
```

주행 중 보조 규칙에 해당하는 환경변수(`ROUTE_ASSIST_M`, `MERGE_SUMO`, `MERGE_STOP`, `RED_STOP`, `JUNCTION_YIELD`, `LC_REVERSE_COOLDOWN` 등)는 모두 설정하지 않는다. `tools/collect_map6b.sh`가 이 조건을 맞추는 방법을 그대로 보여 준다.

## 5. 실행 방법

### 5-1. 평가 (같은 시드 300판 중 한 시드)

```bash
python tools/evaluate.py --no-baseline --independent-seeds --episodes 60 --seed 2026 \
    --model models/map5_ft_200704.pt --out results/eval_2026.json
```

시드 2026, 2086, 2146, 2206, 2266으로 다섯 번 실행하면 300판이다.

### 5-2. 데이터 수집

```bash
bash tools/collect_map6b.sh <시작 시드> <판 수> <저장 폴더> [이름]
# 예) bash tools/collect_map6b.sh 700000 100 data/map6b s700000
python tools/check_collect_map6b.py data/map6b/s700000.jsonl.gz   # 수집 조건 15개 검사, 마지막 줄 PASS
```

- 판 i의 시드 = 시작 시드 + i. 판 시드가 SUMO 시드다.
- 표준 조건(환경변수, 보상 설정, 모델 해시)과 다르면 수집이 시작되지 않는다.
- 수집 방법은 `docs/DATA_COLLECT_MAP6B.md`, 칼럼 설명은 `docs/DATASET_README.md`(Hugging Face 데이터셋 카드와 같은 내용).

### 5-3. 학습

```bash
python train.py --lr 5e-5 --gamma 0.995 --collision-penalty 30 --arrival-bonus 30 --blocked-penalty 0 \
    --timesteps 200000 --ckpt-every 102400 --init-model <시작 모델> --tag <이름>
```

위는 옵션의 사용 예이고, 최종 모델을 만든 정확한 명령 줄은 2절에 적은 대로 기록이 없다.

## 6. 폴더 구성

| 경로 | 내용 |
|---|---|
| `env/` | SUMO 환경. `env/sumo_env.py`(관측·행동·보상·종료), `env/road_config.py`·`env/museum/`(경로와 지도 원본, 로드뷰로 고친 차로 수·연결) |
| `algorithms/`, `train.py` | PPO 구현과 학습 스크립트 |
| `tools/evaluate.py` | 평가 |
| `collect_pomdp_data.py`, `tools/collect_map6b.sh`, `tools/check_collect_map6b.py` | 데이터 수집, 표준 조건 실행, 수집 조건 검사 |
| `models/map5_ft_200704.pt` | 최종 모델 가중치 |
| `results/` | 평가 결과(JSON). 최종 300판은 `results/eval300_map6b_shinhyup_vs_detour/`, 그 밖에 map5·map6 단계의 300판 결과와 이전 실험 기록 |
| `docs/DATASET_README.md`, `docs/DATA_COLUMNS_MAP6B.md`, `docs/DATA_COLLECT_MAP6B.md` | 데이터 칼럼과 수집 방법 |
| `docs/README_old_bukwon_ic.md` | 프로젝트 초기(북수원IC 구간) README. 지금 내용과 다르며 기록용으로만 둠 |
| `project_materials/`, `README_course.md` | 수업에서 제공한 자료 |

## 7. 이 제출본에서 뺀 것

과제 안내에 따라 최종 모델 가중치 하나만 남기고 불필요한 파일을 뺐다.

- 학습 중간 체크포인트와 이전 실험의 모델 파일 (남긴 것은 `models/map5_ft_200704.pt` 하나)
- 학습 로그, 평가 로그, TensorBoard 기록, 캐시
- 주행 영상, 발표 자료, 프로젝트 페이지 파일 (위 링크의 프로젝트 페이지에서 볼 수 있다)
- 수집한 주행 데이터. Hugging Face와 데이터셋 제출 압축 파일에 있다.

`results/`에는 평가 결과 JSON과 하이퍼파라미터 기록만 남아 있다. 이전 실험 폴더의 모델 파일은 없으므로 그 실험을 다시 평가하려면 저장소에서 받아야 한다.

## 8. 알아 둘 점

- 이 제출본을 영문 경로에 풀어 5-1의 평가 명령을 시드 2026으로 1판 실행해 완주하는 것을 확인했다(SUMO 1.28.0).
- `env/sumo/highway.net.xml` 머리말의 파일 경로는 제출본에서 파일 이름만 남겼다. 도로망 내용은 바꾸지 않았다.
- 경로는 의왕역 회전교차로 뒤부터 부곡 영업소 앞까지 두 갈래(약 13.6 km, 약 14.5 km)이고, 환경이 판마다 예상 통행시간이 짧은 쪽을 고른다.
- 남은 실패는 부곡IC 가속차로(95 m), 의왕역 회전교차로와 진입로, 동수원IC 진출, 신협오거리에 몰려 있다. 위치별 판 수는 `results/eval300_map6b_shinhyup_vs_detour/EVAL300.md`에 있다.
