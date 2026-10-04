"""도로망 개요도(PNG) 생성 — 보고서/발표 자료용.

env/sumo/ 에 생성된 도로망(highway.net.xml)과 주변 지형(highway.scenery.xml)을
그리고, ego 경로를 빨간색으로 강조하고 주요 구조(진출/합류/차로감소/분기)에
설명을 붙인다.

사용법 (먼저 view_road.py --nogui 등으로 도로를 한 번 생성해 둘 것):
    python tools/plot_network.py                     # docs/img/network_overview.png
    python tools/plot_network.py --out my.png --dpi 200
"""
import argparse
import os
import sys
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from env.sumo_env import SumoHighwayEnv  # noqa: F401,E402  (SUMO_HOME 자동 설정)
import sumolib  # noqa: E402

# 한글 폰트 (Windows: 맑은 고딕, macOS: AppleGothic, 그 외: 기본)
for _name in ("Malgun Gothic", "AppleGothic", "NanumGothic"):
    if any(_name == f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = _name
        break
plt.rcParams["axes.unicode_minus"] = False

# 주요 지점 설명: (edge id, 문구, 글상자 오프셋 dx, dy [m])
ANNOTATIONS = [
    ("474882669", "시작: 3차로 본선\n(80 km/h)", 100, 300),
    ("474882669-AddedOffRampEdge", "① 진출 감속차로", -200, 350),
    ("51066826", "② 북수원IC 진출", 450, 250),
    ("51066897", "③ 북수원IC 진입\n(2차로 램프)", -900, -500),
    ("206488360", "④ 합류 후 5차로", 150, 300),
    ("1307152438", "⑤ 차로 감소 5→4", -500, -450),
    ("833403522", "⑥ 교량 3차로 병목", -150, -550),
    ("549032648", "⑦ 분기(진출 2차로)", 150, -450),
    ("50981265", "도착: 본선 3차로\n(100 km/h)", -700, 350),
]


def color_of(s: str):
    v = [float(x) for x in s.split(",")[:3]]
    return [x / 255 for x in v] if max(v) > 1 else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(BASE, "docs", "img", "network_overview.png"))
    ap.add_argument("--dpi", type=int, default=160)
    args = ap.parse_args()

    sumo_dir = os.path.join(BASE, "env", "sumo")
    net = sumolib.net.readNet(os.path.join(sumo_dir, "highway.net.xml"))
    ego_edges = set()
    for r in sumolib.xml.parse(os.path.join(sumo_dir, "highway.rou.xml"), "route"):
        if r.id == "r0":
            ego_edges = set(r.edges.split())

    (xmin, ymin), (xmax, ymax) = net.getBBoxXY()
    pad = 250
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_facecolor("#f4f1ea")

    scen = os.path.join(sumo_dir, "highway.scenery.xml")
    if os.path.exists(scen):
        for p in ET.parse(scen).getroot().iter("poly"):
            pts = [tuple(map(float, s.split(","))) for s in p.get("shape").split()]
            col = p.get("color", "0.8,0.8,0.8")
            c = color_of(col) if "," in col else "lightgray"
            xs, ys = zip(*pts)
            if p.get("fill") in ("1", "true"):
                ax.fill(xs, ys, color=c, alpha=0.45, lw=0)
            else:
                ax.plot(xs, ys, color=c, lw=0.6, alpha=0.8)

    for e in net.getEdges():
        on_route = e.getID() in ego_edges
        for lane in e.getLanes():
            xs, ys = zip(*lane.getShape())
            ax.plot(xs, ys, color="#d62728" if on_route else "#333333",
                    lw=1.4 if on_route else 0.8, zorder=3 if on_route else 2)

    for eid, text, dx, dy in ANNOTATIONS:
        if not net.hasEdge(eid):
            continue
        shape = net.getEdge(eid).getShape()
        x, y = shape[len(shape) // 2]
        ax.annotate(text, (x, y), xytext=(x + dx, y + dy), fontsize=10,
                    arrowprops=dict(arrowstyle="->", color="#444"),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#888", alpha=0.9),
                    zorder=5)

    ax.set_xlim(xmin - pad, xmax + pad)
    ax.set_ylim(ymin - pad, ymax + pad)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("영동고속도로 북수원IC 일대 (강릉 방향) — SUMO 도로망  "
                 "(빨강: 자율주행 차량 경로, 약 7.1 km)", fontsize=13)
    ax.text(0.99, 0.01, "Map data © OpenStreetMap contributors (ODbL)",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color="#555")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=args.dpi, bbox_inches="tight")
    print(f"저장: {args.out}")


if __name__ == "__main__":
    main()
