"""14조 최종 성능 평가: 여러 시드를 병렬로 돌리고 합계를 낸다.
사용: python tools/final_eval.py --seeds 106 107 108 109 110 --episodes 60
(보조 규칙 환경변수는 이 스크립트가 직접 켠다. 모델 기본값: results/sua_v9a/model_401408.pt)
"""
import argparse
import json
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAGS = {"PYTHONIOENCODING": "utf-8", "TEAM14_SCENARIO": "museum", "SIM_REUSE": "1",
         "ROUTE_ASSIST_M": "600", "MERGE_SUMO": "1", "MERGE_STOP": "1", "LC_REVERSE_COOLDOWN": "3",
         "RED_STOP": "1", "JUNCTION_YIELD": "3", "ZIPPER_FOLLOW": "1"}

ap = argparse.ArgumentParser()
ap.add_argument("--seeds", type=int, nargs="+", default=[106, 107, 108, 109, 110])
ap.add_argument("--episodes", type=int, default=60)
ap.add_argument("--model", default=os.path.join("results", "sua_v9a", "model_401408.pt"))
ap.add_argument("--out-dir", default=None)
ap.add_argument("--rules", choices=["all", "base"], default="all",
                help="all: 보조 규칙 전부 켬 / base: 보조 규칙 끔 (팀 원래 환경: 안전 게이트·경로 차선 보호만)")
args = ap.parse_args()
if args.rules == "base":
    FLAGS = {k: v for k, v in FLAGS.items() if k in ("PYTHONIOENCODING", "TEAM14_SCENARIO", "SIM_REUSE")}
if args.out_dir is None:
    args.out_dir = os.path.join("results", "final_eval" if args.rules == "all" else "final_eval_base")
os.chdir(BASE)
os.makedirs(args.out_dir, exist_ok=True)
env = dict(os.environ, **FLAGS)
procs = []
for sd in args.seeds:
    log = open(os.path.join(args.out_dir, f"seed{sd}.log"), "w", encoding="utf-8")
    cmd = [sys.executable, "-u", os.path.join("tools", "evaluate.py"), "--episodes", str(args.episodes),
           "--seed", str(sd), "--no-baseline", "--model", args.model,
           "--out", os.path.join(args.out_dir, f"seed{sd}.json")]
    procs.append((sd, subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env), log))
    print(f"시드 {sd} 평가 시작", flush=True)
tot = {"episodes": 0, "arrival": 0, "collision": 0, "lane_end": 0, "timeout": 0, "red_light": 0}
for sd, p, log in procs:
    p.wait()
    log.close()
    text = open(os.path.join(args.out_dir, f"seed{sd}.log"), encoding="utf-8").read()
    eps = [l.strip() for l in text.splitlines() if l.strip().startswith("ep ")]
    c = {"완주": 0, "충돌": 0, "경로이탈": 0, "시간초과": 0, "신호위반": 0}
    for l in eps:
        k = l.split()[-1]
        c[k] = c.get(k, 0) + 1
    print(f"시드 {sd}: {len(eps)}회, 완주 {c['완주']}, 충돌 {c['충돌']}, 신호위반 {c['신호위반']}, "
          f"경로이탈 {c['경로이탈']}, 시간초과 {c['시간초과']}", flush=True)
    tot["episodes"] += len(eps)
    tot["arrival"] += c["완주"]
    tot["collision"] += c["충돌"]
    tot["red_light"] += c["신호위반"]
    tot["lane_end"] += c["경로이탈"]
    tot["timeout"] += c["시간초과"]
n = max(tot["episodes"], 1)
summary = {**tot, "arrival_rate": tot["arrival"] / n, "collision_rate": tot["collision"] / n,
           "red_light_rate": tot["red_light"] / n, "seeds": args.seeds, "model": args.model, "rules": args.rules, "env": FLAGS}
json.dump(summary, open(os.path.join(args.out_dir, "summary.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n합계 {n}회: 완주 {summary['arrival_rate']:.1%}, 충돌 {summary['collision_rate']:.1%}, "
      f"신호위반 {summary['red_light_rate']:.1%}, 경로이탈 {tot['lane_end']}, 시간초과 {tot['timeout']}")
print(f"결과: {os.path.join(args.out_dir, 'summary.json')}")
