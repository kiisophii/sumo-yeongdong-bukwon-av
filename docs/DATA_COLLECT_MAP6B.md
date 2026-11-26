# map6b 모델 데이터 수집 방법 (14조, 2026-11-27)

칼럼 설명은 `docs/DATA_COLUMNS_MAP6B.md`.

## 조건 (모두 같아야 함)

| 항목 | 값 |
|---|---|
| 브랜치 | `share/map6b-collect` (`yunho-forkfix-map6b` + 수집 코드) |
| 모델 | `models/map5_ft_200704.pt` (이 브랜치에 포함. sha256 `6ebdc4f6…`) |
| 경로 | 신협오거리 지나는 기존 경로 |
| SUMO | **1.28.0** (`pip install eclipse-sumo==1.28.0 traci==1.28.0 sumolib==1.28.0 libsumo==1.28.0`) |
| 행동 | 결정적 (평가와 같음) |
| 보상 | 충돌 −30, 완주 +30, 막힘 0, 정지 −0.3, 과속 가중치 1.0 |

pip로 설치한 SUMO를 쓰려면 `SUMO_HOME`을 `<파이썬 환경>/Lib/site-packages/sumo`로 맞추고, 시스템 SUMO의 tools를 가리키는 `PYTHONPATH`는 지운다.

## 순서

1. 3판 시험
   ```
   bash tools/collect_map6b.sh <내 시작 시드> 3 data/map6b test3
   python tools/check_collect_map6b.py data/map6b/test3.jsonl.gz
   ```
   마지막 줄이 `PASS`여야 한다. `FAIL`이면 본 수집을 하지 않는다.
2. 본 수집: 100판 묶음으로 나눠 돌린다 (중간에 멈춰도 끝난 묶음은 남는다).
   ```
   WORKERS=3 bash tools/collect_map6b.sh <시드> 100 data/map6b s<시드>
   ```
   10⁷스텝은 약 4,000판 (1판 평균 약 2,500스텝). 3개 병렬로 약 300 step/s.
3. 묶음마다 `check_collect_map6b.py`로 검사한다.

## 시드 범위 (겹치면 같은 판이 중복됨)

| 담당 | 시작 시드 |
|---|---|
| 김수아 | 700000 ~ |
| 조윤호 | 710000 ~ |
| 김동주 | 720000 ~ |
| 김준희 | 730000 ~ |

판 i의 시드 = 시작 시드 + i. 판 시드가 SUMO 시드다. 공식 평가 시드(2026~2325)와 겹치지 않는다.
파일 안의 `episode` 번호는 묶음마다 0부터 다시 시작한다. 판을 구분하는 값은 `episode_meta.seed`다.

## 주의

- 한 폴더에서 수집을 동시에 두 번 돌리지 않는다 (도로 파일을 같이 써서 깨진다). 병렬은 `WORKERS`로 한다.
- 환경변수를 직접 주지 말고 `tools/collect_map6b.sh`로만 실행한다. 스크립트가 다른 환경변수를 지우고 표준값만 켠다. 표준과 다르면 수집 코드가 시작을 거부한다.
- PC가 다르면 같은 시드여도 결과가 똑같지 않다. 같은 PC에서는 같은 시드가 같은 판을 만든다.
- 용량: 압축 후 1스텝 약 0.8 KB. 10⁷스텝이면 JSONL 약 8 GB + NPZ 약 1.2 GB.
