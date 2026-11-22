"""Apply the experimental zipper ETA patch and replay three merge cases."""

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys


SEEDS = (2344, 2336, 2380)
TRACE = Path("tools/trace_tof_junction_81.py")
MODEL = Path("results/run_20261122_143625_tof_ppo_tof_residual_40k/checkpoints/model_40960.pt")
SETTING = "TEAM14_TOF_ZIPPER_ETA_GATE"


def apply_patch(repo, patch):
    command = ["git", "apply"]
    applied = subprocess.run(
        [*command, "--reverse", "--check", str(patch)],
        cwd=repo, capture_output=True,
    )
    if applied.returncode == 0:
        return
    subprocess.run([*command, "--check", str(patch)], cwd=repo, check=True)
    subprocess.run([*command, str(patch)], cwd=repo, check=True)


def main():
    repo = Path.cwd()
    if not (repo / TRACE).is_file():
        repo = Path.home() / "sumo-tof-junction-reward"
    config = repo / "env" / "mdp_config.py"
    patch = Path(__file__).resolve().with_name("tof_zipper_eta_gate.patch")
    for file in (repo / TRACE, repo / MODEL, config, patch):
        if not file.is_file():
            sys.exit(f"Missing file: {file}")
    if "TEAM14_TOF_ZIPPER_CONFLICT_CONTINUITY" not in config.read_text(encoding="utf-8-sig"):
        sys.exit("Apply the previous zipper continuity patch first.")
    try:
        apply_patch(repo, patch)
    except (OSError, subprocess.CalledProcessError) as error:
        sys.exit(f"Could not apply the ETA patch: {error}")

    output = repo / "results" / "eval300" / f"zipper_eta_gate_{datetime.now():%Y%m%d_%H%M%S_%f}"
    output.mkdir(parents=True)
    env = dict(
        os.environ, PYTHONUTF8="1", TEAM14_TOF_ZIPPER_CONFLICT_CONTINUITY="1",
        MERGE_COOP="0", MERGE_SPEEDMATCH="0", ROUNDABOUT_VMAX="0", LC_TRACK_SUMO="0",
        EXEC_ACTION_BUFFER="0",
    )
    for label, setting in (("continuity", "0"), ("eta_gate", "1")):
        env[SETTING] = setting
        print(f"\n=== {label} | seeds 2344, 2336, 2380 ===", flush=True)
        args = [sys.executable, "-u", str(TRACE), "--model", str(MODEL), "--out", str(output / label)]
        for seed in SEEDS:
            args.extend(("--seed", str(seed)))
        result = subprocess.run(args, cwd=repo, env=env)
        if result.returncode:
            sys.exit(result.returncode)
    print(f"\nReplay files: {output}")


if __name__ == "__main__":
    main()
