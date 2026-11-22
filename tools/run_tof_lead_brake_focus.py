"""Train and evaluate PPO for car following in the original SUMO traffic."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys

import gymnasium as gym
import numpy as np


BASE_MODEL = Path("results/run_20261122_143625_tof_ppo_tof_residual_40k/checkpoints/model_40960.pt")
FOCUS_LANE = "1307152438_3"
LEAD_RANGE = 120.0
FOCUS_SHARE = 0.65
FOCUS_STEPS = 96
FOCUS_DISTANCE_FROM_END_M = (800.0, 1100.0)
RUN_TAG = "tof_lead_brake_natural"


class LeadObservation(gym.ObservationWrapper):
    """Append bumper gap and relative speed from visible tracks on the ego lane."""

    def __init__(self, env):
        super().__init__(env)
        self.observation_space = gym.spaces.Box(
            -1.0, 1.0, shape=(env.observation_space.shape[0] + 2,), dtype=np.float32,
        )

    def observation(self, observation):
        env = self.unwrapped
        if not np.any(observation):
            return np.pad(observation, (0, 2))
        frame = env._tof_frame()
        geometry = env._tof_geometry
        lane = geometry.net.getLane(env._tof_lane_id)
        path, current_lane, prefix = geometry._lane_path(lane)
        origin = current_lane.project(frame.center)
        speed = float(observation[0]) * env.vmax
        lead = None
        if origin is not None:
            ref = prefix + origin[0]
            for track in frame.tracks.values():
                projection = path.project(track.center, track.direction)
                if projection is None:
                    continue
                along, lateral = projection
                delta = along - ref
                if delta <= 0.0 or lateral > lane.getWidth() / 2.0:
                    continue
                gap = max(0.0, delta - (env._tof_length + track.length) / 2.0)
                if gap > LEAD_RANGE or (lead is not None and gap >= lead[0]):
                    continue
                relative_speed = track.speed - speed if track.speed is not None else 0.0
                lead = (gap, relative_speed)
        extra = (1.0, 1.0) if lead is None else (lead[0] / LEAD_RANGE, lead[1] / env.vmax)
        return np.concatenate((observation, np.clip(np.asarray(extra, dtype=np.float32), -1.0, 1.0)))


def lead_interaction(obs, action, new_speed, vmax):
    """Count policy responses using the ToF features present before each action."""
    visible = bool(0.0 <= obs[-2] < 1.0)
    closing = visible and float(obs[-1]) * vmax < -1.0
    return {
        "lead_visible_steps": int(visible),
        "lead_closing_steps": int(closing),
        "brake_cmd_while_closing_steps": int(closing and float(action[0]) < -0.05),
        "decel_while_closing_steps": int(closing and new_speed is not None
                                         and new_speed < float(obs[0]) * vmax - 0.01),
    }


def configure_environment():
    os.environ.update(
        TEAM14_SCENARIO="museum", TEAM14_TOF_OBS="1", TEAM14_TOF_REAR_DENSITY="0",
        TEAM14_TOF_LEAD_HOLD_S="0", TEAM14_TOF_LEAD_GAP_WINDOW="0",
        TEAM14_TOF_ZIPPER_CONFLICT_CONTINUITY="0", TEAM14_TOF_ZIPPER_ETA_GATE="0",
        SUMO_USE_LIBSUMO="1", HARD_START_PROB="0", STOP_SHAPING="0",
        TEAM14_TOF_JUNCTION_YIELD="0", JUNCTION_YIELD="0", ROUTE_ASSIST_M="0",
        ROUTE_SHIELD_M="0", RED_STOP="0", MERGE_SUMO="0", MERGE_STOP="0", ZIPPER_FOLLOW="0",
        LC_REVERSE_COOLDOWN="0", JUNCTION_ROW="0", MERGE_COOP="0", MERGE_SPEEDMATCH="0",
        ROUNDABOUT_VMAX="0", LC_TRACK_SUMO="0", EXEC_ACTION_BUFFER="0",
    )
    for key in ("SIM_REUSE", "ASSIST_PROB"):
        os.environ.pop(key, None)


def make_env(repo):
    from env import road_builder, sumo_env
    from env.road_config import ROAD, EGO, TRAFFIC
    from env.mdp_config import SIMULATION, OBSERVATION, ACTION
    from train import REWARD

    class LeadApproachEnv(sumo_env.SumoHighwayEnv):
        def _tof_junction_start(self, route_id, *, focus_lane=None):
            # Reuse the reset's ego-only start and blocked-insertion fallback.
            edge, lane_index = focus_lane.rsplit("_", 1)
            api = sumo_env.traci
            edges = api.route.getEdges(route_id)
            if edge not in edges[:-1] or int(lane_index) >= api.edge.getLaneNumber(edge):
                raise ValueError(f"Training lane {focus_lane} is missing from route {route_id}.")
            index = edges.index(edge)
            length = api.lane.getLength(focus_lane)
            if length <= FOCUS_DISTANCE_FROM_END_M[1]:
                raise ValueError(f"Training lane {focus_lane} is too short for the start range.")
            position = length - self.np_random.uniform(*FOCUS_DISTANCE_FROM_END_M)
            focused_route = f"tof_lead_{route_id}_{index}"
            if focused_route not in api.route.getIDList():
                api.route.add(focused_route, edges[index:])
            return focused_route, lane_index, str(position), edges[index + 1]

    cfg = road_builder.build(ROAD, EGO, TRAFFIC, str(repo / "env" / "sumo"))
    traffic = {**TRAFFIC, "reuse_episodes": 0}
    env = LeadApproachEnv(cfg, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD,
                         traffic=traffic, gui=False)
    if env.observation_space.shape != (39,):
        raise ValueError(f"Expected 39 baseline observations, got {env.observation_space.shape}.")
    return env


def focused_env(base, share, seed):
    from collections import Counter
    from env.junction_curriculum import JunctionCurriculum

    class LeadCurriculum(JunctionCurriculum):
        def __init__(self, env):
            super().__init__(env, share=share, seed=seed, focus_steps=FOCUS_STEPS,
                             target_lane=FOCUS_LANE, warmup_jitter_s=60.0)
            self.totals = Counter()

        def reset(self, *, seed=None, options=None):
            requested = self.share > 0.0 and (
                self.share == 1.0 or self.total == 0 or self.focus_total < self.share * self.total
            )
            if 0.0 < self.share < 1.0:
                obs, info = super().reset(seed=seed, options=options)
            else:
                options = {**(options or {}), "tof_junction_focus": self.share == 1.0,
                           "tof_junction_focus_lane": self.target_lane,
                           "tof_junction_warmup_jitter_s": self.warmup_jitter_s}
                obs, info = self.env.reset(seed=seed, options=options)
                self.focused = info.get("tof_junction_focus", False)
                self.exit_edge = info.get("tof_junction_focus_exit_edge")
                self.elapsed = 0
            self.previous_obs = obs
            self.totals["focus_requests"] += int(requested)
            self.totals["focus_fallback_episodes"] += int(requested and not self.focused)
            self.totals["focus_episodes"] += int(self.focused)
            return obs, info

        def step(self, action):
            obs, reward, terminated, truncated, info = super().step(action)
            if self.focused:
                metrics = lead_interaction(self.previous_obs, action, info["speed"], self.unwrapped.vmax)
                self.totals.update(metrics)
                info["lead_interaction"] = metrics
                if truncated and info["end_reason"] is None:
                    info["end_reason"] = "focus_window"
            self.previous_obs = obs
            return obs, reward, terminated, truncated, info

    return LeadCurriculum(LeadObservation(base))


def training(args, repo, output):
    from algorithms.ppo import PPO
    from train import HPARAMS
    from utils.buffer import RolloutBuffer
    from utils.logger import RunLogger

    env = focused_env(make_env(repo), args.focus_share, args.seed)
    settings = {**HPARAMS, "n_steps": args.rollout, "seed": args.seed, "lr": 3e-5, "gamma": 0.995}
    agent = PPO(env.observation_space.shape[0], env.action_space.shape[0],
                buffer=RolloutBuffer(), **settings)
    agent.load(str(repo / BASE_MODEL), append_zero_inputs=2)
    logger = RunLogger(str(output), use_tensorboard=False)
    details = {"checkpoint": str(BASE_MODEL), "steps": args.steps, "lead_range_m": LEAD_RANGE,
               "focus_share": args.focus_share, "focus_lane": FOCUS_LANE,
               "background_traffic": "original", "hyperparameters": settings}
    (output / "hparams.json").write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Results: {output}", flush=True)
    try:
        agent.learn(env, args.steps, logger=logger, ckpt_dir=str(output / "checkpoints"),
                    ckpt_every=args.rollout)
        agent.save(str(output / "model.pt"))
    finally:
        summary = {"steps": env.total, "focus_steps": env.focus_total, **env.totals}
        (output / "focus_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        try:
            logger.close()
        finally:
            env.close()
    print(f"Focus summary: {json.dumps(summary)}")
    print(f"Model: {output / 'model.pt'}")


def evaluation(args, repo, output):
    from collections import Counter
    from test import load_agent
    from tools.evaluate import run

    base = make_env(repo)
    results = {}
    for label, model in (("baseline", repo / BASE_MODEL), ("trained", args.model)):
        print(f"\n=== {label} ===", flush=True)
        uses_longer_obs = label == "trained"
        env = (focused_env(base, 1.0, args.seed) if args.mode == "probe"
               else LeadObservation(base) if uses_longer_obs else base)
        dim = base.observation_space.shape[0] + 2 * int(uses_longer_obs)
        policy = load_agent(str(model), dim, env.action_space.shape[0])
        try:
            if args.mode == "eval":
                results[label] = run(policy, env, args.episodes, episode_seed=args.seed)
                continue
            results[label] = []
            for seed in range(args.seed, args.seed + args.episodes):
                np.random.seed(seed)
                obs, info = env.reset(seed=seed)
                if not info.get("tof_junction_focus"):
                    row = {"seed": seed, "outcome": "focus_start_blocked", "steps": 0}
                else:
                    counts = Counter()
                    steps = 0
                    while True:
                        action = policy.predict(obs if uses_longer_obs else obs[:-2], deterministic=True)
                        obs, _, done, truncated, info = env.step(action)
                        counts.update(info["lead_interaction"])
                        steps += 1
                        if done or truncated:
                            break
                    row = {"seed": seed, "outcome": info["end_reason"],
                           "end_lane": info["end_lane"], "steps": steps, **counts}
                results[label].append(row)
                print(json.dumps(row), flush=True)
        finally:
            env.close()
    (output / "comparison.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Comparison: {output / 'comparison.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    train = modes.add_parser("train")
    train.add_argument("--steps", type=int, default=40960)
    train.add_argument("--rollout", type=int, default=1024)
    train.add_argument("--seed", type=int, default=31)
    train.add_argument("--focus-share", type=float, default=FOCUS_SHARE)
    for name, episodes, seed in (("eval", 100, 2326), ("probe", 12, 3000)):
        mode = modes.add_parser(name)
        mode.add_argument("--model", type=Path)
        mode.add_argument("--episodes", type=int, default=episodes)
        mode.add_argument("--seed", type=int, default=seed)
    args = parser.parse_args()
    repo = Path.cwd()
    if not (repo / "tools" / "evaluate.py").is_file():
        repo = Path.home() / "sumo-tof-junction-reward"
    if not (repo / BASE_MODEL).is_file():
        parser.error(f"Missing checkpoint: {repo / BASE_MODEL}")
    if args.mode == "train":
        if not 0.0 <= args.focus_share <= 1.0:
            parser.error("--focus-share must be between 0 and 1.")
        if args.rollout < 2 or args.steps < args.rollout or args.steps % args.rollout:
            parser.error("--steps must be a positive multiple of --rollout, which must be at least 2.")
    else:
        if args.episodes < 1:
            parser.error("--episodes must be positive.")
        if not args.model:
            args.model = max((repo / "results").glob(f"run_*_{RUN_TAG}/model.pt"),
                             default=None)
        if args.model is None or not args.model.is_file():
            parser.error("No trained model found. Run train first or pass --model.")
        args.model = args.model.resolve()
    configure_environment()
    os.chdir(repo)
    sys.path.insert(0, str(repo))
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    name = f"run_{stamp}_{RUN_TAG}" if args.mode == "train" else f"lead_brake_{args.mode}_{stamp}"
    output = repo / "results" / name
    output.mkdir(parents=True)
    if args.mode == "train":
        training(args, repo, output)
    else:
        evaluation(args, repo, output)


if __name__ == "__main__":
    main()
