"""발표 시연용: sumo-gui가 바로 재생되며 빨간 자율주행 차를 따라간다 (▶ 누를 필요 없음).

사용법:
    python tools/demo.py                         # 최종 모델, 1회 주행
    python tools/demo.py --episodes 2 --delay 80 --zoom 3500
    python tools/demo.py --model results/team14_ppo_v2/model.pt

화면 조작: 마우스 휠 = 확대/축소, 툴바 Delay(ms) = 속도 (클수록 느림)
"""
import argparse
import time
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

from env.road_config import ROAD, EGO, TRAFFIC  # noqa: E402
from env.mdp_config import SIMULATION, OBSERVATION, ACTION  # noqa: E402
from env import road_builder  # noqa: E402
import env.sumo_env as sumo_env  # noqa: E402
from train import REWARD  # noqa: E402
from test import load_agent  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="results/team14_ppo_v1/model.pt")
    ap.add_argument("--episodes", type=int, default=1)
    ap.add_argument("--delay", type=float, default=60.0, help="스텝 사이 지연(ms), 클수록 느림")
    ap.add_argument("--zoom", type=float, default=3000.0, help="확대 배율(%%), 클수록 가까이")
    ap.add_argument("--hold", type=float, default=0.0,
                    help="ego가 --hold-edge 끝에 오면 이 초만큼 멈춤 (캡처용)")
    ap.add_argument("--hold-edge", default="", help="멈출 위치의 edge id (예: 사거리 W_C)")
    args = ap.parse_args()

    cfg = road_builder.build(ROAD, EGO, TRAFFIC, os.path.join(BASE, "env", "sumo"))
    sim = dict(SIMULATION, gui_delay=args.delay, gui_zoom=args.zoom, gui_track_ego=True)
    env = sumo_env.SumoHighwayEnv(cfg, ROAD, EGO, sim, OBSERVATION, ACTION, REWARD,
                                  traffic=TRAFFIC, gui=True, gui_autostart=True)
    agent = load_agent(os.path.join(BASE, args.model), env.observation_space.shape[0],
                       env.action_space.shape[0])
    try:
        for ep in range(args.episodes):
            obs, _ = env.reset()
            T = sumo_env.traci
            view = T.gui.getIDList()[0]
            T.gui.trackVehicle(view, "ego")      # 빨간 차 추적
            T.gui.setZoom(view, args.zoom)
            steps, held = 0, False
            while True:
                obs, r, term, trunc, info = env.step(agent.predict(obs, deterministic=True))
                steps += 1
                if term or trunc:
                    break
                # 캡처용 정지: ego가 지정한 edge 끝(교차로 앞) 30 m 안에 오면
                # 시뮬레이션 진행을 hold초 동안 멈춘다 (화면은 그대로 떠 있음)
                if (args.hold > 0 and not held and args.hold_edge
                        and T.vehicle.getRoadID("ego") == args.hold_edge):
                    lane = T.vehicle.getLaneID("ego")
                    if T.lane.getLength(lane) - T.vehicle.getLanePosition("ego") < 30:
                        print(f"교차로 앞에서 {args.hold:.0f}초 정지 — 지금 캡처하세요", flush=True)
                        time.sleep(args.hold)
                        held = True
            result = ("경로 이탈" if info.get("lane_end") else "충돌" if info["collided"]
                      else "완주" if info["arrived"] else "시간 초과")
            print(f"주행 {ep + 1}: {result}, {steps * 0.5:.0f}초", flush=True)
    finally:
        env.close()


if __name__ == "__main__":
    main()
