"""팀14 학습별 속도 변화 기록 만들기.

학습 로그의 중간 평가 줄(`[eval @스텝] ... 평균속도=...`)과 학습 중 평균 보상을 모아
speed_trend.csv(전체 기록)와 SPEED_TREND.md(요약)를 만든다.
사용법: python experiments/speed-trend/build_speed_trend.py [로그 폴더] [출력 폴더]
"""
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "logs")
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else HERE
os.makedirs(OUT_DIR, exist_ok=True)

# (로그 파일, 실험 이름, 설정, 시작 누적 스텝, 결과 폴더)
RUNS = [
    ("train_s0.log", "기본1", "처음부터, 전진 20", 0, "run_20261123_153022_tof_progress_s0"),
    ("train_s0_part2.log", "기본2", "전진 20", 51200, "run_20261123_172414_tof_progress_s0"),
    ("train_s0_part3.log", "A", "전진 20 (그대로)", 350000, "run_20261123_181756_tof_progress_s0"),
    ("train_time_part1.log", "B", "전진 20 + 시간 감점 0.003", 350000, "run_20261123_182301_tof_progress_time_s0"),
    ("train_p100_part1.log", "C1", "전진 100", 350000, "run_20261123_192921_tof_progress_p100_s0"),
    ("train_p100_part2.log", "C2", "전진 100", 650000, "run_20261123_203116_tof_progress_p100_s0"),
    ("train_p150.log", "P150", "전진 150", 350000, "run_20261124_031351_tof_progress_p150_s0"),
    ("train_route_ft.log", "600k-과속0.1", "600k 초기값, 갈림길 41칸, 전진 150, 과속 0.1 (중단)", 600000,
     "run_20261124_050403_tof_route_outcome_ft_overspeed0.1_aborted"),
    ("train_route_ft_os1.log", "600k-과속1.0", "600k 초기값, 갈림길 41칸, 전진 150, 과속 1.0", 600000,
     "run_20261124_054352_tof_route_outcome_ft_s0"),
    ("train_route_ft_os1_part2.log", "600k-과속1.0-2", "위에서 이어서 (중단)", 907200,
     "run_20261124_064716_tof_route_outcome_ft_part2_aborted"),
    ("train_p150_fork.log", "P150갈림길-과속1.0", "P150 + 갈림길, 과속 1.0", 650000,
     "run_20261124_071448_tof_route_outcome_ft_p150fork_os1.0"),
    ("train_p150_fork_os03_sp005.log", "P150갈림길-속도0.05", "P150 + 갈림길, 과속 0.3, 속도 0.05", 650000,
     "run_20261124_095014_tof_route_outcome_ft_p150fork_os0.3_sp0.05"),
    ("train_p150_fork_os03_sp01.log", "P150갈림길-속도0.1", "P150 + 갈림길, 과속 0.3, 속도 0.1", 650000,
     "run_20261124_111212_tof_route_outcome_ft_s0"),
    ("train_speed_offset.log", "속도-0.05기준", "위 속도0.1 최종에서 이어서, 속도 보상 0.1×(속도/제한)−0.05", 957200,
     "run_20261124_123728_tof_route_outcome_ft_s0"),
    ("train_newmap.log", "새지도", "위 모델에서 이어서, 새 지도(경로 끝 12.85 km, 부곡중앙로 교통, 끊긴 차로 복원)", 1157904,
     "run_20261124_141151_tof_route_outcome_ft_s0"),
    ("train_fail20.log", "새지도-실패20", "위 새지도 모델에서 이어서, 실패 벌점 -10 → -20", 1358608,
     "run_20261124_152824_tof_route_outcome_ft_s0"),
    ("train_600k_part1.log", "60만-1", "실패 -20 모델에서 이어서, 어려운 구간 출발에 동수원IC 앞(50981265) 추가", 1559312, "(학습 중)"),
    ("train_600k_part2.log", "60만-2", "위에서 이어서", 1760016, "(학습 중)"),
    ("train_600k_part3.log", "60만-3", "위에서 이어서", 1960720, "(학습 중)"),
]

# 공식 20판 평가 (시드 2026, 결정적 정책)
OFFICIAL = [
    ("C1", "누적 65만", 6.5, "0/20", "신협오거리 앞 19"),
    ("C2", "누적 95만", 6.6, "0/20", "회전교차로 직전 8, 신협오거리 전후 12"),
    ("P150", "누적 65만", 8.5, "0/20", "신협오거리 통과 19 → 회전교차로 직전"),
    ("P150갈림길-과속1.0", "누적 95만", 1.2, "0/20", "출발 직후 20"),
    ("P150갈림길-속도0.05", "누적 95만", 6.4, "0/20", "신협오거리 진입로 18, 회전교차로 1, 부곡IC 진입로 1"),
    ("P150갈림길-속도0.1", "누적 85.5만 (20.48만 체크포인트)", 8.3, "0/20", "의왕역 회전교차로 직전 20 (0.90 km)"),
    ("속도-0.05기준", "누적 115.8만", 12.9, "0/20",
     "부곡중앙로 18 (1.19~1.34 km), 영동고속도로 1 (11.1 km), 신협오거리 충돌 1"),
    ("새지도 (시드 2026 10판 + 92840 10판)", "누적 135.9만", 39.3, "0/20",
     "순간이동 0. 경로 이탈 14 (부곡중앙로 회전 차로 12, 부곡IC 진입로 1, 영동고속도로 1), 충돌 6 (신협 4, 영동고속도로 2)"),
]

EVAL = re.compile(r"\[eval @(\d+)\].*?충돌률=(\d+)%\s+완주율=(\d+)%\s+평균속도=([0-9.]+)m/s")
UPD = re.compile(r"\[update\s+\d+\] steps=\s*(\d+)\s+ep_rew_mean=([-0-9.na]+)")

rows, summary = [], []
for log, name, setting, offset, folder in RUNS:
    path = os.path.join(LOG_DIR, log)
    if not os.path.isfile(path):
        continue
    rewards = []
    evals = []
    for line in open(path, encoding="utf-8", errors="ignore"):
        m = UPD.search(line)
        if m and m.group(2) != "nan":
            rewards.append((int(m.group(1)), float(m.group(2))))
        m = EVAL.search(line)
        if m:
            evals.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4))))
    for step, fail, arrive, v in evals:
        near = min(rewards, key=lambda r: abs(r[0] - step))[1] if rewards else ""
        rows.append([name, setting, folder, step, offset + step, v, round(v * 3.6, 1), arrive, fail, near])
    if evals:
        vs = [e[3] for e in evals]
        last5 = vs[-5:]
        summary.append((name, setting, f"{offset // 10000}만 → {(offset + evals[-1][0]) // 10000}만",
                        vs[0], max(vs), sum(last5) / len(last5), vs[-1], len(evals),
                        rewards[-1][1] if rewards else None))

with open(os.path.join(OUT_DIR, "speed_trend.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f)
    w.writerow(["실험", "설정", "결과 폴더", "이번 학습 스텝", "누적 스텝", "평가 평균속도(m/s)",
                "평가 평균속도(km/h)", "평가 완주율(%)", "평가 실패율(%)", "학습 중 평균 보상(가까운 업데이트)"])
    w.writerows(rows)

with open(os.path.join(OUT_DIR, "SPEED_TREND.md"), "w", encoding="utf-8") as f:
    f.write("# 학습별 속도 변화 기록\n\n")
    f.write("중간 평가(학습 중 1만 스텝마다 5판, 결정적 정책)의 평균 속도. 전체 값은 [speed_trend.csv](speed_trend.csv).\n")
    f.write("시간 제한(1,800초) 안에 13.6 km를 완주하려면 평균 **7.5 m/s(27 km/h) 이상**이 필요하다.\n\n")
    f.write("| 실험 | 설정 | 누적 스텝 | 첫 평가 | 최고 | 마지막 5회 평균 | 마지막 | 평가 횟수 | 마지막 학습 보상 |\n")
    f.write("|---|---|---|---:|---:|---:|---:|---:|---:|\n")
    for name, setting, span, first, best, last5, last, n, rew in summary:
        f.write(f"| {name} | {setting} | {span} | {first:.1f} | {best:.1f} | {last5:.1f} | {last:.1f} | {n} | "
                f"{'' if rew is None else f'{rew:+.1f}'} |\n")
    f.write("\n단위: m/s\n\n## 공식 20판 평가 (시드 2026)\n\n")
    f.write("| 실험 | 시점 | 평균 속도 (km/h) | 완주 | 멈춘 곳 |\n|---|---|---:|---:|---|\n")
    for name, when, kmh, arr, where in OFFICIAL:
        f.write(f"| {name} | {when} | {kmh} | {arr} | {where} |\n")
print(f"rows={len(rows)} runs={len(summary)}")
