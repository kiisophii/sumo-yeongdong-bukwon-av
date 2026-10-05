"""차선변경 안전 게이트의 제동 가능성 검사 전/후 비교 (같은 모델, 같은 시드).

사용법:
    python tools/compare_gate.py --mode new --episodes 300
    python tools/compare_gate.py --mode old --episodes 300   # 제동 검사 끔 (수정 전)
결과: results/gate_<mode>.json
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
from tools.evaluate import run  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["old", "new"], required=True)
    ap.add_argument("--model", default="results/team14_ppo_v1/model.pt")
    ap.add_argument("--episodes", type=int, default=300)
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()

    # 병렬 실행 시 서로의 도로 파일을 덮어쓰지 않도록 모드별 폴더에 생성
    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", f"sumo_{args.mode}"))
    env = SumoHighwayEnv(cfg, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD,
                         traffic=TRAFFIC, gui=False)
    if args.mode == "old":
        env.lc_brake_decel = 0.0
        env.lc_follower_decel = 0.0
    agent = load_agent(os.path.join(BASE, args.model), 31, 2)
    np.random.seed(args.seed)
    try:
        res = run(agent, env, args.episodes)
    finally:
        env.close()
    res.update(mode=args.mode, model=args.model, seed=args.seed)
    out = os.path.join(BASE, "results", f"gate_{args.mode}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
