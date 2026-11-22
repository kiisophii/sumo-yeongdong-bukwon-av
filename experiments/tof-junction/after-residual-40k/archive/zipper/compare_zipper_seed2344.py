"""Replay seed 2344 with the existing zipper patch off and on."""

from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys


SEED = 2344
TRACE_SCRIPT = Path("tools/trace_tof_junction_81.py")
MODEL = Path("results/run_20261122_143625_tof_ppo_tof_residual_40k/checkpoints/model_40960.pt")
PATCH_SETTING = "TEAM14_TOF_ZIPPER_CONFLICT_CONTINUITY"


def main():
    repo = Path.cwd()
    if not (repo / TRACE_SCRIPT).is_file():
        repo = Path.home() / "sumo-tof-junction-reward"
    for relative in (TRACE_SCRIPT, MODEL, Path("env/mdp_config.py")):
        if not (repo / relative).is_file():
            sys.exit(f"Missing file: {repo / relative}")
    if PATCH_SETTING not in (repo / "env/mdp_config.py").read_text(encoding="utf-8"):
        sys.exit("Apply the zipper continuity patch before running this comparison.")

    output = repo / "results" / "eval300" / f"zipper_seed{SEED}_{datetime.now():%Y%m%d_%H%M%S_%f}"
    environment = dict(
        os.environ,
        PYTHONUTF8="1",
        MERGE_COOP="0",
        MERGE_SPEEDMATCH="0",
        ROUNDABOUT_VMAX="0",
        LC_TRACK_SUMO="0",
        EXEC_ACTION_BUFFER="0",
    )
    for mode, value in (("off", "0"), ("on", "1")):
        print(f"\n=== Seed {SEED} | zipper continuity {mode.upper()} ===", flush=True)
        environment[PATCH_SETTING] = value
        result = subprocess.run(
            [sys.executable, "-u", str(TRACE_SCRIPT), "--model", str(MODEL),
             "--seed", str(SEED), "--out", str(output / mode)],
            cwd=repo, env=environment,
        )
        if result.returncode:
            sys.exit(result.returncode)
    print(f"\nReplay files: {output}")


if __name__ == "__main__":
    main()
