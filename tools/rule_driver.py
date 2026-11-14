"""(팀14) 박물관 경로용 규칙 기반 운전자 (학습 없음, 비교·도구용).

관측 37차원만 보고 운전한다: 앞차 간격 유지, 빨간·노란 신호 정지,
양보 교차로에서 다가오는 차가 있으면 정지, 내 차선이 경로상 곧 끝나면 옆 차선으로.
길 선택 AI 학습처럼 "운전은 고정하고 다른 것만 비교"할 때 쓴다.
"""
import numpy as np


def rule_action(obs, vmax, visibility=50.0, lookahead=150.0):
    v = obs[0] * vmax
    a = 0.4
    if obs[9] * visibility < 4 + 1.5 * v:                 # 같은 차선 앞차
        a = -1.0
    if len(obs) >= 37:
        sd, col = obs[31] * lookahead, obs[32]
        stop_d = 5 + v * v / 6
        if col < 0 and sd < stop_d:                        # 빨간불
            a = -1.0
        if col == 0 and v < sd < stop_d:                   # 노란불, 설 수 있으면 섬
            a = -1.0
        if obs[35] > 0 and obs[36] > 0 and obs[34] * lookahead < stop_d:   # 양보
            a = -1.0
    lc = 0.0
    if obs[23] < 0.6:                                      # 내 차선이 경로상 곧 끝남
        lc = 1.0 if obs[22] > obs[24] else -1.0
    return np.array([a, lc], dtype=np.float32)
