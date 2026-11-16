"""대규모 주행 데이터 수집 (과제 요구: 주행 데이터 10^7 transition).

collect_pomdp_data.py와 같은 NPZ 형식(키 이름·dtype 동일)을, 에피소드 묶음(샤드) 단위
파일로 나눠 저장한다. 차이점:
  · 샤드 단위 저장 → 중간에 끊겨도 같은 명령을 다시 돌리면 다음 샤드부터 이어서 수집
  · 에피소드마다 시드를 고정(np.random → SUMO --seed) → 끊긴 샤드를 다시 돌려도 같은 데이터
  · --launch N: 워커 프로세스 N개를 같은 저장소 폴더에서 실행 (프로세스마다 다른 시드)
    (예전에는 build()가 env/sumo/highway.net.xml을 서로 덮어써서 폴더를 복사해야 했다.
     road_builder.build()를 고쳐서 이제 같은 폴더에서 동시에 돌려도 안전하다)
  · privileged state JSONL은 10^7 규모에선 수백 GB라 기본으로 끈다 (--jsonl로 켬)

환경변수(보조 규칙)는 부모 셸에서 설정하면 워커에 그대로 전달된다:
    SIM_REUSE=1 ROUTE_ASSIST_M=600 MERGE_SUMO=1 MERGE_STOP=1 LC_REVERSE_COOLDOWN=3
    TEAM14_SCENARIO=museum PYTHONIOENCODING=utf-8

사용 예:
    # 시험: 프로세스 1개, 3 에피소드
    python tools/collect_data.py --model results/run_20261112_141623_city_v4_routeendfix/model.pt \
        --out-dir D:/team14_data --worker-id 0 --max-episodes 3 --shard-episodes 3

    # 전체: 12 프로세스로 합계 10^7 스텝 (같은 명령을 다시 실행하면 이어서 수집)
    python tools/collect_data.py --model <절대경로 model.pt> --out-dir D:/team14_data \
        --launch 12 --total-steps 10000000

    # 진행 상황/통계 (stats.json 생성)
    python tools/collect_data.py --out-dir D:/team14_data --summarize

출력 (out-dir):
    shards/w03_s00012.npz   샤드 하나 (에피소드 --shard-episodes개)
    shards/w03_s00012.json  샤드 메타 (스텝 수, 에피소드별 결과, 시드, 환경변수)
    logs/w03.log            워커 로그 (--launch일 때)
    stats.json              --summarize 결과

읽기:
    import numpy as np, glob
    for p in sorted(glob.glob("shards/*.npz")):
        d = np.load(p)
        obs, act, rew, nxt = d["observation"], d["action_raw"], d["reward"], d["next_observation"]
        done = d["terminated"] | d["truncated"]
"""
import argparse
import glob
import gzip
import json
import math
import os
import subprocess
import sys
import time
from datetime import datetime

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ENV_KEYS = ["SIM_REUSE", "ROUTE_ASSIST_M", "MERGE_SUMO", "MERGE_STOP",
            "LC_REVERSE_COOLDOWN", "TEAM14_SCENARIO", "MERGE_SPEEDMATCH"]
EPISODE_STRIDE = 1_000_000   # 전역 에피소드 번호 = worker_id * STRIDE + 워커 내 번호


def episode_seed(base_seed: int, worker_id: int, ep: int) -> int:
    """(기본시드, 워커, 에피소드) → 32비트 시드. 재실행해도 같은 값."""
    return int(np.random.SeedSequence([base_seed, worker_id, ep]).generate_state(1)[0])


def shard_paths(out_dir, worker_id, shard):
    stem = os.path.join(out_dir, "shards", f"w{worker_id:02d}_s{shard:05d}")
    return stem + ".npz", stem + ".json"


def done_shards(out_dir, worker_id):
    """완성된 샤드(메타 json까지 써진 것)의 메타 목록. json은 npz 다음에 쓰므로 json이 있으면 완성."""
    metas = []
    for p in sorted(glob.glob(os.path.join(out_dir, "shards", f"w{worker_id:02d}_s*.json"))):
        with open(p, encoding="utf-8") as f:
            m = json.load(f)
        if os.path.exists(p[:-5] + ".npz"):
            metas.append(m)
    return metas


# ──────────────────────────────────────────────────────────────────
# 워커: 한 프로세스 = SUMO(libsumo) 하나
# ──────────────────────────────────────────────────────────────────
def run_worker(args):
    os.chdir(BASE)
    sys.path.insert(0, BASE)
    import torch
    torch.set_num_threads(1)   # 관측 1개씩 추론 → 1스레드면 충분, 병렬 워커끼리 코어를 뺏지 않게

    from env.road_config import ROAD, EGO, TRAFFIC
    from env.mdp_config import SIMULATION, OBSERVATION, ACTION
    from env import road_builder
    from env.sumo_env import SumoHighwayEnv
    from train import REWARD
    from test import load_agent

    os.makedirs(os.path.join(args.out_dir, "shards"), exist_ok=True)
    metas = done_shards(args.out_dir, args.worker_id)
    steps_done = sum(m["steps"] for m in metas)
    eps_done = sum(m["episodes"] for m in metas)
    next_shard = (max(m["shard"] for m in metas) + 1) if metas else 0
    print(f"[w{args.worker_id:02d}] 이어서 시작: 샤드 {len(metas)}개, 스텝 {steps_done:,}, "
          f"에피소드 {eps_done} (목표 스텝 {args.target_steps:,}, 최대 에피소드 {args.max_episodes})",
          flush=True)
    if steps_done >= args.target_steps or eps_done >= args.max_episodes:
        print(f"[w{args.worker_id:02d}] 이미 목표 달성", flush=True)
        return

    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    env = SumoHighwayEnv(cfg, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD,
                         traffic=TRAFFIC, gui=False)
    agent = load_agent(args.model, env.observation_space.shape[0], env.action_space.shape[0])
    deterministic = not args.stochastic
    env_vars = {k: os.environ.get(k) for k in ENV_KEYS}
    t_start = time.time()
    steps_this_run = 0

    try:
        shard = next_shard
        ep_local = eps_done   # 샤드 크기를 바꿔도 에피소드 번호가 이어지도록 누적 에피소드 수 사용
        while steps_done < args.target_steps and ep_local < args.max_episodes:
            n_eps = min(args.shard_episodes, args.max_episodes - ep_local)
            buf = {k: [] for k in ("observation", "next_observation", "action_raw", "lane_change",
                                   "lane_change_applied", "reward", "terminated", "truncated",
                                   "collided", "arrived", "lane_end", "speed", "gap",
                                   "episode", "t")}
            det_xy, det_off = [], [0]
            ep_meta = []
            jf = None
            npz_path, meta_path = shard_paths(args.out_dir, args.worker_id, shard)
            if args.jsonl:
                jf = gzip.open(npz_path[:-4] + ".jsonl.gz.tmp", "wt", encoding="utf-8",
                               compresslevel=6)
            t_shard = time.time()
            for k in range(n_eps):
                ep = ep_local + k
                gid = args.worker_id * EPISODE_STRIDE + ep
                seed = episode_seed(args.seed, args.worker_id, ep)
                np.random.seed(seed)     # sumo_env가 SUMO --seed·reuse 간격을 np.random에서 뽑는다
                torch.manual_seed(seed)  # --stochastic 샘플링 재현용
                obs, _ = env.reset(seed=seed)
                t, ret, done = 0, 0.0, False
                while not done:
                    detected = env.get_detected_vehicles() if not args.no_detected else ()
                    state_t = env.get_privileged_state() if jf else None
                    action = np.clip(agent.predict(obs, deterministic=deterministic),
                                     -1.0, 1.0).astype(np.float32)
                    nobs, r, term, trunc, info = env.step(action)
                    done = term or trunc
                    buf["observation"].append(np.asarray(obs, np.float32))
                    buf["next_observation"].append(np.asarray(nobs, np.float32))
                    buf["action_raw"].append(action)
                    buf["lane_change"].append(int(info["lane_change"]))
                    buf["lane_change_applied"].append(bool(info["lane_change_applied"]))
                    buf["reward"].append(float(r))
                    buf["terminated"].append(bool(term))
                    buf["truncated"].append(bool(trunc))
                    buf["collided"].append(bool(info.get("collided")))
                    buf["arrived"].append(bool(info.get("arrived")))
                    buf["lane_end"].append(bool(info.get("lane_end")))
                    buf["speed"].append(np.nan if info.get("speed") is None else float(info["speed"]))
                    buf["gap"].append(np.nan if info.get("gap") is None else float(info["gap"]))
                    buf["episode"].append(gid)
                    buf["t"].append(t)
                    det_xy.extend((d["x"], d["y"]) for d in detected)
                    det_off.append(len(det_xy))
                    if jf:
                        jf.write(json.dumps({"episode": gid, "t": t, "state": state_t,
                                             "lane_change_blocked": info.get("lane_change_blocked"),
                                             "route": info.get("route")},
                                            ensure_ascii=False, separators=(",", ":"),
                                            default=float) + "\n")
                    ret += r
                    t += 1
                    obs = nobs
                outcome = ("lane_end" if info.get("lane_end") else
                           "collision" if info.get("collided") else
                           "arrival" if info.get("arrived") else "timeout")
                ep_meta.append({"episode": gid, "seed": seed, "steps": t,
                                "return": round(ret, 4), "outcome": outcome,
                                "route": info.get("route")})
                print(f"[w{args.worker_id:02d}] ep {gid} steps={t:5d} return={ret:8.3f} {outcome}",
                      flush=True)

            n = len(buf["reward"])
            arrays = dict(
                observation=np.asarray(buf["observation"], np.float32).reshape(n, -1),
                action_raw=np.asarray(buf["action_raw"], np.float32).reshape(n, -1),
                lane_change=np.asarray(buf["lane_change"], np.int8),
                reward=np.asarray(buf["reward"], np.float32),
                next_observation=np.asarray(buf["next_observation"], np.float32).reshape(n, -1),
                terminated=np.asarray(buf["terminated"], np.bool_),
                truncated=np.asarray(buf["truncated"], np.bool_),
                episode=np.asarray(buf["episode"], np.int64),
                t=np.asarray(buf["t"], np.int32),
                # ↓ collect_pomdp_data.py에 없던 추가 항목 (info 일부)
                lane_change_applied=np.asarray(buf["lane_change_applied"], np.bool_),
                collided=np.asarray(buf["collided"], np.bool_),
                arrived=np.asarray(buf["arrived"], np.bool_),
                lane_end=np.asarray(buf["lane_end"], np.bool_),
                speed=np.asarray(buf["speed"], np.float32),
                gap=np.asarray(buf["gap"], np.float32),
            )
            if not args.no_detected:
                arrays["detected_xy"] = np.asarray(det_xy, np.float32).reshape(-1, 2)
                arrays["detected_offsets"] = np.asarray(det_off, np.int64)
            # 원자적 저장: tmp에 쓰고 rename → npz 완성 후 json → json이 있으면 완성된 샤드
            tmp = npz_path[:-4] + ".tmp.npz"
            np.savez_compressed(tmp, **arrays)
            os.replace(tmp, npz_path)
            if jf:
                jf.close()
                os.replace(npz_path[:-4] + ".jsonl.gz.tmp", npz_path[:-4] + ".jsonl.gz")
            dt = time.time() - t_shard
            meta = {"shard": shard, "worker_id": args.worker_id, "steps": n,
                    "episodes": n_eps, "first_episode_local": ep_local,
                    "seconds": round(dt, 2), "steps_per_sec": round(n / max(dt, 1e-9), 1),
                    "npz_bytes": os.path.getsize(npz_path),
                    "model": os.path.relpath(args.model, BASE) if args.model.startswith(BASE)
                    else os.path.basename(os.path.dirname(args.model)) + "/" + os.path.basename(args.model),
                    "stochastic": args.stochastic, "base_seed": args.seed,
                    "env": env_vars, "created": datetime.now().isoformat(timespec="seconds"),
                    "episodes_detail": ep_meta}
            with open(meta_path + ".tmp", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=1)
            os.replace(meta_path + ".tmp", meta_path)

            steps_done += n
            steps_this_run += n
            ep_local += n_eps
            shard += 1
            el = time.time() - t_start
            rate = steps_this_run / max(el, 1e-9)
            eta = (args.target_steps - steps_done) / max(rate, 1e-9)
            print(f"[w{args.worker_id:02d}] 샤드 {shard - 1} 저장 ({n:,} 스텝, "
                  f"{meta['npz_bytes'] / 2**20:.1f} MB, {meta['steps_per_sec']} step/s) | "
                  f"누적 {steps_done:,}/{args.target_steps:,} | 남은 시간 ≈ {eta / 3600:.1f} h",
                  flush=True)
    finally:
        env.close()


# ──────────────────────────────────────────────────────────────────
# 런처: 저장소 복사본 N개 + 워커 프로세스 N개
# ──────────────────────────────────────────────────────────────────
def launch(args):
    n = args.launch
    per = math.ceil(args.total_steps / n)
    os.makedirs(os.path.join(args.out_dir, "logs"), exist_ok=True)
    model = os.path.abspath(args.model)
    # 도로 파일을 부모에서 미리 만들어 둔다 (워커들은 build.stamp를 보고 건너뜀)
    sys.path.insert(0, BASE)
    os.chdir(BASE)
    from env.road_config import ROAD, EGO, TRAFFIC
    from env import road_builder
    road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    procs = []
    for w in range(args.worker_offset, args.worker_offset + n):
        cmd = [sys.executable, "-u", os.path.join(BASE, "tools", "collect_data.py"),
               "--model", model, "--out-dir", os.path.abspath(args.out_dir),
               "--worker-id", str(w), "--target-steps", str(per),
               "--shard-episodes", str(args.shard_episodes), "--seed", str(args.seed)]
        if args.stochastic:
            cmd.append("--stochastic")
        if args.no_detected:
            cmd.append("--no-detected")
        if args.jsonl:
            cmd.append("--jsonl")
        log = open(os.path.join(args.out_dir, "logs", f"w{w:02d}.log"), "a", encoding="utf-8")
        log.write(f"\n===== {datetime.now().isoformat(timespec='seconds')} 시작 =====\n")
        log.flush()
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        flags = 0
        if os.name == "nt" and args.low_priority:
            # 다른 작업을 덜 방해하지만, CPU가 꽉 찬 상태에선 거의 실행되지 않는다
            # (평가 15개가 돌 때 12분 동안 CPU 2초만 받음 — 시험에서 확인)
            flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS
        procs.append((w, subprocess.Popen(cmd, cwd=BASE, stdout=log, stderr=subprocess.STDOUT,
                                          env=env, creationflags=flags), log))
        print(f"워커 w{w:02d} 시작 (pid {procs[-1][1].pid}, 목표 {per:,} 스텝)")
    print(f"\n{n}개 워커 실행 중. 로그: {os.path.join(args.out_dir, 'logs')}\n"
          f"끊겨도 같은 명령을 다시 실행하면 이어서 수집합니다.")
    fails = 0
    for w, p, log in procs:
        rc = p.wait()
        log.close()
        if rc != 0:
            fails += 1
            print(f"워커 w{w:02d} 비정상 종료 (code {rc}) — 로그 확인 후 같은 명령으로 재실행")
    summarize(args)
    sys.exit(1 if fails else 0)


def summarize(args):
    metas = []
    for p in sorted(glob.glob(os.path.join(args.out_dir, "shards", "w*_s*.json"))):
        if os.path.exists(p[:-5] + ".npz"):
            with open(p, encoding="utf-8") as f:
                metas.append(json.load(f))
    eps = [e for m in metas for e in m["episodes_detail"]]
    steps = sum(m["steps"] for m in metas)
    size = sum(m["npz_bytes"] for m in metas)
    outc = {}
    for e in eps:
        outc[e["outcome"]] = outc.get(e["outcome"], 0) + 1
    ne = max(len(eps), 1)
    stats = {"transitions": steps, "episodes": len(eps), "shards": len(metas),
             "workers": sorted({m["worker_id"] for m in metas}),
             "npz_total_bytes": size,
             "bytes_per_transition": round(size / max(steps, 1), 1),
             "outcomes": outc,
             "collision_rate": outc.get("collision", 0) / ne,
             "arrival_rate": outc.get("arrival", 0) / ne,
             "lane_end_rate": outc.get("lane_end", 0) / ne,
             "mean_episode_steps": steps / ne,
             "mean_return": float(np.mean([e["return"] for e in eps])) if eps else None,
             "models": sorted({m["model"] for m in metas}),
             "env": metas[0]["env"] if metas else None}
    with open(os.path.join(args.out_dir, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="샤드 단위·재개 가능한 대규모 주행 데이터 수집")
    ap.add_argument("--model", help="PPO model.pt (train.py 출력)")
    ap.add_argument("--out-dir", required=True, help="출력 폴더 (모든 워커 공용, 절대경로 권장)")
    ap.add_argument("--worker-id", type=int, default=0)
    ap.add_argument("--target-steps", type=int, default=10**7, help="이 워커의 목표 스텝 수")
    ap.add_argument("--max-episodes", type=int, default=10**9, help="이 워커의 최대 에피소드 수 (시험용)")
    ap.add_argument("--shard-episodes", type=int, default=20, help="샤드 하나에 담을 에피소드 수")
    ap.add_argument("--seed", type=int, default=14)
    ap.add_argument("--stochastic", action="store_true", help="결정적 대신 분포에서 샘플링")
    ap.add_argument("--no-detected", action="store_true", help="감지 차량 좌표(detected_xy) 생략")
    ap.add_argument("--jsonl", action="store_true",
                    help="privileged state를 샤드별 .jsonl.gz로도 저장 (10^7 규모에선 매우 큼)")
    ap.add_argument("--launch", type=int, default=0, help="워커 N개를 각자 복사본 폴더에서 실행")
    ap.add_argument("--worker-offset", type=int, default=0,
                    help="--launch 워커 번호 시작값 (여러 컴퓨터에 나눠 돌릴 때 겹치지 않게)")
    ap.add_argument("--total-steps", type=int, default=10**7, help="--launch 전체 목표 스텝")
    ap.add_argument("--low-priority", action="store_true",
                    help="(Windows) 워커를 BELOW_NORMAL 우선순위로 실행. CPU가 한가할 때만 쓸 것")
    ap.add_argument("--summarize",action="store_true", help="수집된 샤드 통계만 출력/저장")
    args = ap.parse_args()
    args.out_dir = os.path.abspath(args.out_dir)

    if args.summarize:
        summarize(args)
        return
    if not args.model or not os.path.exists(args.model):
        ap.error(f"--model 파일이 없습니다: {args.model}")
    args.model = os.path.abspath(args.model)
    if args.launch:
        launch(args)
    else:
        run_worker(args)


if __name__ == "__main__":
    main()
