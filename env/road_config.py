"""도로 / 차량 / 배경 교통류 설정 파일.

이 파일의 값을 수정한 뒤 train.py를 다시 실행하면
road_builder.py가 SUMO 도로 파일(.net.xml 등)을 자동으로 다시 만들어준다.
즉, 도로를 바꾸고 싶으면 이 파일만 고치면 된다.

단위 참고:
    - 거리: m (미터)
    - 속도: m/s  (참고: 33.33 m/s ≈ 120 km/h,  27 m/s ≈ 97 km/h)
"""

# ──────────────────────────────────────────────────────────────
# 1) 도로 형상
#    현재는 "직선 편도 도로" 하나만 생성한다.
#    (교차로, 합류부 등 복잡한 도로는 road_builder.py를 확장해야 함)
# ──────────────────────────────────────────────────────────────
# ★ 팀14 프로젝트 도로: 영동고속도로 북수원IC 일대 (강릉 방향)
#   - 원본: OpenStreetMap (© OpenStreetMap contributors, ODbL)
#           env/osm/yeongdong_bukwon_motorway.osm  (고속도로 본선 + 램프)
#           env/osm/yeongdong_bukwon_context.osm   (건물/녹지/하천 — 시각 요소)
#   - ego 경로(강릉 방향 본선, 약 5.6 km)에서 만나는 구조:
#       3차로 본선(80 km/h) → 북수원IC 진출 감속차로 → 북수원IC 진입 2차로 합류
#       → 5차로 → 차로 감소(5→4→3) → 차로 추가(3→4) → 분기 후 본선 3차로(100 km/h)
#   - 반대(인천) 방향과 램프에도 배경 교통이 흐른다 (TRAFFIC["routes"]).
#   직선 도로로 되돌리려면 "type": "straight"로 바꾸고 length/num_lanes/
#   speed_limit을 지정하면 된다 (예전 수업 실습 환경).
ROAD = {
    "type": "osm",
    "name": "영동고속도로 북수원IC (강릉방향)",
    "osm_file": "env/osm/yeongdong_bukwon_motorway.osm",
    "context_osm_file": "env/osm/yeongdong_bukwon_context.osm",
    # ego가 달릴 경로: (출발 edge, 도착 edge). 사이 경로는 자동 계산.
    #   edge id = OSM way id (netconvert가 그대로 사용)
    "ego_route": ("474882669", "50981265"),
    "gui_focus_edge": "206488360",   # GUI 시작 화면 중심 (합류 후 5차로 구간)
    # OSM 변환 직후 순서대로 적용하는 도로망 패치 (env/patches/ 파일 안 설명 참고)
    #   북수원 영업소: OSM에는 1차로 평행 도로 2개뿐 → 실제 운영 차로(입구 5·출구 5)와
    #   하이패스/현금/화물차 차로 구분, 영업소 앞뒤 램프 2차로를 반영한다.
    #   빈 리스트로 두면 예전(OSM 그대로) 도로망.
    "net_patches": [
        {"edg": "env/patches/bukwon_toll_1_shape.edg.xml",
         "con": "env/patches/bukwon_toll_1_shape.con.xml"},
        {"nod": "env/patches/bukwon_toll_2_lanes.nod.xml",
         "edg": "env/patches/bukwon_toll_2_lanes.edg.xml",
         "con": "env/patches/bukwon_toll_2_lanes.con.xml"},
    ],
    "speed_limit": 27.78,  # 관측/보상 정규화 기준 vmax (= 구간 최고 제한속도 100 km/h).
                           # 실제 주행 상한은 구간별 제한속도(80/100 km/h)를 따른다.
    # 아래 두 값은 build()가 ego 경로에서 계산해 채운다.
    "length": None,
    "num_lanes": None,
}

# ──────────────────────────────────────────────────────────────
# 2) ego 차량 (RL 에이전트가 조종하는 빨간 차)
#    accel/decel은 SUMO 물리엔진이 허용하는 "한계치"이고,
#    실제 한 스텝에 얼마나 가감속할지는 mdp_config.py의
#    SPEED_DELTAS(행동 정의)가 결정한다.
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────
# 도로변 장식 (순수 시각 요소 — 시뮬레이션 물리/학습에 영향 없음)
# GUI에서 도로가 허허벌판에 떠 있는 느낌을 줄이고,
# ego 추적 화면에서 "지나가는 배경"이 생겨 속도감이 보인다.
# ──────────────────────────────────────────────────────
SCENERY = {
    "osm_polygons": True,   # (OSM 도로) 주변 건물/녹지/하천 폴리곤 표시
    "trees": True,          # (직선 도로) 나무 심기 on/off          # 나무 심기 on/off
    "tree_spacing": 45.0,   # 같은 쪽 나무 사이 평균 간격 (m)
    "tree_jitter": 0.5,     # 간격/위치의 무작위 흔들림 비율
    "side_offset": 6.0,     # 도로 가장자리에서 나무까지 거리 (m)
    "seed": 7,              # 배치 난수 시드 (매번 같은 숲)
}

EGO = {
    "accel": 5.4,          # 최대 가속도 (m/s^2)  → 행동 a=+1 일 때
    "decel": 5.4,          # 최대 감속도 (m/s^2)  → 행동 a=-1 일 때
    "max_speed": 33.33,    # 차량 자체의 최고속도
    "depart_lane": "random", # 시작 차선. "random"이면 시작 edge의 아무 차선 (팀14: 다양한 상황 학습)
                           # "center"면 중앙 차선(차선수//2)에서
                           # 자동 시작 — 차선 수를 바꿔도 항상 가운데.
    "depart_speed": 10,    # 시작 속도 (m/s)
}

# ──────────────────────────────────────────────────────────────
# 3) 배경 교통류 (SUMO가 알아서 운전하는 일반 차량들)
#    ego보다 느리게 설정해서 "느린 앞차를 만나면 감속해야 하는"
#    상황이 자연스럽게 만들어지도록 했다.
# ──────────────────────────────────────────────────────────────
TRAFFIC = {
    # ══════════════════════════════════════════════════════
    # ★ 실제 고속도로 교통류 시나리오 (팀14)
    #
    # 배경차의 희망속도 = 구간 제한속도 × speedFactor 분포.
    # (80 km/h 구간과 100 km/h 구간에서 각각 자연스러운 속도로 달림)
    # 컨트롤러마다 speedFactor 평균을 달리 줘서 차선 간 속도차를 만든다.
    #
    # 합류/분기 도로에서는 배경차가 경로를 따라가려면 차선변경이 필수이므로
    # keep_lane=False + lc 파라미터로 SUMO 차선변경 모델(LC2013)을 켠다.
    #   lcStrategic  : 경로상 필요한 차선으로 미리 이동하는 적극성
    #   lcCooperative: 합류 차량에게 양보(차선 비켜주기/감속)하는 정도
    #   lcSpeedGain  : 더 빠른 차선으로 옮기려는 성향
    #   lcKeepRight  : 우측 차로 유지 성향
    # ══════════════════════════════════════════════════════
    "max_speed": 36.0,        # 차량 자체 상한 (실제 희망속도는 speed_factor가 결정)
    "depart_lane": "best",    # SUMO가 경로에 맞는 차선을 골라 투입
    "depart_speed": "max",    # 투입 즉시 주변 흐름 속도로 진입

    # ── 경로별 교통 수요 (대/시간) ──
    #   from / to : 출발·도착 edge (= OSM way id), 경로는 자동 계산
    #   ego는 여기에 포함되지 않는다 (환경이 r0 경로로 직접 투입)
    #
    #   ★ 실측 보정 (평일 아침 첨두 근사). 근거:
    #     - 북수원 영업소(코드 212) 진입 07시 2,252대/h, 진출 07시 883대/h
    #       (한국도로공사 영업소별 교통량, 2026-11-05 목)
    #     - 진입 차량 방향: 강릉 68% / 인천 31%, 진출 차량 출발: 강릉쪽에서 21% / 인천쪽에서 78%
    #       (도로공사 영업소간 교통량, 2026-11-05) → 강릉행 중 동수원 방면 24%
    #     - 본선: VDS 0500VDE02700(32.6 km, IC 하류) 최대 3,167대/h,
    #       0500VDS02700(31.9 km) 최대 4,256대/h (2026-11-08 일요일 — 평일 자료로 다시 확인 필요)
    #     - 부곡~북수원(27.5~30.8 km) 검지기는 무자료라 상류 본선은 하류 값에서 역산
    #     - 영업소로 들어오는 진입로 2개(582107260, 51066899)의 비율은 자료가 없어 반반 가정
    #       (예전 설정처럼 강릉행 전부를 한 진입로에 넣으면 1차로 진입로가 막힌다)
    #   예전 값(가정): 직진 1500, 진출 350, 북수원 진출 250, 합류 450+100, 인천 900+700+200, 350
    "routes": {
        # 강릉 방향 (ego와 같은 방향)
        "east_through":   {"from": "474882669", "to": "50981265",   "vehs_per_hour": 1450},
        "east_to_exit":   {"from": "474882669", "to": "549032648",  "vehs_per_hour": 220},
        "east_to_bukwon": {"from": "474882669", "to": "51066895",   "vehs_per_hour": 185},
        # 북수원 진입 → 강릉 방향 1,530 (본선 직진 1,160 + 동수원 방면 370), 진입로 2개에 반씩
        "bukwon_to_east":        {"from": "582107260", "to": "50981265",  "vehs_per_hour": 580},
        "bukwon_to_east_b":      {"from": "51066899",  "to": "50981265",  "vehs_per_hour": 580},
        "bukwon_to_east_exit":   {"from": "582107260", "to": "549032648", "vehs_per_hour": 185},
        "bukwon_to_east_exit_b": {"from": "51066899",  "to": "549032648", "vehs_per_hour": 185},
        # 인천 방향 (반대 차로 — 시각적 현실감 + 램프 상호작용)
        "west_through_a": {"from": "50981258",  "to": "41948037",   "vehs_per_hour": 1900},
        "west_through_b": {"from": "50981259",  "to": "41948037",   "vehs_per_hour": 1666},
        "west_to_bukwon": {"from": "50981258",  "to": "1235185551", "vehs_per_hour": 690},
        # 북수원 진입 → 인천 방향 700, 진입로 2개에 반씩
        "bukwon_to_west":   {"from": "51066899",  "to": "41948037", "vehs_per_hour": 350},
        "bukwon_to_west_b": {"from": "582107260", "to": "41948037", "vehs_per_hour": 350},
    },

    # ── 에피소드 시작 전 교통류 생성(warm-up) ──
    # 직선 도로의 "프리필" 대신, 실제 도로에서는 SUMO를 일정 시간 미리
    # 돌려서 모든 경로(램프 포함)에 자연스러운 교통류가 형성된 상태에서
    # ego를 투입한다. 매 에피소드 [min, max] 초 사이에서 무작위로 골라
    # 시작 시점의 교통 상황을 다양화한다.
    "warmup_seconds": (240, 330),
    # 학습 속도용: 한 번 띄운 시뮬레이션을 이 에피소드 수만큼 재사용한다
    # (이전 ego만 제거 → reuse_gap_seconds 초 흘림 → 새 ego 투입).
    # 0이면 매 에피소드 재시작. GUI 모드에서는 항상 재시작.
    "reuse_episodes": 50,
    "reuse_gap_seconds": (5, 20),

    # ──────────────────────────────────────────────────────
    # 배경차 컨트롤러(차량추종모델) 믹스 — Krauss / IDM / EIDM / ACC
    # (SUMO vTypeDistribution, road_builder.py가 생성)
    #   speed_factor: "normc(평균,표준편차,하한,상한)" — 제한속도 대비 희망속도
    # ──────────────────────────────────────────────────────
    "controllers": {
        "krauss": {   # 산만한 인간 운전자 — 가장 느리고 들쑥날쑥
            "probability": 0.35,
            "carFollowModel": "Krauss",
            "accel": 2.0, "decel": 4.5,
            "tau": 1.0, "min_gap": 2.5,
            "sigma": 0.3,
            "speed_factor": "normc(0.85,0.08,0.65,1.05)",
            "color": "1,1,0",    # 노랑
            "keep_lane": False,
            "lc": {"lcStrategic": 1.0, "lcCooperative": 0.8,
                   "lcSpeedGain": 0.6, "lcKeepRight": 0.5},
        },
        "idm": {      # 부드러운 표준 인간 모델
            "probability": 0.30,
            "carFollowModel": "IDM",
            "accel": 1.8, "decel": 3.5,
            "tau": 1.2, "min_gap": 2.0,
            "speed_factor": "normc(0.92,0.07,0.7,1.1)",
            "color": "0,1,1",    # 시안
            "keep_lane": False,
            "lc": {"lcStrategic": 1.0, "lcCooperative": 1.0,
                   "lcSpeedGain": 0.8, "lcKeepRight": 0.8},
        },
        "eidm": {     # 반응지연·부주의가 있는 현실적 인간
            "probability": 0.20,
            "carFollowModel": "EIDM",
            "accel": 2.0, "decel": 4.0,
            "tau": 1.1, "min_gap": 2.0,
            "speed_factor": "normc(0.95,0.08,0.7,1.15)",
            "color": "1,0.6,0",  # 주황
            "keep_lane": False,
            "lc": {"lcStrategic": 1.0, "lcCooperative": 0.7,
                   "lcSpeedGain": 1.0, "lcKeepRight": 0.3},
        },
        "acc": {      # 크루즈 차량 — 제한속도 근처를 일정하게
            "probability": 0.15,
            "carFollowModel": "ACC",
            "accel": 2.0, "decel": 4.0,
            "tau": 1.5, "min_gap": 2.0,
            "speed_factor": "normc(1.0,0.03,0.9,1.1)",
            "color": "1,0,1",    # 마젠타
            "keep_lane": False,
            "lc": {"lcStrategic": 1.0, "lcCooperative": 1.0,
                   "lcSpeedGain": 0.3, "lcKeepRight": 1.0},
        },
        # ── 영업소 이용 방식·차종 (실측 비율) ──
        # 북수원 영업소 2026-11-05: 하이패스 96.3% / TCS(현금) 3.7%,
        # 대형(2~5종) 8.6%. 위 4종 승용(합 1.0)에 아래를 더하고 자동 정규화하면
        # 현금 승용 ≈ 3.7%, 화물차 ≈ 8.5%가 된다.
        "tcs_car": {  # 현금 결제 승용차 — 영업소에서 TCS 부스만 쓸 수 있음
            "probability": 0.042,
            "carFollowModel": "Krauss",
            "accel": 2.0, "decel": 4.5,
            "tau": 1.0, "min_gap": 2.5,
            "sigma": 0.3,
            "speed_factor": "normc(0.88,0.08,0.7,1.05)",
            "color": "0.6,0.6,1",   # 연보라
            "v_class": "custom1",
            "keep_lane": False,
            "lc": {"lcStrategic": 1.0, "lcCooperative": 0.8,
                   "lcSpeedGain": 0.5, "lcKeepRight": 0.6},
        },
        "truck": {    # 화물차 — 영업소 입구는 화물차 전용 차로(축중)만 사용
            "probability": 0.097,
            "carFollowModel": "Krauss",
            "accel": 1.0, "decel": 4.0,
            "tau": 1.5, "min_gap": 3.0,
            "sigma": 0.2,
            "max_speed": 25.0,      # 화물차 고속도로 제한 90 km/h
            "speed_factor": "normc(0.9,0.05,0.75,1.0)",
            "length": 12.0,
            "color": "0.9,0.9,0.9", # 흰색
            "v_class": "truck",
            "gui_shape": "truck",
            "keep_lane": False,
            "lc": {"lcStrategic": 1.0, "lcCooperative": 0.6,
                   "lcSpeedGain": 0.2, "lcKeepRight": 1.0},
        },
    },

    # 직선 도로용 프리필 — OSM 도로에서는 warm-up이 대신하므로 끈다.
    "prefill": {"enabled": False},
}


# ══════════════════════════════════════════════════════════════════
# ★ 시나리오 선택 (팀14)
#   "bukwon" : 위의 영동고속도로 북수원IC 7.1 km (고속도로만)
#   "museum" : 팀원(김준희)이 만든 철도박물관 주차장 → 수원광교박물관 주차장 14.4 km
#              (신협오거리·의왕역회전교차로·부곡IC 진입·북수원 합류부·동수원IC 진출)
#   환경변수 TEAM14_SCENARIO로도 바꿀 수 있다 (예: set TEAM14_SCENARIO=bukwon)
# ══════════════════════════════════════════════════════════════════
import os as _os
SCENARIO = _os.environ.get("TEAM14_SCENARIO", "museum")

if SCENARIO == "museum":
    ROAD = {
        "type": "osm",
        "name": "철도박물관 → 수원광교박물관 (부곡IC·북수원IC·동수원IC)",
        # 팀원 지도(단톡 공유 ZIP Museum_Parking_to_Gwanggyo_V2)의 원본 OSM과 같은 변환 설정으로
        # 다시 만들되, 차로 수가 실제와 다른 길만 고친다 (osm_tag_overrides).
        # 원래 만들어진 도로망은 env/museum/museum_to_gwanggyo.net.xml (비교용)
        "osm_file": "env/museum/source/museum_corridor.osm",
        "netconvert_args": [
            "-t", "@env/museum/source/osmNetconvert_base.typ.xml,"
                  + "env/museum/source/service_types.typ.xml",
            "--geometry.remove", "true", "--ramps.guess", "false",
            "--ramps.set", "474882669#1",
            "--junctions.join", "false", "--no-turnarounds", "true",
            "--keep-edges.by-vclass", "passenger", "--osm.sidewalks", "false",
            "--osm.bike-access", "false", "--output.street-names", "true",
            "--output.original-names", "true",
            "--tls.yellow.time", "5", "--tls.allred.time", "1", "--no-warnings"],
        # 카카오 로드뷰로 확인한 차로 수 (방향별). 근거: 메인 세션 표 D:/자유대화/박물관경로_차선확인.md
        #   덕영대로 1 → 2 (37.33136,126.95649 2023-11 / 37.32513,126.95794 2026-06)
        #   철도박물관로 북쪽(회전교차로 → 오봉로) 1 → 2 (37.32468,126.94849 2023-11)
        #   창룡대로 2 → 4 (37.29597,127.04455 2026-08)
        "osm_tag_overrides": {
            **{w: {"lanes": "2"} for w in [
                "377720051", "491135704", "491135708", "1417143032", "51066581", "51066587",
                "472039936", "491135707", "494855746",
                "955971705", "955971706", "955971707", "955971708"]},          # 덕영대로 (일방 way)
            **{w: {"lanes": "2"} for w in ["488779086", "568664957", "496583277"]},  # 철도박물관로 북쪽 일방
            "488779084": {"lanes": "3", "lanes:forward": "1", "lanes:backward": "2"},  # 양방향 way, AV는 역방향
            "667354422": {"lanes": "4"},                       # 창룡대로 (OSM에 이미 60 km/h)
            # ── 제한속도 (안전속도 5030, 2021-04 시행) ──
            "155790360": {"maxspeed": "30"},   # 부곡초등길: 의왕부곡초 옆 어린이보호구역(로드뷰 빨간 노면)
            "667234604": {"maxspeed": "50"},   # 광교로: 로드뷰 2025-08 37.29564,127.04927 '50' 표지판 (OSM 60)
            "1500643091": {"maxspeed": "50"},  # 광교로
            # 창룡대로: OSM 일부 구간 60. 표지판은 로드뷰(2026-08)에서 못 찾음 → 같은 길 나머지도 60 가정
            **{w: {"lanes": "4", "maxspeed": "60"} for w in ["667354425", "621656305"]},  # 창룡대로 2→4차로
            "375714602": {"maxspeed": "60"},
        },
        # maxspeed가 없는 도시부 도로 기본값 (안전속도 5030): 일반도로 50, 이면·주거지 30.
        # 고속도로·램프(motorway*)와 국도급 primary(경수대로 등)는 건드리지 않음
        "osm_default_maxspeed": {
            "tertiary": "50", "tertiary_link": "50", "secondary": "50", "secondary_link": "50",
            "unclassified": "50", "residential": "30", "living_street": "30", "service": "30"},
        "context_osm_file": None,
        "ego_edges_file": "env/museum/route_check.json",       # 주황 경로(오봉로) 72개 edge
        # 갈림길 경로 선택: 의왕역회전교차로 → (주황) 오봉로 / (파랑) 부곡중앙로·덕영대로 → 다시 만남
        #   mode "fastest" = 출발 직전 예상 통행시간이 짧은 길 (계산 방식 A)
        #   disruption = 에피소드의 40%에서 한 길의 가운데 구간을 7 km/h로 (공사·사고 가정)
        "route_choice": {"file": "env/museum/route_alternatives.json",
                         "mode": "fastest",      # "learned" = 길 선택 AI (tools/train_route_policy.py)
                         "decision_edge": "496583281#0",  # 회전교차로 직전 21 m 구간에서 고름(learned)
                         "disruption": {"prob": 0.4, "speed": 2.0}},
        "gui_focus_edge": "206488360",
        "speed_limit": 27.78,
        "net_patches": [
            {"edg": "env/patches_museum/toll_1.edg.xml",
             "con": "env/patches_museum/toll_1.con.xml"},
            {"nod": "env/patches_museum/toll_2.nod.xml",
             "edg": "env/patches_museum/toll_2.edg.xml",
             "con": "env/patches_museum/toll_2.con.xml"},
            # 부곡(진입)·동수원(진출) 영업소 — AV 경로가 직접 지나는 요금소
            {"nod": "env/patches_museum/tolls_bd_1.nod.xml",
             "edg": "env/patches_museum/tolls_bd_1.edg.xml",
             "con": "env/patches_museum/tolls_bd_1.con.xml"},
            {"nod": "env/patches_museum/tolls_bd_2.nod.xml",
             "edg": "env/patches_museum/tolls_bd_2.edg.xml",
             "con": "env/patches_museum/tolls_bd_2.con.xml"},
        ],
        "length": None,
        "num_lanes": None,
    }
    # 고속도로 흐름은 북수원 시나리오의 실측 보정값을 이 지도의 edge 번호로 옮김.
    # 일반도로 흐름(신협오거리·회전교차로·부곡IC)은 팀원 설정값(가정, 실측 아님).
    _hw = {
        "east_through":          ("474882669#0", "50981265",  700),
        "east_to_bukwon":        ("474882669#0", "51066895",  185),
        "bukwon_to_east":        ("582107260",   "50981265",  580),
        "bukwon_to_east_b":      ("51066899",    "50981265",  580),
        "west_through_a":        ("50981263",    "41948037",  1900),
        "west_through_b":        ("206488703",   "41948037",  1666),
        "west_to_bukwon":        ("50981263",    "1235185551", 690),
        "bukwon_to_west":        ("51066899",    "41948037",  350),
        "bukwon_to_west_b":      ("582107260",   "41948037",  350),
        "five_north_south":      ("155809507#1", "472043938#7", 90),
        "five_east_northwest":   ("-155788504#0", "-40839116#1", 90),
        "five_south_east":       ("-472043938#7", "155788504#3", 90),
        "five_market_south":     ("461776049#5", "472043938#7", 60),
        "circle_north_east":     ("682100872#0", "452597718#1", 90),
        "circle_south_north":    ("496583281#0", "488779086#1", 90),
        "circle_east_south":     ("-496583283",  "462907008#1", 90),
        "bugok_to_citygoal":     ("51066582#0",  "667354422#1", 120),   # 667354425는 속도 보정 후 667354422#1로 합쳐짐
        # ── 부곡·동수원 영업소 (도로공사 2026-11-05, 영업소별·영업소간 교통량) ──
        # 동수원 진출 08시 3,478대/h: 인천 쪽(우리 진행 방향)에서 59% ≈ 2,050, 강릉 쪽에서 41% ≈ 1,430
        # 그대로 넣으면 북수원 합류 뒤 본선이 5,300대/h가 되어 VDS 실측(32.6 km 최대 3,167대/h, 일요일)과
        # 안 맞고 엇갈림 정체·순간이동이 생김(2026-11-09 시험) → 본선이 약 3,600대/h가 되게 줄임:
        #   본선 직진 1,450 → 700, 동수원행 상류 1,670 → 900, 강릉 쪽 동수원 진출 1,430 → 900(1차로 램프 용량)
        "east_to_dongsuwon":     ("474882669#0", "468241513", 900),
        "bukwon_to_dongsuwon":   ("582107260",   "468241513", 190),
        "bukwon_to_dongsuwon_b": ("51066899",    "468241513", 190),
        "west_to_dongsuwon":     ("27523870",    "50981089",  900),
        # 부곡 진입 07시 960대/h 중 강릉 방향 47% ≈ 450 (진입로 2개 반반 가정). 대형 19.5%는 미반영
        "bugok_to_east":         ("51066582#0",  "50981265",  225),
        "bugok_to_east_b":       ("491135706",   "50981265",  225),
    }
    TRAFFIC = {**TRAFFIC,
               "routes": {k: {"from": a, "to": b, "vehs_per_hour": v}
                          for k, (a, b, v) in _hw.items()}}
    EGO = {**EGO, "depart_speed": 0}   # 주차장 안에서 정지 상태로 출발
