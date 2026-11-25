"""Fine-tune and replay the Team 14 PPO with the updated ToF observations."""

import argparse
import os
from pathlib import Path
import runpy
import sys


BUNDLED_INIT = Path(__file__).resolve().with_name("tof_600k_init_41.pt")
ROLLOUT = 2048
TAG = "tof_route_outcome_ft"
# In order: ego speed and neighbors, front density and signal range/color,
# then junction observations and rear densities.
COMMON_COLUMNS = ((slice(0, 21), slice(0, 21)),
                  (slice(26, 33), slice(27, 34)),
                  (slice(34, 39), slice(34, 39)))


def transfer_weights(source, target):
    import torch

    state = torch.load(source, map_location="cpu", weights_only=True)
    required = {"trunk.0.weight", "trunk.0.bias", "mu_head.weight", "lane_head.weight"}
    if (not isinstance(state, dict) or not required <= state.keys()
            or state["trunk.0.weight"].shape != (256, 39)
            or "accel_residual_junction_index" in state):
        raise ValueError("Expected the original 39-input plain ToF PPO checkpoint.")
    old = state["trunk.0.weight"]
    new = old.new_zeros((old.shape[0], 41))
    for before, after in COMMON_COLUMNS:
        new[:, after] = old[:, before]
    state["trunk.0.weight"] = new
    # At initialization, fold one identical neutral reference for all five
    # removed route scores into the bias. They have no input columns in the new policy.
    state["trunk.0.bias"] = state["trunk.0.bias"] + old[:, 21:26].sum(dim=1)
    # Use exclusive creation so a supplied path cannot overwrite a checkpoint.
    with target.open("xb") as file:
        torch.save(state, file)
    print(f"Initial weights saved: {target} (33 transferred inputs, 8 zero-initialized inputs)")


MUST_YIELD_COLUMN = 35   # 41칸 관측에서 양보 의무 칸 위치


def drop_must_yield_weights(source, target):
    """41칸 모델의 첫 층에서 양보 의무 칸(35번) 열만 지워 40칸 모델로 만든다. 나머지 가중치는 그대로."""
    import torch

    state = torch.load(source, map_location="cpu", weights_only=True)
    old = state["trunk.0.weight"]
    if old.shape[1] != 41:
        raise ValueError(f"Expected a 41-input checkpoint, got {old.shape[1]} inputs: {source}")
    keep = [i for i in range(old.shape[1]) if i != MUST_YIELD_COLUMN]
    state["trunk.0.weight"] = old[:, keep].clone()
    torch.save(state, target)
    print(f"40칸 초기 모델 저장: {target} (41칸 모델에서 양보 의무 칸만 제거)", flush=True)


def checkpoint_inputs(path):
    import torch

    return torch.load(path, map_location="cpu", weights_only=True)["trunk.0.weight"].shape[1]


def configure(training, hard_start_prob=0.0):
    for key in (
        "ASSIST_PROB", "ROUTE_ASSIST_M", "ROUTE_SHIELD_M", "MERGE_SUMO",
        "MERGE_STOP", "MERGE_SPEEDMATCH", "MERGE_COOP", "LC_REVERSE_COOLDOWN",
        "LC_COOLDOWN_EXEMPT", "LC_TRACK_SUMO", "RED_STOP", "JUNCTION_YIELD",
        "JUNCTION_ROW", "ZIPPER_FOLLOW", "ROUNDABOUT_VMAX", "STOP_SHAPING",
        "STOP_SHAPING_YELLOW", "EXEC_ACTION_BUFFER", "TEAM14_JUN_INSIDE",
        "TEAM14_OVERSPEED_W", "TEAM14_TOF_LEAD_HOLD_S", "TEAM14_TOF_LEAD_GAP_WINDOW",
    ):
        os.environ.pop(key, None)
    os.environ.update(
        TEAM14_SCENARIO="museum", TEAM14_TOF_OBS="1", TEAM14_TOF_REAR_DENSITY="1",
        TEAM14_ROUTE_OBS="none", TEAM14_ROUTE_FORK_OBS="1", TEAM14_LANE_END_OBS="1",
        TEAM14_LANE_END_RANGE="50", TEAM14_DROP_SIGNAL_TIME="1", TEAM14_NO_SPEED_CAP="1",
        TEAM14_REWARD="progress", PROGRESS_TOTAL="150", PROGRESS_OVERSPEED_W=os.environ.get("PROGRESS_OVERSPEED_W_OVERRIDE", "1.0"),
        PROGRESS_YIELD_PENALTY="2", PROGRESS_TIME_PENALTY="0",
        PROGRESS_SPEED_W=os.environ.get("PROGRESS_SPEED_W_OVERRIDE", "0"),
        PROGRESS_SPEED_OFFSET=os.environ.get("PROGRESS_SPEED_OFFSET_OVERRIDE", "0"),
        HARD_START_PROB=str(hard_start_prob if training else 0.0),
        HARD_START_TARGETS=os.environ.get("HARD_START_TARGETS_OVERRIDE", "568664967#4,51066582#1,1307152438"),
        HARD_START_BACK_M=os.environ.get("HARD_START_BACK_M_OVERRIDE", "100"),
        TEAM14_FORK_RELATIVE=os.environ.get("FORK_RELATIVE_OVERRIDE", "0"), TEAM14_FORK_NEAR_DEG="30",
        PROGRESS_GAP_PENALTY=os.environ.get("PROGRESS_GAP_PENALTY_OVERRIDE", "0"),
        PROGRESS_GAP_BASE="2", PROGRESS_GAP_HEADWAY="1",
        PROGRESS_GAP_RSS_DECEL=os.environ.get("GAP_RSS_DECEL_OVERRIDE", "0"),
        TEAM14_DROP_MUST_YIELD=os.environ.get("DROP_MUST_YIELD_OVERRIDE", "0"),
        SIM_REUSE="5" if training else "1",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    prepare = commands.add_parser("prepare", help="Recreate the initial checkpoint.")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("output", type=Path)
    train = commands.add_parser("train")
    train.add_argument("--steps", type=int, default=102400)
    train.add_argument("--seed", type=int, default=0)
    train.add_argument("--init-model", type=Path, default=BUNDLED_INIT)
    train.add_argument("--hard-start-prob", type=float, default=0.5)
    for mode, episodes in (("evaluate", 20), ("gui", 5)):
        replay = commands.add_parser(mode)
        replay.add_argument("--model", type=Path)
        replay.add_argument("--episodes", type=int, default=episodes)
        replay.add_argument("--seed", type=int, default=2326)
    args = parser.parse_args()

    if args.mode == "prepare":
        transfer_weights(args.source, args.output)
        return

    root = Path.cwd()
    env_source = root / "env" / "sumo_env.py"
    if not env_source.is_file() or "TEAM14_ROUTE_FORK_OBS" not in env_source.read_text(encoding="utf-8"):
        parser.error("Run from sumo-tof-progress-clean after applying tof_route_outcome_ft.patch.")
    if not 0 <= args.seed < 2**32:
        parser.error("--seed must be in range.")

    training = args.mode == "train"
    if training:
        if args.steps <= 0 or args.steps % ROLLOUT:
            parser.error(f"--steps must be a positive multiple of {ROLLOUT}.")
        if not 0.0 <= args.hard_start_prob <= 1.0:
            parser.error("--hard-start-prob must be between 0 and 1.")
        model = args.init_model.resolve()
    else:
        if not 1 <= args.episodes <= 2**32 - args.seed:
            parser.error("--episodes must be positive and must fit the seed range.")
        model = args.model or max(
            root.glob(f"results/run_*_{TAG}_s*/model.pt"), default=None
        )
        if model is None:
            parser.error("Train first or pass --model.")
        model = model.resolve()
    if not model.is_file():
        parser.error(f"Checkpoint not found: {model}")

    configure(training, args.hard_start_prob if training else 0.0)
    sys.path.insert(0, str(root))
    n_inputs = 40 if os.environ["TEAM14_DROP_MUST_YIELD"] == "1" else 41
    if training and n_inputs == 40 and checkpoint_inputs(model) == 41:
        converted = model.with_name(f"{model.stem}_obs40.pt")
        if not converted.exists():
            drop_must_yield_weights(model, converted)
        model = converted
    print(f"ToF PPO | {n_inputs} inputs | progress 150 | arrival +10 | failure -{os.environ.get('COLLISION_PENALTY_OVERRIDE', '10')} | yield entry -2 | overspeed {os.environ['PROGRESS_OVERSPEED_W']} | speed {os.environ['PROGRESS_SPEED_W']} - {os.environ['PROGRESS_SPEED_OFFSET']} | gap -{os.environ['PROGRESS_GAP_PENALTY']} if < 2 m + 1 s (+RSS b={os.environ['PROGRESS_GAP_RSS_DECEL']}) | fork relative {os.environ['TEAM14_FORK_RELATIVE']} | hard start back {os.environ['HARD_START_BACK_M']} m",
          flush=True)
    if training:
        print(f"Training hard-start probability: {args.hard_start_prob:g}", flush=True)
        script = root / "train.py"
        options = [
            "--seed", str(args.seed), "--gamma", "0.995",
            "--collision-penalty", os.environ.get("COLLISION_PENALTY_OVERRIDE", "10"),
            "--arrival-bonus", "10", "--blocked-penalty", "0",
            "--timesteps", str(args.steps), "--ckpt-every", str(min(51200, args.steps)),
            "--init-model", str(model), "--tag", f"{TAG}_s{args.seed}",
        ]
    else:
        from train import REWARD
        REWARD.update(collision_penalty=10.0, arrival_bonus=10.0, blocked_penalty=0.0)
        if args.mode == "gui":
            import numpy as np
            np.random.seed(args.seed)
            script = root / "test.py"
            options = [str(model), "--episodes", str(args.episodes), "--algorithm", "ppo"]
        else:
            script = root / "tools" / "evaluate.py"
            report = model.with_name(f"{model.stem}_eval{args.episodes}_seed{args.seed}.json")
            options = [
                "--model", str(model), "--episodes", str(args.episodes), "--seed", str(args.seed),
                "--independent-seeds", "--no-baseline", "--out", str(report),
            ]
    sys.argv = [str(script), *options]
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
