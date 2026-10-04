"""학습된 모델의 주행 장면을 GIF로 저장 — 발표/프로젝트 페이지용.

sumo-gui 화면 캡처 대신, 화면 없는 시뮬레이션에서 차량 위치를 읽어
matplotlib으로 직접 그린다 (GUI가 없는 환경에서도 동작하고, 캡처 중
sumo-gui가 멈추는 문제가 없다). 카메라는 ego(빨간 차)를 따라간다.

사용법:
    python tools/record_gif.py results/team14_ppo_v1/model.pt
    python tools/record_gif.py results/team14_ppo_v1/model.pt --every 2 --view 220 --seed 5
결과: docs/img/drive.gif
"""
import argparse
import io
import math
import os
import sys

import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.collections import PolyCollection  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from PIL import Image  # noqa: E402

from env.road_config import ROAD, EGO, TRAFFIC  # noqa: E402
from env.mdp_config import SIMULATION, OBSERVATION, ACTION  # noqa: E402
from env import road_builder  # noqa: E402
import env.sumo_env as sumo_env  # noqa: E402
import sumolib  # noqa: E402
from train import REWARD  # noqa: E402
from test import load_agent  # noqa: E402

for _name in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if any(_name == f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _name
        break

# 컨트롤러별 색 (road_config의 GUI 색과 동일)
TYPE_COLORS = {"krauss": "#f2d21b", "idm": "#22c7d6", "eidm": "#f39a1e", "acc": "#d63fd0"}


GRASS = "#3f6b3a"


def make_palette():
    """GIF 고정 팔레트: 작은 빨간 차가 색 양자화에서 사라지지 않도록
    주요 색(ego 빨강, 컨트롤러 색, 도로/잔디/흰색)을 반드시 포함시킨다."""
    keys = ["#ff2a1a", "#2b2e31", GRASS, "#ffffff", "#000000"] + list(TYPE_COLORS.values())
    sw = Image.new("RGB", (len(keys) * 8 + 256, 8))
    for i, k in enumerate(keys):
        sw.paste(Image.new("RGB", (8, 8), k), (i * 8, 0))
    for g in range(256):                      # 회색 계조 (글자 배경·안티에일리어싱)
        sw.paste(Image.new("RGB", (1, 8), (g, g, g)), (len(keys) * 8 + g, 0))
    return sw.quantize(colors=64)


def lane_polygon(shape, width):
    """차선 중심선 → 폭을 가진 다각형 (도로 면 그리기용)."""
    pts = np.asarray(shape, dtype=float)
    left, right = [], []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        d = b - a
        n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-9)
        left.append(pts[i] + n * width / 2)
        right.append(pts[i] - n * width / 2)
    return np.vstack([left, right[::-1]])


def car_polygon(x, y, angle_deg, length=4.8, width=1.9):
    """SUMO 차량 위치(앞 범퍼 중앙)와 방향각(북=0, 시계방향) → 차체 사각형."""
    th = math.radians(90.0 - angle_deg)          # 수학 좌표계 각도
    ux, uy = math.cos(th), math.sin(th)
    vx, vy = -uy, ux
    cx, cy = x - ux * length / 2, y - uy * length / 2
    hl, hw = length / 2, width / 2
    return [(cx + ux * hl + vx * hw, cy + uy * hl + vy * hw),
            (cx + ux * hl - vx * hw, cy + uy * hl - vy * hw),
            (cx - ux * hl - vx * hw, cy - uy * hl - vy * hw),
            (cx - ux * hl + vx * hw, cy - uy * hl + vy * hw)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--out", default=os.path.join(BASE, "docs", "img", "drive.gif"))
    ap.add_argument("--every", type=int, default=2, help="몇 스텝마다 한 프레임")
    ap.add_argument("--max-steps", type=int, default=1000)
    ap.add_argument("--start-step", type=int, default=0, help="이 스텝부터 녹화 (앞부분 생략)")
    ap.add_argument("--view", type=float, default=200.0, help="화면 가로 시야(m)")
    ap.add_argument("--px", type=int, default=960, help="GIF 가로 픽셀")
    ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()

    np.random.seed(args.seed)
    sumo_dir = os.path.join(BASE, "env", "sumo")
    cfg = road_builder.build(ROAD, EGO, TRAFFIC, sumo_dir)
    net = sumolib.net.readNet(os.path.join(sumo_dir, "highway.net.xml"), withInternal=True)
    road_polys, marks = [], []
    for e in net.getEdges(withInternal=True):
        for lane in e.getLanes():
            road_polys.append(lane_polygon(lane.getShape(), lane.getWidth()))
            if not e.isSpecial() and lane.getIndex() > 0:   # 차선 사이 점선
                marks.append(lane_polygon(lane.getShape(), lane.getWidth())[len(lane.getShape()):])  # 오른쪽 경계

    env = sumo_env.SumoHighwayEnv(cfg, ROAD, EGO, SIMULATION, OBSERVATION, ACTION, REWARD,
                                  traffic=TRAFFIC, gui=False)
    agent = load_agent(args.model, env.observation_space.shape[0], env.action_space.shape[0])
    aspect = 9 / 16
    fig = plt.figure(figsize=(args.px / 100, args.px * aspect / 100), dpi=100,
                     facecolor=GRASS)
    palette = make_palette()
    ax = fig.add_axes([0, 0, 1, 1])
    frames = []
    lim = 80.0
    try:
        obs, _ = env.reset()
        T = sumo_env.traci
        for t in range(args.max_steps):
            obs, r, term, trunc, info = env.step(agent.predict(obs, deterministic=True))
            if term or trunc:
                print(f"종료: step={t + 1} collided={info['collided']} arrived={info['arrived']}")
                break
            if t < args.start_step or t % args.every:
                continue
            ex, ey = T.vehicle.getPosition("ego")
            ax.clear()
            ax.add_collection(PolyCollection(road_polys, facecolors="#2b2e31", edgecolors="none"))
            for m in marks:
                ax.plot(m[:, 0], m[:, 1], color="white", lw=0.8, ls=(0, (4, 6)), alpha=0.8)
            for vid in T.vehicle.getIDList():
                x, y = T.vehicle.getPosition(vid)
                if abs(x - ex) > args.view or abs(y - ey) > args.view:
                    continue
                ang = T.vehicle.getAngle(vid)
                if vid == "ego":
                    col = "#ff2a1a"
                else:
                    tid = T.vehicle.getTypeID(vid).replace("car_", "")
                    col = TYPE_COLORS.get(tid, "#dddddd")
                ax.add_patch(plt.Polygon(car_polygon(x, y, ang), closed=True,
                                         fc=col, ec="black", lw=0.6, zorder=5 if vid == "ego" else 4))
            half = args.view / 2
            ax.set_xlim(ex - half, ex + half)
            ax.set_ylim(ey - half * aspect, ey + half * aspect)
            ax.set_aspect("equal")
            ax.axis("off")
            v = info["speed"] or 0.0
            if not T.vehicle.getRoadID("ego").startswith(":"):   # 교차로 내부 차선은 제외
                lim = T.vehicle.getAllowedSpeed("ego") * 3.6
            ax.text(0.015, 0.95, f"t = {(t + 1) * 0.5:5.1f} s   속도 {v * 3.6:5.1f} km/h (제한 {lim:.0f})"
                    f"   차로 {T.vehicle.getLaneIndex('ego') + 1}",
                    transform=ax.transAxes, color="white", fontsize=12, va="top",
                    bbox=dict(fc="black", alpha=0.55, ec="none", pad=4))
            ax.text(0.985, 0.04, "PPO 자율주행 차량(빨강) · 영동고속도로 북수원IC (강릉 방향)",
                    transform=ax.transAxes, color="white", fontsize=10, ha="right",
                    bbox=dict(fc="black", alpha=0.45, ec="none", pad=3))
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100, facecolor=GRASS)
            frames.append(Image.open(buf).convert("RGB").quantize(
                palette=palette, dither=Image.Dither.NONE))
    finally:
        env.close()
    if not frames:
        raise RuntimeError("프레임이 없습니다.")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    frames[0].save(args.out, save_all=True, append_images=frames[1:],
                   duration=int(1000 / args.fps), loop=0, optimize=True)
    print(f"저장: {args.out}  ({len(frames)} 프레임, {os.path.getsize(args.out) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
