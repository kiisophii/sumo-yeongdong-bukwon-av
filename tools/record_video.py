"""제출용 주행 영상(30초 mp4) 만들기 — sumo-gui 화면을 스텝마다 캡처해서 편집한다.

세 단계로 나뉜다 (기록은 무겁고, 편집은 가벼워서 몇 번이고 다시 할 수 있다).

  1) check  : 화면 없이(libsumo) 같은 시드로 미리 돌려 "완주하는 시드"를 찾는다.
  2) record : sumo-gui로 같은 시드를 돌리며 ego를 따라가는 화면을 스텝마다 PNG로 저장,
              스텝별 위치·속도·구간을 frames.csv에 기록한다.
  3) edit   : frames.csv를 보고 핵심 구간(회전교차로·영업소 뒤 합류·부곡 합류·동수원 출구)은
              천천히, 나머지는 빠르게 넘겨 정확히 N초짜리 mp4를 만든다. 자막(속도·구간·배속) 포함.

환경변수 (보조 규칙, sua-assist 브랜치):
  SIM_REUSE=1 ROUTE_ASSIST_M=600 MERGE_SUMO=1 MERGE_STOP=1 LC_REVERSE_COOLDOWN=3
  TEAM14_SCENARIO=museum PYTHONIOENCODING=utf-8

사용 예 (저장소 폴더에서):
  python tools/record_video.py check  --seed 2026 --tries 5
  python tools/record_video.py record --seed 2026 --out video_out/full
  python tools/record_video.py record --seed 2026 --out video_out/test --max-steps 300   # 짧은 시험
  python tools/record_video.py edit   --src video_out/full --seconds 30 --mp4 video_out/team14_drive_30s.mp4

ffmpeg: PATH의 ffmpeg 또는 pip 패키지 imageio-ffmpeg에 들어 있는 ffmpeg를 쓴다.
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

DEFAULT_MODEL = "results/run_20261112_141623_city_v4_routeendfix/model.pt"
REQUIRED_ENV = {"SIM_REUSE": "1", "ROUTE_ASSIST_M": "600", "MERGE_SUMO": "1",
                "MERGE_STOP": "1", "LC_REVERSE_COOLDOWN": "3",
                "TEAM14_SCENARIO": "museum", "PYTHONIOENCODING": "utf-8"}

# ── 핵심 구간 (경로 순서). edge id가 정확히 같거나, prefix로 시작하면 그 구간 ──
#   id는 env/museum/route_check.json + env/patches_museum/tolls_bd_1.edg.xml 기준
KEY_ZONES = [
    ("roundabout", "의왕역 회전교차로",
     {"496583281#0", "496583281#1", "568664967#4", "568664967#0", "488779086#0",
      "452597718#0"},                     # 452597718#0 = 파랑 경로(부곡중앙로) 첫 구간
     (":4582364294", ":4582364295")),
    ("toll_merge", "부곡 영업소 뒤 지퍼 합류 (3→1차로)",
     {"51066582#1", "51066582#1.95", "51066582#1.110"},
     (":51066582#1",)),
    ("bugok_merge", "부곡IC 합류 → 영동고속도로",
     {"468211809#2", "474882669#1-AddedOnRampEdge"},
     (":474882669#1-AddedOnRamp",)),
    ("dongsuwon_exit", "동수원IC 출구 · 영업소",
     {"206488704", "377057231", "50981102", "1250775757", "1224608702",
      "1224608702.60", "1224608702.75"},
     (":1224608702",)),
]
ZONE_LABEL = {k: lab for k, lab, _, _ in KEY_ZONES}
# 구간별 슬로모션 정도 (스텝당 출력 프레임 수 배율). 회전교차로는 4초 남짓이라 더 느리게
ZONE_WEIGHT = {"roundabout": 2.0, "toll_merge": 1.0, "bugok_merge": 1.0, "dongsuwon_exit": 1.0}

# 화면 확대 배율(%) — 도심 구간은 가까이, 고속도로는 조금 멀리
ZOOM_CITY, ZOOM_HIGHWAY = 4500.0, 2600.0
EGO_COLOR = (255, 20, 20, 255)      # 배경차(노랑·시안·주황·마젠타·연보라·흰색)와 겹치지 않는 빨강
EGO_RING = (0, 255, 90, 255)        # ego 주변 형광 초록 링 (traci.vehicle.highlight)


def zone_of(edge):
    if not edge:
        return ""
    for key, _, ids, prefixes in KEY_ZONES:
        if edge in ids or any(edge.startswith(p) for p in prefixes):
            return key
    return ""


def check_env():
    missing = {k: v for k, v in REQUIRED_ENV.items() if os.environ.get(k) != v}
    if missing:
        print("※ 환경변수가 지시값과 다릅니다(그대로 진행):",
              ", ".join(f"{k}={os.environ.get(k)!r} (기대 {v})" for k, v in missing.items()))


def make_env(gui):
    from env.road_config import ROAD, EGO, TRAFFIC
    from env.mdp_config import SIMULATION, OBSERVATION, ACTION
    from env import road_builder
    import env.sumo_env as se
    from train import REWARD
    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    sim = dict(SIMULATION, gui_delay=0.0, gui_zoom=ZOOM_CITY, gui_track_ego=True)
    env = se.SumoHighwayEnv(cfg, ROAD, EGO, sim, OBSERVATION, ACTION, REWARD,
                            traffic=TRAFFIC, gui=gui, gui_autostart=gui)
    return env, se


def load_policy(env, model):
    from test import load_agent
    path = model if os.path.isabs(model) else os.path.join(BASE, model)
    return load_agent(path, env.observation_space.shape[0], env.action_space.shape[0])


def outcome(info):
    if info.get("lane_end"):
        return "lane_end"
    if info.get("collided"):
        return "collision"
    if info.get("arrived"):
        return "arrival"
    return "timeout"


# ══════════════════════════════════════════════════════════════════
# 1) check — 화면 없이 시드별 결과 확인
# ══════════════════════════════════════════════════════════════════
def cmd_check(a):
    check_env()
    env, se = make_env(gui=False)
    pol = load_policy(env, a.model)
    try:
        for s in range(a.seed, a.seed + a.tries):
            np.random.seed(s)
            env.close()
            obs, _ = env.reset()
            n, t0 = 0, time.time()
            while True:
                obs, r, term, trunc, info = env.step(pol.predict(obs, deterministic=True))
                n += 1
                if term or trunc or (a.max_steps and n >= a.max_steps):
                    break
            print(f"seed {s}: {outcome(info)}, {n} 스텝 ({n * env.step_length / 60:.1f}분), "
                  f"계산 {time.time() - t0:.0f}초", flush=True)
            if outcome(info) == "arrival" and a.stop_at_first:
                break
    finally:
        env.close()


# ══════════════════════════════════════════════════════════════════
# 2) record — sumo-gui 캡처
# ══════════════════════════════════════════════════════════════════
def cmd_record(a):
    check_env()
    out = os.path.abspath(a.out)
    fdir = os.path.join(out, "frames")
    os.makedirs(fdir, exist_ok=True)
    env, se = make_env(gui=True)
    pol = load_policy(env, a.model)
    rows, info, n = [], {}, 0
    T = None
    try:
        np.random.seed(a.seed)
        env.close()
        obs, _ = env.reset()
        T = se.traci
        view = T.gui.getIDList()[0]
        ego = env.ego_id
        T.vehicle.setColor(ego, EGO_COLOR)
        try:
            T.vehicle.highlight(ego, EGO_RING, size=-1, alphaMax=200, duration=1e7, type=0)
        except Exception as e:  # noqa: BLE001  (구버전 SUMO면 링 없이)
            print("highlight 실패:", e)
        T.gui.trackVehicle(view, ego)
        zoom = ZOOM_CITY
        T.gui.setZoom(view, zoom)
        names = {}
        t0 = time.time()
        last_edge = ""
        while True:
            obs, r, term, trunc, info = env.step(pol.predict(obs, deterministic=True))
            n += 1
            alive = ego in T.vehicle.getIDList()
            if alive:
                edge = T.vehicle.getRoadID(ego)
                if not edge.startswith(":"):
                    last_edge = edge
                if edge not in names:
                    try:
                        names[edge] = T.edge.getStreetName(edge) if not edge.startswith(":") else ""
                    except Exception:  # noqa: BLE001
                        names[edge] = ""
                hw = last_edge and (T.lane.getMaxSpeed(T.vehicle.getLaneID(ego)) > 22.3
                                    or "AddedOnRamp" in last_edge)
                want = ZOOM_HIGHWAY if hw else ZOOM_CITY
                if want != zoom:
                    zoom = want
                    T.gui.trackVehicle(view, ego)
                    T.gui.setZoom(view, zoom)
                x, y = T.vehicle.getPosition(ego)
                lane = T.vehicle.getLaneIndex(ego)
            else:
                edge, x, y, lane = "", float("nan"), float("nan"), -1
            fname = f"f{n:05d}.png"
            if alive or n == 1:
                # 캡처는 다음 화면 갱신(=다음 simulationStep) 때 파일로 써진다
                T.gui.screenshot(view, os.path.join(fdir, fname), a.width, a.height)
            rows.append({"step": n, "t": round(n * env.step_length, 1), "frame": fname if alive else "",
                         "edge": edge, "zone": zone_of(edge or last_edge),
                         "street": names.get(edge, "") or names.get(last_edge, ""),
                         "lane": lane, "speed": round(float(info.get("speed") or 0), 3),
                         "x": round(x, 1), "y": round(y, 1), "zoom": zoom})
            if n % 100 == 0:
                print(f"  {n} 스텝, 계산 {time.time() - t0:.0f}초, {edge}", flush=True)
            if term or trunc or (a.max_steps and n >= a.max_steps):
                break
        # 마지막 캡처가 써지도록 한 스텝 더
        try:
            T.simulationStep()
        except Exception:  # noqa: BLE001
            pass
    finally:
        env.close()
    res = outcome(info) if not (a.max_steps and n >= a.max_steps) else "max_steps"
    with open(os.path.join(out, "frames.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    meta = {"seed": a.seed, "model": a.model, "steps": n, "outcome": res,
            "step_length": 0.5, "width": a.width, "height": a.height,
            "env": {k: os.environ.get(k) for k in REQUIRED_ENV}}
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"기록 끝: {res}, {n} 스텝 → {out}")


# ══════════════════════════════════════════════════════════════════
# 3) edit — 30초로 압축 + 자막 + mp4
# ══════════════════════════════════════════════════════════════════
def ffmpeg_exe():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001
        sys.exit("ffmpeg가 없습니다. `pip install imageio-ffmpeg` 또는 https://www.gyan.dev/ffmpeg/builds/ "
                 "에서 받아 PATH에 추가하세요.")


def plan_frames(rows, n_out, key_w, smooth, pad=6):
    """스텝별 '출력 프레임 가중치'를 정해(핵심 구간 key_w, 나머지 b) 누적합으로 프레임을 고른다.
    b는 총 프레임 수가 n_out이 되도록 이분법으로 찾고, 경계는 이동평균으로 부드럽게 바꾼다."""
    zw = np.array([ZONE_WEIGHT.get(r["zone"], 1.0) if r["zone"] else 0.0 for r in rows])
    # 구간 앞뒤 pad 스텝(기본 3초)도 같이 느리게 — 다가가는 장면부터 보이도록
    zw = np.array([zw[max(0, i - pad):i + pad + 1].max() for i in range(len(zw))])
    key = (zw > 0).astype(float)
    ker = np.ones(smooth) / smooth if smooth > 1 else np.ones(1)
    keys = np.convolve(key, ker, mode="same")

    def weights(b):
        return np.convolve(zw, ker, mode="same") * key_w + (1 - keys) * b

    if weights(0.0).sum() > n_out * 0.7:          # 핵심 구간만으로 넘치면 줄인다
        key_w *= n_out * 0.7 / weights(0.0).sum()
    lo, hi = 0.0, key_w
    for _ in range(60):
        mid = (lo + hi) / 2
        if weights(mid).sum() < n_out:
            lo = mid
        else:
            hi = mid
    w = weights(lo)
    w *= n_out / w.sum()
    cum = np.cumsum(w)
    idx = np.searchsorted(cum, np.arange(n_out) + 0.5)
    idx = np.clip(idx, 0, len(rows) - 1)
    return idx, w


def load_font(size, bold=False):
    from PIL import ImageFont
    for f in (["malgunbd.ttf"] if bold else []) + ["malgun.ttf", "NanumGothic.ttf", "AppleGothic.ttf"]:
        for d in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/nanum", "/Library/Fonts"):
            p = os.path.join(d, f)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def cmd_edit(a):
    from PIL import Image, ImageDraw
    src = os.path.abspath(a.src)
    meta = json.load(open(os.path.join(src, "meta.json"), encoding="utf-8"))
    with open(os.path.join(src, "frames.csv"), encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["frame"]
                and os.path.exists(os.path.join(src, "frames", r["frame"]))]
    if not rows:
        sys.exit("프레임이 없습니다.")
    fps = a.fps
    n_hold = int(round(a.end_hold * fps))
    n_out = int(round(a.seconds * fps)) - n_hold
    idx, w = plan_frames(rows, n_out, a.key_weight, a.smooth, a.pad)
    W, H = a.width, a.height
    f_big, f_mid, f_small = load_font(int(H * 0.05), True), load_font(int(H * 0.034), True), load_font(int(H * 0.026))
    step_len = float(meta.get("step_length", 0.5))
    total_t = float(rows[-1]["t"])
    arrived = meta.get("outcome") == "arrival"

    mp4 = os.path.abspath(a.mp4)
    os.makedirs(os.path.dirname(mp4), exist_ok=True)
    proc = subprocess.Popen(
        [ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "medium",
         "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", mp4],
        stdin=subprocess.PIPE)

    def panel(d, xy, text, font, pad=10, fill=(255, 255, 255), bg=(0, 0, 0, 160)):
        x, y = xy
        bb = d.textbbox((x, y), text, font=font)
        d.rounded_rectangle((bb[0] - pad, bb[1] - pad, bb[2] + pad, bb[3] + pad), radius=8, fill=bg)
        d.text((x, y), text, font=font, fill=fill)
        return bb

    cache = {}
    last_img = None
    for k, i in enumerate(idx):
        r = rows[i]
        if i not in cache:
            cache.clear()
            im = Image.open(os.path.join(src, "frames", r["frame"])).convert("RGB")
            if im.size != (W, H):
                im = im.resize((W, H), Image.LANCZOS)
            cache[i] = im
        img = cache[i].copy().convert("RGBA")
        ov = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        speedup = step_len * fps / w[i] if w[i] > 0 else 0   # 시뮬레이션 초 / 영상 초
        kmh = float(r["speed"]) * 3.6
        m = int(H * 0.035)
        # 왼쪽 위: 속도 / 오른쪽 위: 시뮬레이션 시각·배속
        panel(d, (m, m), f"{kmh:5.1f} km/h", f_big)
        tt = float(r["t"])
        txt = f"주행 {int(tt // 60)}:{int(tt % 60):02d}   {speedup:.0f}배속"
        bb = d.textbbox((0, 0), txt, font=f_mid)
        panel(d, (W - m - (bb[2] - bb[0]), m + 6), txt, f_mid)
        # 아래: 구간 이름 (핵심 구간이면 강조색)
        zone = r["zone"]
        label = ZONE_LABEL.get(zone) or r["street"] or "도심 도로"
        if zone:
            label = "▶ " + label
        bb = d.textbbox((0, 0), label, font=f_mid)
        panel(d, ((W - (bb[2] - bb[0])) // 2, H - m - (bb[3] - bb[1]) - 8), label, f_mid,
              fill=(255, 235, 60) if zone else (255, 255, 255))
        # 첫 2초: 제목
        if k < fps * 2:
            title = "PPO 자율주행차 · 철도박물관 → 수원광교박물관 (14.4 km)"
            sub = "빨간 차(초록 링) = 학습한 ego · ICE3052 팀14 · SUMO 1.27.1"
            bb = d.textbbox((0, 0), title, font=f_mid)
            panel(d, ((W - (bb[2] - bb[0])) // 2, int(H * 0.16)), title, f_mid)
            bb = d.textbbox((0, 0), sub, font=f_small)
            panel(d, ((W - (bb[2] - bb[0])) // 2, int(H * 0.16) + int(H * 0.07)), sub, f_small)
        # 진행 막대
        prog = tt / max(total_t, 1)
        d.rectangle((0, H - 6, W, H), fill=(0, 0, 0, 140))
        d.rectangle((0, H - 6, int(W * prog), H), fill=(255, 40, 40, 255))
        out = Image.alpha_composite(img, ov).convert("RGB")
        proc.stdin.write(out.tobytes())
        last_img = cache[i]
    # 끝: 마지막 장면에 결과 카드
    for _ in range(n_hold):
        img = last_img.copy().convert("RGBA")
        ov = Image.new("RGBA", img.size, (0, 0, 0, 110))
        d = ImageDraw.Draw(ov)
        res = "완주" if arrived else {"collision": "충돌", "lane_end": "경로 이탈",
                                      "timeout": "시간 초과"}.get(meta.get("outcome"), "기록 일부")
        t1 = f"{res} · 실제 주행 {int(total_t // 60)}분 {int(total_t % 60)}초"
        t2 = "합류 · 출구 · 회전교차로 통과 (시드 %s)" % meta.get("seed")
        for txt, font, yy in ((t1, f_big, 0.40), (t2, f_mid, 0.52)):
            bb = d.textbbox((0, 0), txt, font=font)
            d.text(((W - (bb[2] - bb[0])) // 2, int(H * yy)), txt, font=font, fill=(255, 255, 255))
        proc.stdin.write(Image.alpha_composite(img, ov).convert("RGB").tobytes())
    proc.stdin.close()
    proc.wait()
    # 구간별 배속 요약
    used = {}
    for i in idx:
        z = rows[i]["zone"] or "(기타)"
        used[z] = used.get(z, 0) + 1
    print(f"저장: {mp4}  ({a.seconds}초, {fps} fps, 원본 {len(rows)} 스텝 = {total_t / 60:.1f}분)")
    for z, c in used.items():
        steps = sum(1 for r in rows if (r["zone"] or "(기타)") == z)
        print(f"  {ZONE_LABEL.get(z, z):30s} 원본 {steps * step_len:6.0f}초 → 영상 {c / fps:5.1f}초 "
              f"(약 ×{steps * step_len / max(c / fps, 1e-9):.0f})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="화면 없이 시드별 완주 여부 확인")
    c.add_argument("--model", default=DEFAULT_MODEL)
    c.add_argument("--seed", type=int, default=2026)
    c.add_argument("--tries", type=int, default=1)
    c.add_argument("--max-steps", type=int, default=0)
    c.add_argument("--stop-at-first", action="store_true")
    r = sub.add_parser("record", help="sumo-gui로 돌리며 스텝마다 캡처")
    r.add_argument("--model", default=DEFAULT_MODEL)
    r.add_argument("--seed", type=int, default=2026)
    r.add_argument("--out", default="video_out/full")
    r.add_argument("--max-steps", type=int, default=0, help="시험용: 이 스텝까지만")
    r.add_argument("--width", type=int, default=1280)
    r.add_argument("--height", type=int, default=720)
    e = sub.add_parser("edit", help="프레임 → 압축 mp4")
    e.add_argument("--src", default="video_out/full")
    e.add_argument("--mp4", default="video_out/team14_drive_30s.mp4")
    e.add_argument("--seconds", type=float, default=30.0)
    e.add_argument("--fps", type=int, default=30)
    e.add_argument("--key-weight", type=float, default=1.0,
                   help="핵심 구간에서 스텝당 출력 프레임 수 (1 = 0.5초당 1프레임 = ×15)")
    e.add_argument("--smooth", type=int, default=15, help="배속 전환을 부드럽게 할 스텝 수")
    e.add_argument("--pad", type=int, default=6, help="핵심 구간 앞뒤로 같이 느리게 할 스텝 수")
    e.add_argument("--end-hold", type=float, default=2.0, help="끝 결과 카드 길이(초)")
    e.add_argument("--width", type=int, default=1280)
    e.add_argument("--height", type=int, default=720)
    e.add_argument("--crf", type=int, default=20)
    a = ap.parse_args()
    os.chdir(BASE)
    {"check": cmd_check, "record": cmd_record, "edit": cmd_edit}[a.cmd](a)


if __name__ == "__main__":
    main()
