"""configs/road_config.py 를 읽어 SUMO 도로 파일들을 자동 생성하는 모듈.

SUMO는 도로를 여러 XML 파일로 정의한다:
    highway.nod.xml  : 노드(교차점/도로 끝점)의 좌표
    highway.edg.xml  : 엣지(도로 구간) — 어느 노드에서 어느 노드로, 차선 수, 제한속도
    highway.net.xml  : 위 두 파일을 netconvert 도구로 컴파일한 "완성된 도로망"
                       (SUMO가 실제로 읽는 파일. 직접 작성하기엔 복잡해서 도구로 생성)
    highway.rou.xml  : 차량 타입(vType)과 교통 수요(flow/route) 정의
    highway.sumocfg  : 위 파일들을 묶어주는 설정 파일 (시뮬레이션 실행의 진입점)

train.py / test.py 가 시작할 때마다 build()를 호출하므로,
road_config.py만 수정하면 도로가 자동으로 다시 만들어진다.
"""
import os
import subprocess

from sumolib import checkBinary  # SUMO 실행파일(sumo, netconvert 등) 경로를 찾아주는 유틸
from env.mdp_config import SIMULATION
try:
    from env.road_config import SCENERY
except ImportError:      # 구버전 설정 하위호환
    SCENERY = {"trees": False}


def build(road: dict, ego: dict, traffic: dict, out_dir: str) -> str:
    """SUMO 파일들을 out_dir에 생성하고, sumocfg 파일 경로를 반환한다.

    Args:
        road:    configs.road_config.ROAD    (도로 형상)
        ego:     configs.road_config.EGO     (RL 차량 속성)
        traffic: configs.road_config.TRAFFIC (배경 교통류)
        out_dir: 생성 위치 (보통 프로젝트의 sumo/ 폴더)

    road["type"] == "osm" 이면 실제 지도(OpenStreetMap) 기반 도로망을 만든다
    (_build_osm 참고). 지정하지 않으면 기존 "직선 편도 도로" 방식.
    """
    if road.get("type", "straight") == "osm":
        return _build_osm(road, ego, traffic, out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # ──────────────────────────────────────────────────────
    # 1) 노드 파일: 직선 도로의 양 끝점 2개
    #    n0 = 원점(출발), n1 = length만큼 떨어진 지점(도착)
    # ──────────────────────────────────────────────────────
    with open(os.path.join(out_dir, "highway.nod.xml"), "w") as f:
        f.write(f"""<nodes>
    <node id="n0" x="0" y="0"/>
    <node id="n1" x="{road['length']}" y="0"/>
</nodes>
""")

    # ──────────────────────────────────────────────────────
    # 2) 엣지 파일: n0 → n1 을 잇는 도로 구간 하나
    #    numLanes = 차선 수, speed = 제한속도(m/s)
    # ──────────────────────────────────────────────────────
    with open(os.path.join(out_dir, "highway.edg.xml"), "w") as f:
        f.write(f"""<edges>
    <edge id="e0" from="n0" to="n1" numLanes="{road['num_lanes']}" speed="{road['speed_limit']}"/>
</edges>
""")

    # ──────────────────────────────────────────────────────
    # 3) 라우트 파일: 차량 타입 2종 + 배경 교통 flow
    #
    #    <vType>  : 차량의 물리 속성 템플릿
    #       ego_type : RL이 조종할 차 (빨간색, color="1,0,0" = RGB)
    #    <vTypeDistribution> : 배경차 컨트롤러 믹스.
    #       TRAFFIC["controllers"]에 정의된 여러 차량추종모델(Krauss/IDM/
    #       EIDM/ACC 등)을 probability 비율로 섞는다. flow가 이 분포를
    #       type으로 쓰면, 투입되는 차량마다 SUMO가 확률적으로 타입을 뽑는다.
    #    <route>  : 지나갈 엣지들의 나열. 여기선 e0 하나뿐.
    #    <flow>   : 교통 수요 정의. period="X"는 "X초마다 정확히 1대씩"
    #               → 등간격(uniform) 생성. (vehsPerHour와 등가지만
    #               "비슷한 간격으로 새로 생성"을 명시적으로 보장)
    #               ego는 여기에 없고, 환경(sumo_env.py)이 reset마다
    #               traci.vehicle.add()로 직접 투입한다.
    # ──────────────────────────────────────────────────────
    vtypes_block, flow_type = _vtypes_block(traffic)

    with open(os.path.join(out_dir, "highway.rou.xml"), "w") as f:
        f.write(f"""<routes>
    <vType id="ego_type" accel="{ego['accel']}" decel="{ego['decel']}" maxSpeed="{ego['max_speed']}" color="1,0,0" vClass="passenger" guiShape="passenger/sedan"/>
{vtypes_block}
    <route id="r0" edges="e0"/>
    <flow id="traffic" type="{flow_type}" route="r0" begin="0" end="100000"
          period="{3600.0 / traffic['vehs_per_hour']:.2f}"
          departLane="{traffic['depart_lane']}" departSpeed="{traffic['depart_speed']}"/>
</routes>
""")
    return _finish_straight(road, out_dir)


def _vtypes_block(traffic: dict):
    """배경차 vType(Distribution) XML 블록과 flow가 쓸 type id를 반환."""
    controllers = traffic.get("controllers")
    if controllers:
        # probability 합이 1이 아니어도 되도록 자동 정규화
        total_p = sum(float(c.get("probability", 1.0))
                      for c in controllers.values())
        vtype_lines = []
        for name, c in controllers.items():
            prob = float(c.get("probability", 1.0)) / total_p
            attrs = [
                f'id="car_{name}"',
                f'probability="{prob:.4f}"',
                f'carFollowModel="{c["carFollowModel"]}"',
                f'accel="{c.get("accel", 2.5)}"',
                f'decel="{c.get("decel", 4.5)}"',
                f'tau="{c.get("tau", 1.0)}"',
                f'minGap="{c.get("min_gap", 2.5)}"',
                # 컨트롤러별 희망속도 오버라이드 (없으면 공통 max_speed).
                # 컨트롤러마다 속도를 다르게 주면 차선 간 속도차가 생겨
                # "추월할 이유"가 자연스럽게 만들어진다.
                f'maxSpeed="{c.get("max_speed", traffic["max_speed"])}"',
                f'color="{c.get("color", "1,1,0")}"',
                'vClass="passenger"', 'guiShape="passenger/sedan"',
            ]
            # sigma는 Krauss 계열에만 의미가 있으므로 지정된 경우에만 넣는다
            if "sigma" in c:
                attrs.append(f'sigma="{c["sigma"]}"')
            # ── 배경차 차선 유지 (keep_lane, 기본 True) ──
            # 배경차의 자율 차선변경(전략/협조/속도이득/우측유지)을 전부 꺼서
            # 각자 자기 차선을 지키게 한다. 이유:
            #   배경차가 자유롭게 돌아다니면 (측정: 150스텝에 477회 변경)
            #   차선 간 틈이 수시로 닫혀서, ego가 틈을 노려 파고드는
            #   "칼치기 추월"을 학습할 안정적인 기회 자체가 사라진다.
            #   배경차가 차선을 유지하면 "느린 차 뒤 → 옆 틈으로 변경 →
            #   가속"이라는 추월 패턴이 재현 가능한 형태로 나타난다.
            # 특정 컨트롤러만 돌아다니게 하려면 그 항목에 "keep_lane": False.
            # speedDev: 같은 타입 안에서도 개체별 희망속도 편차 (0~)
            #   speed_factor(분포 직접 지정)가 있으면 그쪽이 편차까지 정의한다.
            if "speed_factor" not in c:
                attrs.append(f'speedDev="{c.get("speed_dev", 0.1)}"')
            if "speed_factor" in c:
                # 희망속도 = 차선 제한속도 × speedFactor (OSM 도로처럼 구간마다
                # 제한속도가 다를 때 자연스럽다). speedDev와 함께 분포를 이룬다.
                attrs.append(f'speedFactor="{c["speed_factor"]}"')
            if c.get("keep_lane", True):
                attrs += ['lcStrategic="0"', 'lcCooperative="0"',
                          'lcSpeedGain="0"', 'lcKeepRight="0"']
            else:
                # 차선변경 허용 시 성향 파라미터(lcStrategic 등)를 그대로 전달.
                # 합류/분기 도로에서는 경로를 따라가기 위한 전략적 변경이 필수.
                for k, v in (c.get("lc") or {}).items():
                    attrs.append(f'{k}="{v}"')
            vtype_lines.append("        <vType " + " ".join(attrs) + "/>")
        vtypes_block = ('    <vTypeDistribution id="carDist">\n'
                        + "\n".join(vtype_lines)
                        + "\n    </vTypeDistribution>")
        flow_type = "carDist"
    else:
        # controllers 설정이 없으면 예전 방식(단일 Krauss)으로 동작 (하위호환)
        vtypes_block = (f'    <vType id="car" accel="2.5" decel="4.5" '
                        f'maxSpeed="{traffic["max_speed"]}" '
                        f'sigma="{traffic.get("sigma", 0.5)}" '
                        f'vClass="passenger" guiShape="passenger/sedan"/>')
        flow_type = "car"

    return vtypes_block, flow_type


def _finish_straight(road: dict, out_dir: str) -> str:
    """직선 도로 모드의 GUI 설정 / 장식 / sumocfg / netconvert 단계."""
    # ──────────────────────────────────────────────────────
    # 4) GUI 기본 시각화 설정
    #    GUI 관련 값의 source of truth는 env/mdp_config.py의 SIMULATION 하나뿐이다.
    #    view_road.py / train.py / test.py / 데이터 수집 모두 build()를 거치므로
    #    gui_zoom/gui_delay를 바꾸면 생성되는 highway.gui.xml에도 즉시 반영된다.
    # ──────────────────────────────────────────────────────
    # GUI 시작 화면: "도로 시작 구간"이 차선까지 보이게 자동 확대해둔다.
    #   (12km 전체 맞춤으로 시작하면 도로가 가느다란 선으로만 보여 직관성이
    #    떨어지므로, ego가 등장할 시작부를 확대해 대기 화면으로 삼는다.
    #    ▶ 재생 후에는 env가 ego를 추적(trackVehicle)하며 시점을 가져간다.)
    # 좌표/배율은 도로 길이·차선 수에서 "계산"하므로 설정을 바꿔도 안 어긋난다:
    #   zoom(%) = 도로길이 / 보고싶은폭(gui_view_width) × 100
    #     (SUMO zoom은 "네트워크 전체 = 100%" 기준)
    #   y 중심 = -차선폭(3.2m) × 차선수 / 2   (SUMO는 차선을 y<0 쪽으로 그림)
    gui_delay = float(SIMULATION.get("gui_delay", 100.0))
    view_width = float(SIMULATION.get("gui_view_width", 500.0))   # 시작 화면 시야(m)
    zoom = float(road["length"]) / view_width * 100.0
    center_x = view_width * 0.4                                   # 시작점이 화면 왼쪽에 오게
    center_y = -3.2 * int(road["num_lanes"]) / 2.0
    gui_settings_path = os.path.join(out_dir, "highway.gui.xml")
    with open(gui_settings_path, "w") as f:
        f.write(f"""<viewsettings>
    <scheme name="real world"/>
    <viewport zoom="{zoom:.0f}" x="{center_x:.1f}" y="{center_y:.1f}" angle="0"/>
    <delay value="{gui_delay}"/>
</viewsettings>
""")

    # ──────────────────────────────────────────────────────
    # 4.7) 도로변 장식(나무) — 순수 시각 요소
    #
    # SUMO의 <poly>(다각형)로 "초록 수관 + 갈색 줄기"를 그려 도로
    # 양옆에 심는다. additional 파일로 로드되며 차량 물리와 완전히
    # 무관하다 (충돌/관측/보상 어디에도 안 잡힘).
    # 좌표계: 차선은 y ∈ [0, -3.2×차선수] 영역 → 왼쪽 숲은 y > 0,
    # 오른쪽 숲은 y < -3.2×차선수 - side_offset 에 배치.
    # ──────────────────────────────────────────────────────
    _write_scenery(out_dir, road)

    # ──────────────────────────────────────────────────────
    # 5) sumocfg: "이 net 파일과 이 route 파일로 시뮬레이션해라"
    # ──────────────────────────────────────────────────────
    cfg_path = os.path.join(out_dir, "highway.sumocfg")
    with open(cfg_path, "w") as f:
        f.write("""<configuration>
    <input>
        <net-file value="highway.net.xml"/>
        <route-files value="highway.rou.xml"/>
        <additional-files value="highway.scenery.xml"/>
    </input>
    <gui_only>
        <gui-settings-file value="highway.gui.xml"/>
    </gui_only>
</configuration>
""")

    # ──────────────────────────────────────────────────────
    # 6) netconvert 실행: nod + edg → net.xml 컴파일
    #    (SUMO 설치 시 함께 깔리는 커맨드라인 도구)
    # ──────────────────────────────────────────────────────
    netconvert = checkBinary("netconvert")
    subprocess.run(
        [netconvert,
         "--node-files", os.path.join(out_dir, "highway.nod.xml"),
         "--edge-files", os.path.join(out_dir, "highway.edg.xml"),
         "-o", os.path.join(out_dir, "highway.net.xml")],
        check=True,           # 실패하면 예외를 던져서 바로 알 수 있게
        capture_output=True,  # 출력은 조용히 삼킴
    )
    return cfg_path


def _blob(cx: float, cy: float, r: float, rng, n: int = 14,
          roughness: float = 0.35) -> str:
    """유기적인(울퉁불퉁한) 수관 실루엣 다각형을 만든다.

    실제 나무를 위에서 내려다보면 완전한 원이 아니라 잎 뭉치들이
    만드는 불규칙한 테두리다. 꼭짓점마다 반지름을 무작위로 흔들되,
    이웃 꼭짓점과 평균을 내서(smoothing) 뾰족하지 않고 부드럽게
    울퉁불퉁한 실루엣을 얻는다.
    """
    import math
    raw = [1.0 + rng.uniform(-roughness, roughness) for _ in range(n)]
    sm = [(raw[i - 1] + raw[i] + raw[(i + 1) % n]) / 3.0 for i in range(n)]
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * sm[i]
        pts.append(f"{cx + rr * math.cos(a):.2f},{cy + rr * math.sin(a):.2f}")
    return " ".join(pts)


def _write_scenery(out_dir: str, road: dict):
    """도로변 나무를 highway.scenery.xml (additional 파일)로 생성.

    항공뷰(top-down) 조경처럼 보이도록 나무 한 그루를 여러 겹으로 그린다:
      layer 1  그림자  : 수관을 남동쪽으로 살짝 밀어낸 반투명 검정 blob
                         (해가 북서쪽에 있는 항공사진 느낌)
      layer 2  수관 몸통: 중간톤 초록의 불규칙 실루엣
      layer 3  잎 뭉치  : 수관 안에 어두운/짙은 클럼프 1~2개
                         → 캐노피의 입체적인 질감
      layer 4  하이라이트: 북서쪽으로 치우친 밝은 초록 작은 blob
    배치도 실제 조경처럼: 단독목 / 2~3그루 군락 / 낮은 관목이 섞인다.
    SCENERY["trees"]가 False면 빈 additional 파일 생성.
    """
    import random
    path = os.path.join(out_dir, "highway.scenery.xml")
    cfg = SCENERY if isinstance(SCENERY, dict) else {}
    if not cfg.get("trees", False):
        with open(path, "w") as f:
            f.write("<additional/>\n")
        return

    rng = random.Random(int(cfg.get("seed", 7)))
    spacing = float(cfg.get("tree_spacing", 45.0))
    jitter = float(cfg.get("tree_jitter", 0.5))
    side = float(cfg.get("side_offset", 6.0))
    length = float(road["length"])
    road_bottom = -3.2 * int(road["num_lanes"])

    # (몸통, 어두운 클럼프, 밝은 하이라이트) 초록 팔레트 — 수종별 톤
    palettes = [
        ("46,110,44", "32,84,32", "96,158,84"),
        ("38,98,40",  "26,72,28", "84,146,74"),
        ("56,122,50", "40,92,38", "110,168,92"),
        ("30,88,36",  "20,64,26", "76,138,70"),
    ]
    bush_greens = ["70,124,58", "84,136,64", "62,112,52"]

    lines = ["<additional>"]
    tid = [0]

    def draw_tree(x, y, r):
        body, dark, light = rng.choice(palettes)
        i = tid[0]; tid[0] += 1
        # 그림자 (남동쪽 +x, -y 로 오프셋, 반투명)
        lines.append(f'    <poly id="sh_{i}" color="20,26,18,70" fill="1" '
                     f'layer="1" shape="{_blob(x + r*0.35, y - r*0.35, r*1.02, rng)}"/>')
        # 수관 몸통
        lines.append(f'    <poly id="tr_{i}" color="{body}" fill="1" '
                     f'layer="2" shape="{_blob(x, y, r, rng)}"/>')
        # 잎 뭉치 1~2개 (어두운 톤, 수관 내부 무작위 위치)
        for k in range(rng.randint(1, 2)):
            ox = rng.uniform(-0.35, 0.35) * r
            oy = rng.uniform(-0.35, 0.35) * r
            lines.append(f'    <poly id="cl_{i}_{k}" color="{dark}" fill="1" '
                         f'layer="3" shape="{_blob(x + ox, y + oy, r * rng.uniform(0.4, 0.6), rng, n=10)}"/>')
        # 하이라이트 (북서쪽 -x, +y — 그림자 반대 방향)
        lines.append(f'    <poly id="hl_{i}" color="{light}" fill="1" '
                     f'layer="4" shape="{_blob(x - r*0.28, y + r*0.28, r*0.34, rng, n=8, roughness=0.25)}"/>')

    def draw_bush(x, y):
        i = tid[0]; tid[0] += 1
        g = rng.choice(bush_greens)
        r = rng.uniform(1.0, 1.8)
        lines.append(f'    <poly id="bsh_{i}" color="20,26,18,55" fill="1" '
                     f'layer="1" shape="{_blob(x + 0.3, y - 0.3, r, rng, n=8)}"/>')
        lines.append(f'    <poly id="bs_{i}" color="{g}" fill="1" '
                     f'layer="2" shape="{_blob(x, y, r, rng, n=8)}"/>')

    for side_sign, base_y in [(+1, side), (-1, road_bottom - side)]:
        x = rng.uniform(0, spacing)
        while x < length:
            y = base_y + side_sign * rng.uniform(0, 4.0)
            roll = rng.random()
            if roll < 0.12:
                draw_bush(x, y)                        # 15%: 낮은 관목
            elif roll < 0.67:
                draw_tree(x, y, rng.uniform(2.6, 4.6))  # 55%: 단독목 (실제 수관 스케일)
            else:
                # 25%: 2~3그루 군락 (겹치듯 붙여 심어 숲 덩어리 느낌)
                n = rng.randint(2, 4)
                for _ in range(n):
                    gx = x + rng.uniform(-5.5, 5.5)
                    gy = y + side_sign * rng.uniform(-2.0, 4.5)
                    draw_tree(gx, gy, rng.uniform(2.2, 3.8))
                x += spacing * 0.4                     # 군락 뒤엔 간격 조금 더
            x += spacing * rng.uniform(1.0 - jitter, 1.0 + jitter)
    lines.append("</additional>")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


# ══════════════════════════════════════════════════════════════════
# 실제 지도(OpenStreetMap) 기반 도로망
# ══════════════════════════════════════════════════════════════════
def _resolve(path: str) -> str:
    """road_config의 상대경로를 프로젝트 루트 기준 절대경로로."""
    if os.path.isabs(path):
        return path
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, path)


def _build_osm(road: dict, ego: dict, traffic: dict, out_dir: str) -> str:
    """OSM 파일로 실제 도로망을 만들고 sumocfg 경로를 반환한다.

    처리 순서:
      1) netconvert  : OSM(고속도로 본선+램프) → highway.net.xml
                       (--ramps.guess로 가속/감속 차로를 자동 생성)
      2) 경로 계산    : road_config의 (출발 edge, 도착 edge) 쌍을
                       sumolib 최단경로로 edge 나열로 변환
      3) rou.xml     : ego 경로(r0) + 배경차 경로별 flow
      4) polyconvert : 주변 건물/녹지/하천 OSM → highway.scenery.xml (시각 요소)
      5) gui.xml / sumocfg

    ★ 이 함수는 계산된 ego 경로 길이를 road["length"]에 기록한다.
      (sumo_env가 도로 길이·GUI 기준값으로 사용)
    """
    import sumolib

    os.makedirs(out_dir, exist_ok=True)
    net_path = os.path.join(out_dir, "highway.net.xml")

    # ── 1) netconvert ──
    netconvert = checkBinary("netconvert")
    cmd = [netconvert, "--osm-files", _resolve(road["osm_file"]),
           "-o", net_path,
           "--geometry.remove",           # 불필요한 중간 노드 정리
           "--ramps.guess",               # 진입/진출 램프의 가감속 차로 생성
           "--junctions.join",            # 가까운 교차점 병합
           "--remove-edges.isolated",
           "--no-turnarounds",
           "--output.street-names",
           "--no-warnings"]
    cmd += list(road.get("netconvert_options", []))
    subprocess.run(cmd, check=True, capture_output=True)

    net = sumolib.net.readNet(net_path)

    def path(frm: str, to: str):
        edges, _ = net.getShortestPath(net.getEdge(frm), net.getEdge(to))
        if not edges:
            raise RuntimeError(f"경로 없음: {frm} → {to} (road_config 확인)")
        return [e.getID() for e in edges]

    # ── 2) 경로 ──
    ego_edges = path(*road["ego_route"])
    road["length"] = sum(net.getEdge(e).getLength() for e in ego_edges)
    road["num_lanes"] = max(net.getEdge(e).getLaneNumber() for e in ego_edges)

    routes = traffic.get("routes", {})
    # 콘솔 요약용 총 교통량 (train.py 등이 출력)
    traffic["vehs_per_hour"] = sum(float(r["vehs_per_hour"]) for r in routes.values())
    route_lines = [f'    <route id="r0" edges="{" ".join(ego_edges)}"/>']
    flow_lines = []
    # 계산값을 파일로도 남긴다 — build()를 거치지 않는 프로세스(병렬 수집
    # 워커 등)에서도 sumo_env가 읽어 쓸 수 있도록.
    import json
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump({"length": road["length"], "num_lanes": road["num_lanes"],
                   "vehs_per_hour": traffic["vehs_per_hour"]}, f)
    vtypes_block, flow_type = _vtypes_block(traffic)
    for name, r in routes.items():
        edges = path(r["from"], r["to"])
        route_lines.append(f'    <route id="r_{name}" edges="{" ".join(edges)}"/>')
        flow_lines.append(
            f'    <flow id="f_{name}" type="{flow_type}" route="r_{name}" '
            f'begin="0" end="100000" vehsPerHour="{r["vehs_per_hour"]}" '
            f'departLane="{r.get("depart_lane", traffic["depart_lane"])}" '
            f'departSpeed="{r.get("depart_speed", traffic["depart_speed"])}"/>')

    with open(os.path.join(out_dir, "highway.rou.xml"), "w") as f:
        f.write(f"""<routes>
    <vType id="ego_type" accel="{ego['accel']}" decel="{ego['decel']}" maxSpeed="{ego['max_speed']}" speedFactor="1" color="1,0,0" vClass="passenger" guiShape="passenger/sedan"/>
{vtypes_block}
{chr(10).join(route_lines)}
{chr(10).join(flow_lines)}
</routes>
""")

    # ── 4) 주변 지형 폴리곤 (순수 시각 요소) ──
    scenery = os.path.join(out_dir, "highway.scenery.xml")
    ctx = road.get("context_osm_file")
    if ctx and SCENERY.get("osm_polygons", True):
        typemap = os.path.join(os.environ.get("SUMO_HOME", ""),
                               "data", "typemap", "osmPolyconvert.typ.xml")
        subprocess.run(
            [checkBinary("polyconvert"), "--net-file", net_path,
             "--osm-files", _resolve(ctx), "--type-file", typemap,
             "-o", scenery, "--no-warnings"],
            check=True, capture_output=True)
    else:
        with open(scenery, "w") as f:
            f.write("<additional/>\n")

    # ── 5) GUI 시작 화면: 지정한 관심 지점(합류부 등)을 확대 ──
    #   SUMO zoom(%)은 "네트워크 전체 폭 = 100%" 기준
    (xmin, ymin), (xmax, ymax) = net.getBBoxXY()
    view_width = float(SIMULATION.get("gui_view_width", 500.0))
    zoom = (xmax - xmin) / view_width * 100.0
    if road.get("gui_focus_edge"):
        shape = net.getEdge(road["gui_focus_edge"]).getShape()
        cx, cy = shape[len(shape) // 2]
    else:
        cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    with open(os.path.join(out_dir, "highway.gui.xml"), "w") as f:
        f.write(f"""<viewsettings>
    <scheme name="real world"/>
    <viewport zoom="{zoom:.0f}" x="{cx:.1f}" y="{cy:.1f}" angle="0"/>
    <delay value="{float(SIMULATION.get('gui_delay', 100.0))}"/>
</viewsettings>
""")

    # 주변 지형(highway.scenery.xml)은 sumocfg에 넣지 않는다 — 학습(headless)마다
    # 1MB가 넘는 폴리곤을 읽지 않도록, GUI를 띄울 때만 추가로 불러온다
    # (sumo_env / view_road.py가 --additional-files로 지정).
    cfg_path = os.path.join(out_dir, "highway.sumocfg")
    with open(cfg_path, "w") as f:
        f.write("""<configuration>
    <input>
        <net-file value="highway.net.xml"/>
        <route-files value="highway.rou.xml"/>
    </input>
    <gui_only>
        <gui-settings-file value="highway.gui.xml"/>
    </gui_only>
</configuration>
""")
    return cfg_path
