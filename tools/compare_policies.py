"""정책 비교 평가 — 주행 지표 + 차선변경 명령이 막힌 이유별 횟수.

v1(수정 전 게이트로 학습)과 v2(제동 가능성 검사 게이트로 재학습)를 같은 시드로 비교한다.
"unsafe" = 안전 게이트가 막은 위험한 변경 시도. 정책이 스스로 위험한 시도를
덜 할수록 줄어든다 (재학습의 목적).

사용법:
    python tools/compare_policies.py --model results/team14_ppo_v2/model.pt --tag v2 --episodes 300
    python tools/compare_policies.py --model results/team14_ppo_v2/model.pt --tag v2_nobrake --no-brake-check
결과: results/policy_<tag>.json
"""
import argparse
import json
import os
import sys

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from env.road_config import ROAD, EGO, TRAFFIC  # noqa: E402
from env.mdp_config import SIMULATION, OBSERVATION, ACTION  # noqa: E402
from env import road_builder  # noqa: E402
from env.sumo_env import SumoHighwayEnv  # noqa: E402
from train import REWARD  # noqa: E402
from test import load_agent  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--episodes", type=int, default=300)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--no-brake-check", action="store_true",
                    help="제동 가능성 검사를 끈 게이트(수정 전)로 평가")
    args = ap.parse_args()

    # 병렬 실행 시 서로의 도로 파일을 덮어쓰지 않도록 태그별 폴더에 생성
    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", f"sumo_{args.tag}"))
    env = SumoHighwayEnv(cfg, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD,
                         traffic=TRAFFIC, gui=False)
    if args.no_brake_check:
        env.lc_brake_decel = env.lc_follower_decel = 0.0
    agent = load_agent(os.path.join(BASE, args.model), 31, 2)
    np.random.seed(args.seed)

    ends = {"collision": 0, "lane_end": 0, "arrival": 0, "timeout": 0}
    speeds, times, lcs = [], [], []
    blocked = {"unsafe": [], "no_lane": [], "junction": []}
    commands = []
    try:
        for ep in range(args.episodes):
            obs, _ = env.reset()
            n, lc, cmd = 0, 0, 0
            b = {k: 0 for k in blocked}
            while True:
                obs, r, term, trunc, info = env.step(agent.predict(obs, deterministic=True))
                n += 1
                if info.get("speed") is not None:
                    speeds.append(info["speed"])
                if info.get("lane_change", 0) != 0:
                    cmd += 1
                    if info.get("lane_change_applied"):
                        lc += 1
                reason = info.get("lane_change_blocked")
                if reason in b:
                    b[reason] += 1
                if term or trunc:
                    break
            end = ("lane_end" if info.get("lane_end") else "collision" if info.get("collided")
                   else "arrival" if info.get("arrived") else "timeout")
            ends[end] += 1
            times.append(n * SIMULATION["step_length"])
            lcs.append(lc)
            commands.append(cmd / n)
            for k in blocked:
                blocked[k].append(b[k])
            print(f"  ep {ep + 1:3d}/{args.episodes}: steps={n:4d} {end} lc={lc} unsafe={b['unsafe']}", flush=True)
    finally:
        env.close()

    E = args.episodes
    res = {
        "tag": args.tag, "model": args.model, "seed": args.seed, "episodes": E,
        "brake_check": not args.no_brake_check,
        **{f"{k}_count": v for k, v in ends.items()},
        "mean_speed_kmh": float(np.mean(speeds)) * 3.6,
        "mean_travel_time_s": float(np.mean(times)),
        "lane_changes_per_ep": float(np.mean(lcs)),
        "lane_command_step_share": float(np.mean(commands)),
        **{f"blocked_{k}_per_ep": float(np.mean(v)) for k, v in blocked.items()},
    }
    out = os.path.join(BASE, "results", f"policy_{args.tag}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
