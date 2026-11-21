"""Replay eight junction collisions and time ToF detections before impact."""

import argparse
import csv
from datetime import datetime
import json
import os
from pathlib import Path
import sys


DEFAULT_MODEL = Path("results/run_20261120_202557_tof_multi_lane_bonus_600k/model.pt")
TARGET_LANE = ":1681517542_4_0"
BASE_SEED = 2326
EXPECTED = {1: 189, 21: 201, 28: 178, 38: 219, 70: 218, 76: 209, 86: 165, 99: 201}


def matching_tracks(env, frame, api, lane_id):
    """Name visible tracks that satisfy the existing junction observation test."""
    route = api.vehicle.getRoute(env.ego_id)
    next_index = api.vehicle.getRouteIndex(env.ego_id) + 1
    if not 0 < next_index < len(route):
        return set()
    geometry = env._tof_geometry
    lane = geometry.net.getLane(lane_id)
    connection = next((c for c in lane.getOutgoing() if c.getTo().getID() == route[next_index]), None)
    if connection is None:
        return set()
    matches = set()
    for approach, stop, width in geometry._conflicting_approaches(connection):
        for vehicle, track in frame.tracks.items():
            projected = approach.project(track.center, track.direction)
            if projected is None:
                continue
            position, lateral = projected
            if lateral <= width and stop - position <= max(8.0, 4.0 * (track.speed or 0.0)):
                matches.add(vehicle)
    return matches


def lead_time(rows, collision_time, predicate):
    first = next((row["time_s"] for row in rows if predicate(row)), None)
    return None if first is None else round(collision_time - first, 3)


def replay(env, policy, sumo_env, seed, expected_steps):
    obs, _ = env.reset()
    api = sumo_env.traci
    ego = env.ego_id
    junction_end = env.obs_dim - env.tof_observation_dims
    rows = []
    while True:
        frame = env._tof_frame()
        lane_id = api.vehicle.getLaneID(ego)
        distance_obs, must_yield, conflict = map(float, obs[junction_end - 3:junction_end])
        hazard = must_yield > 0 and conflict > 0
        matches = matching_tracks(env, frame, api, lane_id) if hazard else set()
        if hazard and not matches:
            raise RuntimeError("The ToF trace no longer matches this version of env/tof_observation.py.")
        action = policy.predict(obs, deterministic=True)
        row = {
            "seed": seed,
            "episode": seed - BASE_SEED + 1,
            "observation_step": len(rows),
            "time_s": api.simulation.getTime(),
            "lane_id": lane_id,
            "ego_speed_mps": api.vehicle.getSpeed(ego),
            "distance_to_lane_end_m": api.lane.getLength(lane_id) - api.vehicle.getLanePosition(ego),
            "junction_distance_obs": distance_obs,
            "must_yield_obs": must_yield,
            "conflict_obs": conflict,
            "hazard_obs": hazard,
            "candidate_ids": set(frame.targets),
            "detected_ids": set(frame.tracks),
            "conflict_ids": matches,
            "accel_cmd": float(action[0]),
        }
        obs, _, terminated, truncated, info = env.step(action)
        executed = info.get("action_executed")
        row["executed_accel_cmd"] = executed[0] if executed is not None else None
        row["step_end_reason"] = info["end_reason"]
        rows.append(row)
        if terminated or truncated:
            break

    partners = {}
    if info["end_reason"] == "collision":
        for event in api.simulation.getCollisions():
            if event.collider == ego:
                partners[event.victim] = event.type
            elif event.victim == ego:
                partners[event.collider] = event.type
    collision_time = api.simulation.getTime()
    reproduced = (info["end_reason"] == "collision" and info["end_lane"] == TARGET_LANE
                  and (expected_steps is None or len(rows) == expected_steps))
    summary = {
        "seed": seed,
        "episode": seed - BASE_SEED + 1,
        "steps": len(rows),
        "expected_steps": expected_steps,
        "outcome": info["end_reason"],
        "end_lane": info["end_lane"],
        "matches_original_log": reproduced if expected_steps is not None else None,
        "collision_time_s": collision_time if info["end_reason"] == "collision" else None,
        "final_approach_first_hazard_lead_s": None,
        "partners": [],
    }
    if info["end_reason"] == "collision":
        # An earlier, unrelated junction can also raise the generic hazard flag.
        approach = [row for row in rows if row["time_s"] >= collision_time - 30.0]
        summary["final_approach_first_hazard_lead_s"] = lead_time(
            approach, collision_time, lambda row: row["hazard_obs"])
        for vehicle, collision_type in partners.items():
            summary["partners"].append({
                "vehicle_id": vehicle,
                "collision_type": collision_type,
                "first_context_candidate_lead_s": lead_time(rows, collision_time, lambda row: vehicle in row["candidate_ids"]),
                "first_tof_detection_lead_s": lead_time(rows, collision_time, lambda row: vehicle in row["detected_ids"]),
                "first_tof_conflict_lead_s": lead_time(rows, collision_time, lambda row: vehicle in row["conflict_ids"]),
            })
    for row in rows:
        row["partner_candidate"] = any(vehicle in row["candidate_ids"] for vehicle in partners) if partners else None
        row["partner_detected"] = any(vehicle in row["detected_ids"] for vehicle in partners) if partners else None
        row["partner_classified_conflict"] = any(vehicle in row["conflict_ids"] for vehicle in partners) if partners else None
        for key in ("candidate_ids", "detected_ids", "conflict_ids"):
            row[key] = "|".join(sorted(row[key]))
    return summary, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--seed", type=int, action="append", help="Override the eight replay seeds for testing")
    parser.add_argument("--out", type=Path, help="Output path prefix for .json and .csv")
    args = parser.parse_args()
    root = Path.cwd()
    if not (root / "tools/evaluate.py").is_file():
        parser.error("Run from the SUMO repository folder.")
    if not args.model.is_file():
        parser.error(f"Model not found: {args.model}")

    os.environ.update(
        TEAM14_SCENARIO="museum", TEAM14_TOF_OBS="1", TEAM14_TOF_REAR_DENSITY="0",
        TEAM14_TOF_LEAD_HOLD_S="0", TEAM14_TOF_LEAD_GAP_WINDOW="0", SUMO_USE_LIBSUMO="1",
        HARD_START_PROB="0", STOP_SHAPING="0", TEAM14_TOF_JUNCTION_YIELD="0",
        JUNCTION_YIELD="0", ROUTE_ASSIST_M="0", ROUTE_SHIELD_M="0", RED_STOP="0",
        MERGE_SUMO="0", MERGE_STOP="0", ZIPPER_FOLLOW="0", LC_REVERSE_COOLDOWN="0",
    )
    for key in ("SIM_REUSE", "ASSIST_PROB"):
        os.environ.pop(key, None)
    sys.path.insert(0, str(root))

    from env import sumo_env
    from tools import evaluate

    cfg = evaluate.road_builder.build(evaluate.ROAD, evaluate.EGO, evaluate.TRAFFIC, str(root / "env/sumo"))
    env = evaluate.SumoHighwayEnv(
        cfg, evaluate.ROAD, evaluate.EGO, evaluate.SIMULATION, evaluate.OBSERVATION,
        evaluate.ACTION, evaluate.REWARD, traffic={**evaluate.TRAFFIC, "reuse_episodes": 0}, gui=False,
    )
    out = args.out or root / "results" / "eval300" / f"tof_junction_81_{datetime.now():%Y%m%d_%H%M%S_%f}"
    out.parent.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        policy = evaluate.load_agent(str(args.model.resolve()), env.obs_dim, env.act_dim)
        seeds = args.seed or [BASE_SEED + ep - 1 for ep in EXPECTED]
        with out.with_suffix(".csv").open("x", encoding="utf-8-sig", newline="") as handle:
            writer = None
            for seed in seeds:
                evaluate.np.random.seed(seed)
                summary, rows = replay(env, policy, sumo_env, seed, EXPECTED.get(seed - BASE_SEED + 1))
                if writer is None:
                    writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                    writer.writeheader()
                writer.writerows(rows)
                handle.flush()
                results.append(summary)
                print(json.dumps(summary, ensure_ascii=False), flush=True)
    finally:
        env.close()
    with out.with_suffix(".json").open("x", encoding="utf-8") as handle:
        json.dump({"model": str(args.model.resolve()), "target_lane": TARGET_LANE, "episodes": results}, handle, indent=2)
    print(f"Saved: {out}.csv and {out}.json")


if __name__ == "__main__":
    main()
