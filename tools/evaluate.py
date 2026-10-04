"""최종 평가 스크립트 — 충돌률(목표 ≤ 5%) 등 주행 지표를 여러 정책에 대해 측정.

test.py와 달리
  · 실패 원인을 "충돌"과 "경로 이탈(끝나는 차선에 갇힘)"로 나눠 집계하고
  · 규칙 기반 기준선(rule-based baseline)과 함께 비교하며
  · 결과를 JSON으로 저장한다 (보고서/발표 표 작성용).

사용법:
    python tools/evaluate.py --model results/team14_ppo_v1/model.pt --episodes 100
    python tools/evaluate.py --model results/team14_ppo_v1/model.pt --model results/bc_xxx/model.pt
    python tools/evaluate.py --baseline-only --episodes 50
"""
import argparse
import json
import os
import sys
import time

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from env.road_config import ROAD, EGO, TRAFFIC  # noqa: E402
from env.mdp_config import SIMULATION, OBSERVATION, ACTION  # noqa: E402
from env import road_builder  # noqa: E402
from env.sumo_env import SumoHighwayEnv  # noqa: E402
from train import REWARD  # noqa: E402
from test import load_agent  # noqa: E402


class RuleBasedDriver:
    """비교용 규칙 기반 운전자 (학습 없음).

    - 종방향: 앞차와 시간간격 1.5초 + 5m를 유지하도록 가속/감속
    - 횡방향: 현재 차선이 곧 끝나면(연결성 < 1) 이어지는 쪽 차선으로 이동
    관측 벡터만 사용하므로 RL 정책과 같은 정보 조건이다.
    """

    def __init__(self, vmax, visibility):
        self.vmax, self.W = vmax, visibility

    def predict(self, obs, deterministic=True):
        v = obs[0] * self.vmax
        gap, dv = obs[9] * self.W, obs[10] * self.vmax
        a = 0.6
        if obs[9] < 1.0:
            safe = 5.0 + 1.5 * v
            if gap < safe or dv < -3.0:
                a = -0.6 if gap > 0.6 * safe else -1.0
        lc = 0.0
        if 0.0 <= obs[23] < 0.99:        # 현재 차선이 경로상 곧 끝남
            lc = 1.0 if obs[22] > obs[24] else -1.0
        return np.array([a, lc], dtype=np.float32)


def run(policy, env, episodes):
    out = {"collision": 0, "lane_end": 0, "arrival": 0, "timeout": 0}
    speeds, returns, lengths, lcs, min_gaps = [], [], [], [], []
    for ep in range(episodes):
        obs, _ = env.reset()
        ret, n, lc, mg = 0.0, 0, 0, float("inf")
        while True:
            obs, r, term, trunc, info = env.step(policy.predict(obs, deterministic=True))
            ret += r
            n += 1
            if info.get("speed") is not None:
                speeds.append(info["speed"])
            if info.get("gap") is not None:
                mg = min(mg, info["gap"])
            if info.get("lane_change", 0) != 0 and info.get("lane_change_applied"):
                lc += 1
            if term or trunc:
                break
        if info.get("lane_end"):
            out["lane_end"] += 1
        elif info.get("collided"):
            out["collision"] += 1
        elif info.get("arrived"):
            out["arrival"] += 1
        else:
            out["timeout"] += 1
        returns.append(ret)
        lengths.append(n)
        lcs.append(lc)
        if mg < float("inf"):
            min_gaps.append(mg)
        print(f"  ep {ep + 1:3d}/{episodes}: steps={n:4d} return={ret:7.2f} "
              f"{'충돌' if info.get('collided') and not info.get('lane_end') else '경로이탈' if info.get('lane_end') else '완주' if info.get('arrived') else '시간초과'}",
              flush=True)
    res = {k + "_rate": v / episodes for k, v in out.items()}
    res.update({
        "failure_rate": (out["collision"] + out["lane_end"]) / episodes,
        "episodes": episodes,
        "mean_speed_mps": float(np.mean(speeds)) if speeds else 0.0,
        "mean_return": float(np.mean(returns)),
        "mean_length_steps": float(np.mean(lengths)),
        "mean_travel_time_s": float(np.mean(lengths)) * SIMULATION["step_length"],
        "lane_changes_per_ep": float(np.mean(lcs)),
        "min_gap_median_m": float(np.median(min_gaps)) if min_gaps else None,
    })
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", default=[],
                    help="평가할 model.pt (여러 번 지정 가능)")
    ap.add_argument("--episodes", type=int, default=100)
    ap.add_argument("--baseline-only", action="store_true")
    ap.add_argument("--no-baseline", action="store_true")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--out", default=os.path.join(BASE, "results", "evaluation.json"))
    args = ap.parse_args()

    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    env = SumoHighwayEnv(cfg, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD,
                         traffic=TRAFFIC, gui=False)
    policies = []
    if not args.no_baseline:
        policies.append(("rule_based", RuleBasedDriver(env.vmax, env.visibility)))
    if not args.baseline_only:
        for m in args.model:
            path = m if os.path.isabs(m) else os.path.join(BASE, m)
            policies.append((os.path.relpath(path, BASE),
                             load_agent(path, env.observation_space.shape[0],
                                        env.action_space.shape[0])))
    results = {}
    try:
        for name, pol in policies:
            np.random.seed(args.seed)   # 같은 시드 → 정책 간 공정 비교
            env.close()                 # 시뮬레이션도 새로 시작
            print(f"\n=== {name} ({args.episodes} episodes) ===")
            t = time.time()
            results[name] = run(pol, env, args.episodes)
            results[name]["wall_time_s"] = time.time() - t
    finally:
        env.close()

    print("\n─── 결과 요약 ───")
    print(f"{'정책':<40}{'충돌':>7}{'경로이탈':>9}{'완주':>7}{'평균속도(km/h)':>15}{'통과시간(s)':>12}")
    for name, r in results.items():
        print(f"{name:<40}{r['collision_rate']:>7.0%}{r['lane_end_rate']:>9.0%}"
              f"{r['arrival_rate']:>7.0%}{r['mean_speed_mps'] * 3.6:>15.1f}"
              f"{r['mean_travel_time_s']:>12.1f}")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
