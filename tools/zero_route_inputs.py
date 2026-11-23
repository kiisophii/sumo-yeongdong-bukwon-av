"""(팀14, 11/24) 기존 모델(B)을 새 관측(TEAM14_ROUTE_OBS=coarse)으로 이어서 학습할 때 쓸 초기값을 만든다.

관측 [21..25] 5칸의 의미가 바뀌었으므로 첫 층에서 이 5칸의 가중치를 0으로 만들고,
예전 값 1.0("모든 차로 괜찮음")을 넣은 것과 같아지도록 bias를 보정한다.
이렇게 하지 않으면 B가 새 값을 예전 의미로 읽어 가속 출력이 음수로 포화되고 출발을 안 한다
(11/23 D 실험: 40만 스텝 동안 정지, 300판 완주 0).

사용: python tools/zero_route_inputs.py <B model.pt> <출력 .pt>
"""
import sys
import torch

src, dst = sys.argv[1], sys.argv[2]
sd = torch.load(src, map_location="cpu", weights_only=False)
W, b = sd["trunk.0.weight"], sd["trunk.0.bias"]
assert W.shape[1] == 37, W.shape
b += W[:, 21:26].sum(dim=1) * 1.0
W[:, 21:26] = 0.0
torch.save(sd, dst)
print("저장:", dst)
