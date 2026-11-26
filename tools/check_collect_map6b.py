"""(팀14) 수집 파일이 표준 조건으로 만들어졌는지 검사한다.

    python tools/check_collect_map6b.py data/map6b/s700000_n3.jsonl.gz

모든 항목이 OK면 마지막 줄에 PASS를 찍는다. 본 수집 전에 3판으로 먼저 돌려 볼 것.
"""
import gzip
import json
import sys
from collections import Counter

MODEL_SHA = "6ebdc4f6462497299d03b0197e3c9086dd3e20d9c7af31871a63abaa22d36b36"
ENV = {"TEAM14_SCENARIO": "museum", "TEAM14_ROUTE_OBS": "coarse", "TEAM14_NO_SPEED_CAP": "1",
       "TEAM14_OVERSPEED_W": "1.0", "TEAM14_IDLE_PEN": "0.3", "SIM_REUSE": "1"}
MAY_SET = {"TEAM14_ROUTE_NO_SHINHYUP": "0", "SUMO_USE_LIBSUMO": None}
REWARD = {"collision_penalty": 30.0, "arrival_bonus": 30.0, "blocked_penalty": 0.0, "idle_penalty": 0.3,
          "overspeed_weight": 1.0, "speed_weight": 0.1, "close_gap_threshold": 6.0, "close_gap_penalty": 0.1}
SHINHYUP_EDGE = "-40839116#4"      # 신협오거리를 지난 직후의 도로
EVAL_SEEDS = range(2026, 2326)     # 공식 평가 시드 (60판 x 5)

ok_all = True


def check(name, ok, detail=""):
    global ok_all
    ok_all &= bool(ok)
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def main(path):
    n = bad_sum = bad_obs = 0
    metas, blocked, seeds, reached, ends = [], Counter(), [], set(), Counter()
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            n += 1
            bad_obs += len(r["observation"]) != 37
            bad_sum += abs(sum(r["reward_terms"].values()) - r["reward"]) > 1e-6
            blocked[r["event"]["lane_change_blocked_code"]] += 1
            if r["state"].get("ego_road_id") == SHINHYUP_EDGE:
                reached.add(r["episode"])
            if "episode_meta" in r:
                metas.append(r["episode_meta"])
                seeds.append(r["episode_meta"]["seed"])
            if "episode_summary" in r:
                ends[r["episode_summary"]["end_reason_name"]] += 1
    m = metas[0]
    print(f"파일: {path}\n스텝 {n}, 판 {len(metas)}, 종료 사유 {dict(ends)}")
    check("모든 판의 수집 조건이 같음", all(
        (x["model_sha256"], x["sumo_version"], x["env_options"], x["reward_config"], x["code_commit"]) ==
        (m["model_sha256"], m["sumo_version"], m["env_options"], m["reward_config"], m["code_commit"])
        for x in metas))
    check("모델 파일 해시", m["model_sha256"] == MODEL_SHA, m["model_sha256"][:12])
    check("SUMO 1.28.0", "1.28.0" in str(m["sumo_version"]), str(m["sumo_version"]))
    env = m["env_options"]
    wrong = [f"{k}={env.get(k)!r}" for k, v in ENV.items() if str(env.get(k)) != v and
             not (env.get(k) is not None and _num(env.get(k)) == _num(v))]
    extra = [f"{k}={v!r}" for k, v in env.items() if v is not None and k not in ENV and
             not (k in MAY_SET and (MAY_SET[k] is None or v == MAY_SET[k]))]
    check("환경변수 표준값", not wrong, ", ".join(wrong))
    check("다른 환경변수 꺼짐 (보조 규칙, 중간 출발 등)", not extra, ", ".join(extra))
    rc = m["reward_config"]
    wrong = [f"{k}={rc.get(k)}" for k, v in REWARD.items() if rc.get(k) != v]
    check("보상 설정", not wrong, ", ".join(wrong))
    check("표준 조건 표시(standard_conditions)", m.get("standard_conditions") is True)
    check("결정적 행동, 신협 우회 아님", m["stochastic"] is False and m["detour_no_shinhyup"] is False)
    check("중간 출발(hard_start) 꺼짐", all(not x.get("hard_start") for x in metas))
    check("관측 37칸", bad_obs == 0)
    check("보상 항의 합 = reward", bad_sum == 0, f"불일치 {bad_sum}스텝")
    check("차선변경 막힘 코드 4(route)·5(reverse) 없음", blocked[4] == 0 and blocked[5] == 0,
          str(dict(sorted(blocked.items()))))
    check("신협오거리 통과한 판 있음", len(reached) > 0, f"{len(reached)}판")
    check("시드 중복 없음, 평가 시드와 안 겹침", len(set(seeds)) == len(seeds) and
          not any(s in EVAL_SEEDS for s in seeds), f"{min(seeds)}~{max(seeds)}")
    check("SUMO 시드 = 판 시드", all(x.get("sumo_seed") == x["seed"] for x in metas))
    print("PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
