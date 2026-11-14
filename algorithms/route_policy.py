"""(팀14) 갈림길 길 선택 AI — 계층형 강화학습의 위쪽 정책.

운전(가감속·차선)은 기존 PPO가 맡고, 이 정책은 갈림길 직전에 한 번만
"어느 길로 갈지"를 고른다. 한 에피소드에 결정이 한 번뿐이라
상황(context) → 선택 → 보상(갈림 구간 통과시간)의 contextual bandit으로 보고
REINFORCE(정책 경사)로 학습한다.

  정책: pi(길 | x) = softmax(W x + b)            x = sumo_env._route_context() (길마다 3개)
  보상: r = -(갈림 구간 실제 통과시간) / 100초
  갱신: W <- W + lr * (r - 기준값) * grad log pi(선택 | x),  기준값 = 보상 이동평균

numpy만 쓰므로 가볍고, 가중치는 JSON으로 저장해 사람이 읽을 수 있다.
"""
import json

import numpy as np


class RoutePolicy:
    def __init__(self, route_names, ctx_dim, lr=0.5, seed=0):
        self.names = list(route_names)
        self.W = np.zeros((len(self.names), ctx_dim))
        self.b = np.zeros(len(self.names))
        self.lr = float(lr)
        self.baseline = None
        self.rng = np.random.default_rng(seed)

    def probs(self, x):
        z = self.W @ np.asarray(x, dtype=float) + self.b
        z -= z.max()
        p = np.exp(z)
        return p / p.sum()

    def sample(self, x):
        i = int(self.rng.choice(len(self.names), p=self.probs(x)))
        return self.names[i]

    def greedy(self, x):
        return self.names[int(np.argmax(self.probs(x)))]

    def update(self, x, name, reward):
        x = np.asarray(x, dtype=float)
        if self.baseline is None:
            self.baseline = reward
        adv = reward - self.baseline
        self.baseline = 0.9 * self.baseline + 0.1 * reward
        p = self.probs(x)
        onehot = np.zeros(len(self.names))
        onehot[self.names.index(name)] = 1.0
        g = onehot - p                       # grad of log softmax wrt logits
        self.W += self.lr * adv * np.outer(g, x)
        self.b += self.lr * adv * g
        return adv

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"names": self.names, "W": self.W.tolist(), "b": self.b.tolist(),
                       "baseline": self.baseline}, f, ensure_ascii=False, indent=1)

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        p = cls(d["names"], len(d["W"][0]))
        p.W, p.b, p.baseline = np.array(d["W"]), np.array(d["b"]), d.get("baseline")
        return p
