"""Replay three SUMO seeds and trace estimated zipper merge times."""

from argparse import ArgumentParser
import csv
from datetime import datetime
from math import isfinite
import os
from pathlib import Path
import subprocess
import sys


SEEDS = (2344, 2336, 2380)
JUNCTION = "51066582#1.110"
TRACE_SCRIPT = Path("tools/trace_tof_junction_81.py")
MODEL = Path("results/run_20261122_143625_tof_ppo_tof_residual_40k/checkpoints/model_40960.pt")
PATCH_SETTING = "TEAM14_TOF_ZIPPER_CONFLICT_CONTINUITY"
FIELDS = (
    "step", "time_s", "ego_lane", "hazard_obs", "accel_cmd", "executed_accel_cmd",
    "outcome", "ego_speed_mps", "ego_distance_to_merge_m", "ego_connector_entry_eta_s",
    "ego_merge_eta_s", "ego_clear_eta_s", "other_id", "other_path", "other_same_approach",
    "other_speed_mps", "other_distance_to_merge_m", "other_connector_entry_eta_s",
    "other_merge_eta_s", "other_clear_eta_s", "gap_if_ego_first_s", "gap_if_other_first_s",
    "other_classified_conflict", "collision_partner",
)


def projected_times(position, length, speed, connector_entry, merge_line):
    """Signed constant-speed estimates relative to the current frame."""
    distance = merge_line - position - length / 2
    times = {"distance_to_merge_m": distance}
    if speed is not None and isfinite(speed) and speed > 0.1:
        times.update(
            connector_entry_eta_s=(connector_entry - position - length / 2) / speed,
            merge_eta_s=distance / speed,
            clear_eta_s=(distance + length) / speed,
        )
    return times


class MergePaths:
    def __init__(self, net, path_class):
        self.paths = {}
        self.by_lane = {}
        self.exit_lanes = set()
        for connection in net.getNode(JUNCTION).getConnections():
            via = connection.getViaLaneID()
            if connection.getState() != "Z" or not via:
                continue
            approach = connection.getFromLane()
            incoming = [c for c in approach.getIncomingConnections()
                        if not c.getFromLane().getID().startswith(":")]
            predecessor = min(incoming, key=lambda c: c.getDirection() != "s", default=None)
            shape = []
            if predecessor is not None:
                upstream = predecessor.getFromLane()
                shape.extend(upstream.getShape())
                self.by_lane[upstream.getID()] = via
                upstream_via = predecessor.getViaLaneID()
                if upstream_via:
                    shape.extend(net.getLane(upstream_via).getShape())
                    self.by_lane[upstream_via] = via
            shape.extend(approach.getShape())
            connector_entry = path_class(shape).length
            shape.extend(net.getLane(via).getShape())
            exit_lane = connection.getToLane()
            exit_shape = exit_lane.getShape()
            merge_line = path_class(shape + list(exit_shape[:1])).length
            path = path_class(shape + list(exit_shape))
            self.paths[via] = (path, connector_entry, merge_line, approach.getWidth() / 2)
            self.by_lane[approach.getID()] = via
            self.by_lane[via] = via
            self.exit_lanes.add(exit_lane.getID())
        if not self.paths:
            raise RuntimeError(f"No zipper connections found at {JUNCTION}.")

    def match_track(self, track, previous):
        matches = []
        for name, (path, _, merge_line, half_width) in self.paths.items():
            projection = path.project(track.center, track.direction)
            if projection is not None:
                position, error = projection
                if error <= half_width and -12 <= merge_line - position <= 120:
                    matches.append((round(error, 3), name != previous, name, position))
        if matches:
            _, _, name, position = min(matches)
            return name, position
        return None


class TraceEnvironment:
    def __init__(self, env, api_module, path_class):
        self.env = env
        self.api_module = api_module
        self.path_class = path_class
        self.geometry = None
        self.ego_path = None
        self.other_paths = {}
        self.samples = {}
        self.step_index = 0

    def __getattr__(self, name):
        return getattr(self.env, name)

    def step(self, action):
        self.sample_merge()
        self.step_index += 1
        return self.env.step(action)

    def sample_merge(self):
        api = self.api_module.traci
        ego = self.env.ego_id
        lane = api.vehicle.getLaneID(ego)
        if self.geometry is None:
            self.geometry = MergePaths(self.env._tof_geometry.net, self.path_class)
        if lane in self.geometry.by_lane:
            self.ego_path = self.geometry.by_lane[lane]
        elif lane not in self.geometry.exit_lanes or self.ego_path is None:
            return

        frame = self.env._tof_frame()
        path, connector_entry, merge_line, _ = self.geometry.paths[self.ego_path]
        projection = path.project(frame.center, frame.direction)
        if projection is None or not -12 <= merge_line - projection[0] <= 100:
            return
        speed = api.vehicle.getSpeed(ego)
        ego_times = projected_times(projection[0], self.env._tof_length, speed, connector_entry, merge_line)
        ego_fields = {"ego_speed_mps": speed, **{f"ego_{k}": v for k, v in ego_times.items()}}
        observations = []
        for track_id, track in frame.tracks.items():
            match = self.geometry.match_track(track, self.other_paths.get(track_id))
            if match is None:
                continue
            name, position = match
            self.other_paths[track_id] = name
            _, other_entry, other_merge, _ = self.geometry.paths[name]
            other_times = projected_times(position, track.length, track.speed, other_entry, other_merge)
            row = {
                **ego_fields,
                "other_id": track_id,
                "other_path": name,
                "other_same_approach": name == self.ego_path and position < other_entry,
                "other_speed_mps": track.speed,
                **{f"other_{k}": v for k, v in other_times.items()},
            }
            if "merge_eta_s" in ego_times and "merge_eta_s" in other_times:
                row["gap_if_ego_first_s"] = other_times["merge_eta_s"] - ego_times["clear_eta_s"]
                row["gap_if_other_first_s"] = ego_times["merge_eta_s"] - other_times["clear_eta_s"]
            observations.append(row)
        self.samples[self.step_index] = observations or [ego_fields]


def replay_mode(mode, output):
    sys.path.insert(0, str(Path.cwd()))
    from env.tof_observation import Path as LanePath
    from tools import trace_tof_junction_81 as trace

    replay = trace.replay
    with (output / f"{mode}_eta.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("mode", "seed", *FIELDS))
        writer.writeheader()

        def record_merge(env, policy, sumo_env, seed, expected_steps):
            observed = TraceEnvironment(env, sumo_env, LanePath)
            summary, rows = replay(observed, policy, sumo_env, seed, expected_steps)
            partners = {partner["vehicle_id"] for partner in summary["partners"]}
            for index, samples in observed.samples.items():
                recorded = rows[index]
                conflict_ids = set(recorded["conflict_ids"].split("|")) - {""}
                for sample in samples:
                    other_id = sample.get("other_id")
                    writer.writerow({
                        "mode": mode, "seed": seed, "step": index,
                        "time_s": recorded["time_s"], "ego_lane": recorded["lane_id"],
                        "hazard_obs": recorded["hazard_obs"], "accel_cmd": recorded["accel_cmd"],
                        "executed_accel_cmd": recorded["executed_accel_cmd"],
                        "outcome": summary["outcome"], **sample,
                        "other_classified_conflict": other_id in conflict_ids if other_id else None,
                        "collision_partner": other_id in partners if other_id else None,
                    })
            handle.flush()
            return summary, rows

        trace.replay = record_merge
        sys.argv = [str(TRACE_SCRIPT), "--model", str(MODEL), "--out", str(output / mode)]
        for seed in SEEDS:
            sys.argv.extend(("--seed", str(seed)))
        trace.main()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--worker", nargs=2, metavar=("MODE", "OUTPUT"), help="Run one replay mode.")
    args = parser.parse_args()
    if args.worker:
        mode, output = args.worker
        replay_mode(mode, Path(output))
        return

    repo = Path.cwd()
    if not (repo / TRACE_SCRIPT).is_file():
        repo = Path.home() / "sumo-tof-junction-reward"
    config = repo / "env" / "mdp_config.py"
    for file in (repo / TRACE_SCRIPT, repo / MODEL, config):
        if not file.is_file():
            sys.exit(f"Missing file: {file}")
    if PATCH_SETTING not in config.read_text(encoding="utf-8-sig"):
        sys.exit("Apply the zipper continuity patch before running this comparison.")

    output = repo / "results" / "eval300" / f"zipper_eta_{datetime.now():%Y%m%d_%H%M%S_%f}"
    output.mkdir(parents=True)
    environment = dict(os.environ, PYTHONUTF8="1", MERGE_COOP="0", MERGE_SPEEDMATCH="0",
                       ROUNDABOUT_VMAX="0", LC_TRACK_SUMO="0", EXEC_ACTION_BUFFER="0")
    script = str(Path(__file__).resolve())
    for mode, value in (("off", "0"), ("on", "1")):
        environment[PATCH_SETTING] = value
        print(f"\n=== Zipper continuity {mode.upper()} | seeds 2344, 2336, 2380 ===", flush=True)
        result = subprocess.run(
            [sys.executable, "-u", script, "--worker", mode, str(output)], cwd=repo, env=environment,
        )
        if result.returncode:
            sys.exit(result.returncode)
    print(f"\nETA files: {output}")


if __name__ == "__main__":
    main()
