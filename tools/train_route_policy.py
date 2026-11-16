"""(팀14) 길 선택 AI 학습 + 비교 평가.

  학습:  python tools/train_route_policy.py --episodes 200
  비교:  python tools/train_route_policy.py --compare results/route_policy/route_policy.json --episodes 60

운전은 tools/rule_driver.py(규칙 기반)로 고정해서 "길 선택"만의 효과를 본다.
에피소드는 갈림 구간을 지나면(또는 실패하면) 끝낸다 — 길 선택 학습에 필요한 건 그 구간뿐.
비교: 같은 시드로 계산 방식(fastest) / 학습한 AI(learned) / 항상 주황 / 항상 파랑.
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from env.road_config import ROAD, EGO, TRAFFIC                       # noqa: E402
from env import road_builder                                           # noqa: E402
from env.mdp_config import SIMULATION, OBSERVATION, ACTION, REWARD     # noqa: E402
from env.sumo_env import SumoHighwayEnv                                # noqa: E402
from algorithms.route_policy import RoutePolicy                        # noqa: E402
from tools.rule_driver import rule_action                              # noqa: E402


def make_env(mode):
    ROAD["route_choice"]["mode"] = mode
    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    return SumoHighwayEnv(cfg_path=cfg, road=ROAD, ego=EGO, mdp_sim=SIMULATION,
                          mdp_obs=OBSERVATION, action=ACTION, reward=REWARD,
                          traffic=TRAFFIC, gui=False)


def run_branch(env, seed):
    """갈림 구간을 지날 때까지 달리고 (선택, 통과시간 또는 None, 상황, 막힌 길)."""
    np.random.seed(seed)
    obs, _ = env.reset(seed=seed)
    for _ in range(env.max_steps):
        obs, _, term, trunc, _ = env.step(rule_action(obs, env.vmax))
        if env.branch_time is not None or term or trunc:
            break
    return env.route_name, env.branch_time, env.route_context, (env.disrupted or {}).get("route")


def train(args):
    env = make_env("learned")
    pol = RoutePolicy(list(env.route_alts), 3 * len(env.route_alts), lr=args.lr, seed=args.seed)
    env.route_selector = pol.sample
    out = os.path.join(BASE, "results", "route_policy")
    os.makedirs(out, exist_ok=True)
    rows = []
    for ep in range(args.episodes):
        name, bt, ctx, dis = run_branch(env, args.seed + ep)
        if bt is None or ctx is None:          # 갈림 구간 전에 실패 → 학습에 안 씀
            rows.append([ep, name, "", dis, ""])
            continue
        adv = pol.update(ctx, name, -bt / 100.0)
        p = float(pol.probs(ctx)[pol.names.index(name)])
        rows.append([ep, name, round(bt, 1), dis, round(p, 3)])
        print(f"ep {ep:3d} 선택={name:6s} 막힌길={str(dis):6s} 통과={bt:6.1f}s "
              f"P(선택)={p:.2f} adv={adv:+.2f}", flush=True)
        if (ep + 1) % 20 == 0:
            pol.save(os.path.join(out, "route_policy.json"))
    pol.save(os.path.join(out, "route_policy.json"))
    with open(os.path.join(out, "train_log.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["episode", "route", "branch_time_s", "disrupted", "p_chosen"])
        w.writerows(rows)
    env.close()


def compare(args):
    pol = RoutePolicy.load(args.compare)
    res = {}
    for mode in ["fastest", "learned", "orange", "blue"]:
        env = make_env(mode)
        if mode == "learned":
            env.route_selector = pol.greedy
        times, picks = [], []
        for ep in range(args.episodes):
            name, bt, _, dis = run_branch(env, 10_000 + ep)
            picks.append((name, dis))
            if bt is not None:
                times.append(bt)
        env.close()
        res[mode] = {
            "mean_branch_time_s": float(np.mean(times)) if times else None,
            "n": len(times), "episodes": args.episodes,
            "orange_blocked": sum(1 for _, d in picks if d == "orange"),
            "picked_blue_when_orange_blocked": sum(1 for n, d in picks if d == "orange" and n == "blue"),
            "blue_blocked": sum(1 for _, d in picks if d == "blue"),
            "picked_blue_when_blue_blocked": sum(1 for n, d in picks if d == "blue" and n == "blue"),
        }
        print(mode, res[mode], flush=True)
    out = os.path.join(BASE, "results", "route_policy", "compare.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("저장:", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--lr", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--compare", default=None, help="학습한 route_policy.json으로 비교 평가")
    a = ap.parse_args()
    compare(a) if a.compare else train(a)
