"""학습된 모델의 주행 장면을 sumo-gui로 캡처해 GIF로 저장 — 발표/프로젝트 페이지용.

사용법:
    python tools/record_gif.py results/team14_ppo_v1/model.pt
    python tools/record_gif.py results/team14_ppo_v1/model.pt --every 2 --max-steps 900 --zoom 1800

화면은 ego(빨간 차)를 따라가며, every 스텝마다 한 장씩 캡처한다.
결과: docs/img/drive.gif (+ 프레임은 임시 폴더에 저장 후 삭제)
"""
import argparse
import os
import shutil
import sys
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from PIL import Image  # noqa: E402

from env.road_config import ROAD, EGO, TRAFFIC  # noqa: E402
from env.mdp_config import SIMULATION, OBSERVATION, ACTION  # noqa: E402
from env import road_builder  # noqa: E402
import env.sumo_env as sumo_env  # noqa: E402
from train import REWARD  # noqa: E402
from test import load_agent  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--out", default=os.path.join(BASE, "docs", "img", "drive.gif"))
    ap.add_argument("--every", type=int, default=2, help="몇 스텝마다 캡처할지")
    ap.add_argument("--max-steps", type=int, default=1000)
    ap.add_argument("--zoom", type=float, default=1800.0)
    ap.add_argument("--width", type=int, default=960, help="GIF 가로 픽셀")
    ap.add_argument("--fps", type=int, default=10)
    ap.add_argument("--seed", type=int, default=3)
    args = ap.parse_args()

    import numpy as np
    np.random.seed(args.seed)
    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    sim = dict(SIMULATION, gui_delay=0, gui_zoom=args.zoom)
    env = sumo_env.SumoHighwayEnv(cfg, ROAD, EGO, sim, OBSERVATION, ACTION, REWARD,
                                  traffic=TRAFFIC, gui=True)
    agent = load_agent(args.model, env.observation_space.shape[0],
                       env.action_space.shape[0])
    tmp = tempfile.mkdtemp(prefix="gif_")
    frames = []
    try:
        obs, _ = env.reset()
        T = sumo_env.traci
        view = T.gui.getIDList()[0]
        for t in range(args.max_steps):
            obs, r, term, trunc, info = env.step(agent.predict(obs, deterministic=True))
            if term or trunc:
                print(f"종료: step={t + 1} collided={info['collided']} arrived={info['arrived']}")
                break
            if t % args.every == 0:
                path = os.path.join(tmp, f"f{t:05d}.png")
                T.gui.screenshot(view, path)
                frames.append(path)
        T.simulationStep()   # 마지막 screenshot 요청이 실제로 그려지도록
    finally:
        env.close()

    imgs = []
    for p in frames:
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        h = int(im.height * args.width / im.width)
        imgs.append(im.resize((args.width, h)).quantize(colors=128))
    if not imgs:
        raise RuntimeError("캡처된 프레임이 없습니다.")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    imgs[0].save(args.out, save_all=True, append_images=imgs[1:],
                 duration=int(1000 / args.fps), loop=0, optimize=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"저장: {args.out}  ({len(imgs)} 프레임)")


if __name__ == "__main__":
    main()
