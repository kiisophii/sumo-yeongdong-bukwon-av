"""(팀14, 11/26) 충돌 시드 재현 추적: 마지막 40스텝의 상태·행동·교차로 관측 6칸·주변 차량 + SUMO 충돌 기록."""
import argparse, os, sys, pickle
from collections import deque
import numpy as np
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from env.road_config import ROAD, EGO, TRAFFIC
from env.mdp_config import SIMULATION, OBSERVATION, ACTION
from env import road_builder
from env import sumo_env as se
from env.sumo_env import SumoHighwayEnv
from train import REWARD
from test import load_agent
ap = argparse.ArgumentParser()
ap.add_argument("--model"); ap.add_argument("--episodes", type=int); ap.add_argument("--seed", type=int)
ap.add_argument("--independent-seeds", action="store_true"); ap.add_argument("--no-baseline", action="store_true"); ap.add_argument("--out")
args = ap.parse_args()
seeds = [int(x) for x in open(os.environ["TEAM14_SEED_FILE"]).read().split()]
cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
env = SumoHighwayEnv(cfg, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD, traffic={**TRAFFIC, "reuse_episodes": 0}, gui=False)
pol = load_agent(args.model, env.observation_space.shape[0], env.action_space.shape[0])
last_j = {}
def hook():
    g = env._tof_geometry
    if getattr(g, "_hooked", False): return
    orig = g.junction
    def junction(*a, **k):
        r = orig(*a, **k); last_j["v"] = list(r); return r
    g.junction = junction; g._hooked = True
res = {}
for sd in seeds:
    np.random.seed(sd); obs, _ = env.reset(); hook(); buf = deque(maxlen=40); k = 0; col = []
    while True:
        T = se.traci; e = env.ego_id
        act = np.asarray(pol.predict(obs, deterministic=True), dtype=np.float32).ravel()
        try:
            ln = T.vehicle.getLaneID(e); ex, ey = T.vehicle.getPosition(e); near = []
            for x in T.vehicle.getIDList():
                if x == e: continue
                px, py = T.vehicle.getPosition(x); dd = float(np.hypot(px - ex, py - ey))
                if dd < 40: near.append((x, T.vehicle.getLaneID(x), round(T.vehicle.getSpeed(x), 1), round(dd, 1), round(T.vehicle.getAccumulatedWaitingTime(x), 1)))
            lk = T.vehicle.getNextLinks(e)
            lead = T.vehicle.getLeader(e, 100)
            row = dict(k=k, lane=ln, pos=round(T.vehicle.getLanePosition(e), 1), rem=round(T.lane.getLength(ln) - T.vehicle.getLanePosition(e), 1), v=round(T.vehicle.getSpeed(e), 2),
                       a=float(act[0]), lc=float(act[1]), jun=[round(float(z), 2) for z in last_j.get("v", [])], foe=(bool(lk[0][3]) if lk else None),
                       lead=(lead[0], round(lead[1], 1), round(T.vehicle.getSpeed(lead[0]), 1)) if lead and lead[0] else None,
                       near=sorted(near, key=lambda t: t[3])[:4])
            buf.append(row)
        except Exception as ex_:
            buf.append(dict(k=k, err=str(ex_)[:80]))
        obs, r, term, trunc, info = env.step(act); k += 1
        if term or trunc:
            try:
                for c in se.traci.simulation.getCollisions():
                    col.append(dict(collider=c.collider, victim=c.victim, type=c.type, lane=c.lane, pos=round(c.pos, 1), cs=round(c.colliderSpeed, 1), vs=round(c.victimSpeed, 1)))
            except Exception as ex_:
                col.append(dict(err=str(ex_)[:80]))
            break
    res[sd] = dict(end=info.get("end_reason"), lane=info.get("end_lane"), steps=k, rows=list(buf), col=col)
    print(sd, info.get("end_reason"), info.get("end_lane"), k, col[:1], flush=True)
env.close(); pickle.dump(res, open(args.out, "wb"))
