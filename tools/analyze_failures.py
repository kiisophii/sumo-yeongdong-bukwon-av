"""evaluate.py와 같은 시드/순서로 정책을 돌리면서, 실패 에피소드마다
어디서(edge/lane) 어떻게(추돌/측면/순간이동, 직전 차선변경) 끝났는지 기록한다.

사용: TEAM14_SCENARIO=museum python tools/analyze_failures.py . results/failure_analysis.json <model.pt> [<model.pt> ...]
(평가는 tools/evaluate.py와 같은 시드 2026, 20회. 경로 차선 보호는 sumo_env 기본값을 따름)
"""
import json
import os
import sys
from collections import deque

import numpy as np

BASE = os.path.abspath(sys.argv[1])
sys.path.insert(0, BASE)
os.chdir(BASE)

from env.road_config import ROAD, EGO, TRAFFIC  # noqa: E402
from env.mdp_config import SIMULATION, OBSERVATION, ACTION  # noqa: E402
from env import road_builder  # noqa: E402
import env.sumo_env as se  # noqa: E402
from env.sumo_env import SumoHighwayEnv  # noqa: E402
from train import REWARD  # noqa: E402
from test import load_agent  # noqa: E402

SEED, EPISODES = 2026, 20


def run(policy, env):
    eps = []
    for ep in range(EPISODES):
        obs, _ = env.reset()
        hist = deque(maxlen=20)   # 직전 10초(0.5 s × 20)
        n = 0
        while True:
            T = se.traci
            ego = env.ego_id
            try:
                road = T.vehicle.getRoadID(ego)
                lane = T.vehicle.getLaneIndex(ego)
                pos = T.vehicle.getLanePosition(ego)
            except Exception:
                road, lane, pos = None, None, None
            obs, r, term, trunc, info = env.step(policy.predict(obs, deterministic=True))
            n += 1
            hist.append({
                "t": n, "road": road, "lane": lane, "pos": round(pos or 0, 1),
                "speed": round(float(info.get("speed") or 0), 2),
                "gap": None if info.get("gap") is None else round(float(info["gap"]), 2),
                "lc_cmd": int(info.get("lane_change", 0)),
                "lc_applied": bool(info.get("lane_change_applied")),
                "lc_blocked": info.get("lane_change_blocked"),
            })
            if term or trunc:
                break
        T = se.traci
        rec = {"ep": ep + 1, "steps": n, "last": list(hist)[-1]}
        if info.get("lane_end"):
            rec["outcome"] = "lane_end"
        elif info.get("collided"):
            rec["outcome"] = "collision"
            cols = []
            try:
                for c in T.simulation.getCollisions():
                    if env.ego_id in (c.collider, c.victim):
                        cols.append({"ego_role": "collider" if c.collider == env.ego_id else "victim",
                                     "other": c.victim if c.collider == env.ego_id else c.collider,
                                     "other_type": c.victimType if c.collider == env.ego_id else c.colliderType,
                                     "type": c.type, "lane": c.lane, "pos": round(c.pos, 1),
                                     "collider_speed": round(c.colliderSpeed, 2),
                                     "victim_speed": round(c.victimSpeed, 2)})
            except Exception as e:  # noqa: BLE001
                cols.append({"error": repr(e)})
            rec["collisions"] = cols
            rec["teleport"] = not cols
        elif info.get("arrived"):
            rec["outcome"] = "arrival"
        else:
            rec["outcome"] = "timeout"
        h = list(hist)
        rec["lc_applied_last10s"] = sum(x["lc_applied"] for x in h)
        rec["lc_cmd_last10s"] = sum(1 for x in h if x["lc_cmd"] != 0)
        rec["applied_lc_steps_before_end"] = [n - x["t"] for x in h if x["lc_applied"]]
        rec["tail"] = h[-6:]
        eps.append(rec)
        extra = ""
        if rec["outcome"] == "collision":
            c = (rec["collisions"] or [{}])[0]
            extra = (f" {'TELEPORT' if rec['teleport'] else c.get('type')} role={c.get('ego_role')}"
                     f" lane={c.get('lane')}")
        print(f"ep {ep + 1:2d} {rec['outcome']:9s} road={rec['last']['road']} lane={rec['last']['lane']}"
              f" v={rec['last']['speed']}{extra} lc10s={rec['lc_applied_last10s']}", flush=True)
    return eps


def main():
    out, models = sys.argv[2], sys.argv[3:]
    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    env = SumoHighwayEnv(cfg, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD,
                         traffic=TRAFFIC, gui=False)
    res = {}
    try:
        for m in models:
            pol = load_agent(m, env.observation_space.shape[0], env.action_space.shape[0])
            np.random.seed(SEED)
            env.close()
            print(f"\n=== {m} ===", flush=True)
            res[m] = run(pol, env)
    finally:
        env.close()
    with open(out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("saved", out)


if __name__ == "__main__":
    main()
