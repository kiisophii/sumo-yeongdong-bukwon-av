"""학습 곡선 그림 생성 — results/<run>/training_log.csv, eval_log.csv 사용.

사용법:
    python tools/plot_learning_curve.py results/team14_ppo_v1
    python tools/plot_learning_curve.py results/team14_ppo_v1 --out docs/img/learning_curve.png
"""
import argparse
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

for _name in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if any(_name == f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _name
        break
plt.rcParams["axes.unicode_minus"] = False

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def smooth(xs, k=5):
    out = []
    for i in range(len(xs)):
        w = xs[max(0, i - k + 1):i + 1]
        out.append(sum(w) / len(w))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", default=os.path.join(BASE, "docs", "img", "learning_curve.png"))
    args = ap.parse_args()

    tr = read(os.path.join(args.run_dir, "training_log.csv"))
    ev = read(os.path.join(args.run_dir, "eval_log.csv"))
    s = [int(r["steps"]) / 1000 for r in tr]
    rew = [float(r["ep_rew_mean"]) for r in tr]
    es = [int(r["steps"]) / 1000 for r in ev]
    col = [float(r["collision_rate"]) * 100 for r in ev]
    spd = [float(r["mean_speed"]) * 3.6 for r in ev]

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    ax = axes[0]
    ax.plot(s, rew, color="#9bbfae", lw=1)
    ax.plot(s, smooth(rew, 8), color="#0b6b47", lw=2.2)
    ax.set_title("에피소드 보상 (학습 중, 확률적 정책)")
    ax.set_xlabel("학습 스텝 (×1000)")

    ax = axes[1]
    ax.plot(es, col, "o", color="#e8a39b", ms=3)
    ax.plot(es, smooth(col, 6), color="#d33a2c", lw=2.2)
    ax.axhline(5, ls="--", color="#555", lw=1)
    ax.text(es[-1], 6, "목표 5%", ha="right", fontsize=9, color="#555")
    ax.set_ylim(-3, 103)
    ax.set_title("평가 충돌률 % (결정적 정책, 5에피소드)")
    ax.set_xlabel("학습 스텝 (×1000)")

    ax = axes[2]
    ax.plot(es, spd, "o", color="#9fb6d8", ms=3)
    ax.plot(es, smooth(spd, 6), color="#1d4f91", lw=2.2)
    ax.set_title("평가 평균 속도 (km/h)")
    ax.set_xlabel("학습 스텝 (×1000)")

    for a in axes:
        a.grid(alpha=0.3)
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=150)
    print(f"저장: {args.out}")


if __name__ == "__main__":
    main()
