"""Project visible ego sensor tracks onto local navigation-map geometry."""

import os
from dataclasses import dataclass
from math import hypot, isfinite

from .tof_perception import offset


YIELD_CONNECTION_STATES = {"m", "=", "s", "w", "Z"}


class Path:
    def __init__(self, points):
        self.segments = []
        self.length = 0.0
        for a, b in zip(points, points[1:]):
            length = hypot(b[0] - a[0], b[1] - a[1])
            if length:
                tangent = ((b[0] - a[0]) / length, (b[1] - a[1]) / length)
                self.segments.append((self.length, length, a, tangent))
                self.length += length

    def project(self, point, direction=None):
        """Return distance along and perpendicular to the nearest aligned segment."""
        result = None
        for start, length, a, tangent in self.segments:
            tx, ty = tangent
            if direction is not None and direction[0] * tx + direction[1] * ty < 0.5:
                continue
            dx, dy = point[0] - a[0], point[1] - a[1]
            local = max(0.0, min(length, dx * tx + dy * ty))
            error = hypot(dx - local * tx, dy - local * ty)
            if result is None or error < result[1]:
                result = (start + local, error)
        return result

    def point_at(self, position):
        pose = self.pose_at(position)
        return pose[0] if pose is not None else None

    def pose_at(self, position):
        for start, length, a, tangent in self.segments:
            if start <= position <= start + length:
                return offset(a, tangent, position - start), tangent
        return None


@dataclass(frozen=True)
class _LastLead:
    track_id: str
    observed_at: float
    path: Path
    position: float
    length: float
    speed: float


def _shape(lane):
    return tuple(lane.getShape())


def _connection_shape(connection, net):
    via = connection.getViaLaneID()
    return _shape(net.getLane(via)) if via else ()


class ToFObservation:
    def __init__(self, net, visibility, nominal_spacing, junction_range, *,
                 lead_hold_s=0.0, lead_gap_window=False, keep_inside=False):
        if not isfinite(lead_hold_s) or lead_hold_s < 0.0:
            raise ValueError("ToF lead_hold_s must be finite and non-negative")
        # (팀14, 11/26) keep_inside: 양보 교차로 안(내부 차선)에 들어간 뒤에도 교차로 관측을 유지
        #   [거리 0, 양보 의무 +1, 교차 차량(ToF)]. 기존에는 내부 차선에서 [1, −1, −1](교차로 없음)이라
        #   건너는 중에 가속해 신협오거리에서 충돌했음. 새 정보 없이 같은 세 칸을 끊기지 않게 함.
        self.keep_inside = keep_inside
        self._yield_connection = None
        self.net = net
        self.window = visibility
        self.spacing = nominal_spacing
        self.junction_range = junction_range
        self.lead_hold_s = lead_hold_s
        self.lead_gap_window = lead_gap_window
        self._last_lead = None
        self.lane_paths = {}
        self.foe_paths = {}
        self.signal_points = {
            (tls.getID(), link): _shape(lane)[-1]
            for tls in net.getTrafficLights()
            for lane, _, link in tls.getConnections()
        }

    def _lane_path(self, lane):
        lane_id = lane.getID()
        if lane_id not in self.lane_paths:
            center = _shape(lane)
            incoming = [c for c in lane.getIncomingConnections()
                        if not c.getFromLane().getID().startswith(":")]
            outgoing = lane.getOutgoing()
            before = ()
            after = ()
            if incoming:
                conn = min(incoming, key=lambda c: c.getDirection() != "s")
                before = _shape(conn.getFromLane()) + _connection_shape(conn, self.net)
            if outgoing:
                conn = min(outgoing, key=lambda c: c.getDirection() != "s")
                after = _connection_shape(conn, self.net) + _shape(conn.getToLane())
            path = Path(before + center + after)
            prefix = Path(before + center[:1]).length
            self.lane_paths[lane_id] = (path, Path(center), prefix)
        return self.lane_paths[lane_id]

    def _density(self, path, ref, count, sign, frame):
        length = min(self.window, path.length - ref if sign > 0 else ref)
        if length <= 0:
            return -1.0
        if count:
            return min(1.0, count * self.spacing / length)
        samples = (path.point_at(ref + sign * length * fraction)
                   for fraction in (0.2, 0.5, 0.8))
        return 0.0 if all(p is not None and frame.visible(p) for p in samples) else -1.0

    def reset_lead_history(self):
        self._last_lead = None

    def _estimate_lead(self, frame, window, ego_length, now):
        previous = self._last_lead
        if previous is None:
            return None
        # Retire the estimate if the target is now measured outside the current lane.
        age = now - previous.observed_at
        if not 0.0 < age <= self.lead_hold_s or previous.track_id in frame.tracks:
            self.reset_lead_history()
            return None

        path, ref, width = window
        pose = previous.path.pose_at(previous.position + previous.speed * age)
        projection = path.project(*pose) if pose is not None else None
        if projection is not None:
            along, lateral = projection
            delta = along - ref
            gap = max(0.0, delta - (ego_length + previous.length) / 2)
            range_distance = gap if self.lead_gap_window else delta
            # A clear line of sight without a fresh return invalidates the estimate.
            if (lateral <= width / 2 and delta > 0.0 and range_distance <= self.window
                    and not frame.visible(pose[0])):
                return gap, previous.speed

        self.reset_lead_history()
        return None

    def lanes(self, frame, lane_id, offsets, ego_length, ego_speed, *, now=None):
        lane = self.net.getLane(lane_id)
        edge_lanes = lane.getEdge().getLanes()
        windows = {}
        for side in offsets:
            idx = lane.getIndex() + side
            if 0 <= idx < len(edge_lanes):
                target = edge_lanes[idx]
                path, central, prefix = self._lane_path(target)
                origin = central.project(frame.center)
                if origin is not None:
                    windows[side] = (path, prefix + origin[0], target.getWidth())

        hits = {side: [] for side in windows}
        remember_lead = self.lead_hold_s > 0.0 and now is not None
        select_lead = remember_lead or self.lead_gap_window
        current_lead = None
        for track_id, track in frame.tracks.items():
            possible = []
            extended_delta = None
            half_lengths = (ego_length + track.length) / 2
            for side, (path, ref, width) in windows.items():
                position = path.project(track.center, track.direction)
                if position is None:
                    continue
                along, lateral = position
                delta = along - ref
                if lateral > width / 2:
                    continue
                if abs(delta) <= self.window:
                    possible.append((lateral, abs(side), side, delta))
                elif self.lead_gap_window and side == 0 and 0.0 < delta <= self.window + half_lengths:
                    extended_delta = delta
            if possible:
                _, _, side, delta = min(possible)
            elif extended_delta is not None:
                # Use unassigned tracks at the edge of the window only for the ego-lane lead.
                side, delta = 0, extended_delta
            else:
                continue
            gap = max(0.0, abs(delta) - half_lengths)
            speed = ego_speed if track.speed is None else track.speed
            if possible:
                hits[side].append((delta, gap, speed))
            if select_lead and side == 0 and delta > 0.0:
                reading = gap, speed
                if current_lead is None or reading < current_lead[0]:
                    path, ref, _ = windows[0]
                    current_lead = reading, track_id, track, path, ref + delta

        neighbors, front_density, rear_density = {}, {}, {}
        for side in offsets:
            if side not in windows:
                neighbors[side] = (None, None)
                front_density[side], rear_density[side] = 1.0, -1.0
                continue
            path, ref, _ = windows[side]
            front = [(gap, speed) for delta, gap, speed in hits[side] if delta > 0]
            rear = [(gap, speed) for delta, gap, speed in hits[side] if delta <= 0]
            neighbors[side] = (min(front, default=None), min(rear, default=None))
            front_density[side] = self._density(path, ref, len(front), 1, frame)
            rear_density[side] = self._density(path, ref, len(rear), -1, frame)

        if current_lead is not None:
            reading, track_id, track, path, position = current_lead
            if self.lead_gap_window:
                neighbors[0] = reading, neighbors[0][1]
            if remember_lead:
                self._last_lead = None if track.speed is None else _LastLead(
                    track_id, now, path, position, track.length, track.speed,
                )
        elif remember_lead and 0 in windows:
            estimate = self._estimate_lead(frame, windows[0], ego_length, now)
            if estimate is not None:
                # Only fill the PPO lead slots; density uses current measurements.
                neighbors[0] = estimate, neighbors[0][1]
        return neighbors, front_density, rear_density

    def _upstream_shapes(self, lane, need, depth=0):
        """lane으로 들어오는 차로들의 모양을 need m만큼 거슬러 올라가며 이어 붙인 목록 (갈라지면 갈래마다 하나)."""
        if need <= 0.0 or depth >= 8:
            return [()]
        out = []
        for incoming in lane.getIncomingConnections():
            source = incoming.getFromLane()
            if source.getID().startswith(":"):
                continue
            via = _connection_shape(incoming, self.net)
            via_length = Path(via).length if via else 0.0
            segment = _shape(source) + via
            for prefix in self._upstream_shapes(source, need - source.getLength() - via_length, depth + 1):
                out.append(prefix + segment)
        return out or [()]

    def _conflicting_approaches(self, connection):
        if connection in self.foe_paths:
            return self.foe_paths[connection]
        junction = connection.getJunction()
        index = junction.getLinkIndex(connection)
        paths = []
        if index >= 0 and junction.hasFoes():
            for other in junction.getConnections():
                other_index = junction.getLinkIndex(other)
                if other == connection or other_index < 0 or not junction.areFoes(index, other_index):
                    continue
                lane = other.getFromLane()
                if lane.getID().startswith(":"):
                    continue
                shape = _shape(lane)
                # (팀14, 11/26) TEAM14_FOE_UPSTREAM_M=m > 0: 교차 진입로 차로가 m보다 짧으면 그 차로로 들어오는
                #   앞쪽 차로(내부 차로 포함)를 거슬러 올라가 합친 길이가 m가 될 때까지 이어 붙인다 (기본 0 꺼짐).
                #   의왕역 회전교차로 진입부는 진입로 차로가 1.4 m라 안에서 도는 차가 판단에서 빠졌음.
                upstream_m = float(os.environ.get("TEAM14_FOE_UPSTREAM_M", "0") or 0)
                prefixes = (self._upstream_shapes(lane, upstream_m - lane.getLength())
                            if upstream_m > lane.getLength() else [()])
                for prefix in prefixes:
                    approach = Path(prefix + shape)
                    path = Path(prefix + shape + _connection_shape(other, self.net))
                    paths.append((path, approach.length, lane.getWidth() / 2))
        self.foe_paths[connection] = paths
        return paths

    def junction(self, frame, lane_id, next_edge_id, signals, route_after=(), skip_short_m=0.0):
        # Distance and phase are a line-of-sight gated RGB signal proxy.
        # Preserve the pretrained policy's encoding when no signal is upcoming.
        # (팀14, 11/26) 관측 D용: 이번 스텝에 ToF로 보이는 교차 차량 중 가장 가까운 것 (중심 거리 m, 그 차 길이 m). 없으면 None.
        self.cross_gap = None
        signal = [1.0, 0.0, -1.0] if signals else [1.0, 1.0, 1.0]
        if signals:
            tls, link, distance, state = signals[0]
            point = self.signal_points.get((tls, link))
            if distance <= self.junction_range and point is not None and frame.visible(point, front_only=True):
                color = 1.0 if state in "Gg" else -1.0 if state in "Rr" else 0.0
                signal = [distance / self.junction_range, color, -1.0]

        # Static right-of-way and possible conflict approaches come from the map.
        # No simulator vehicle routes, hasFoe flag, or invisible track states enter PPO.
        lane = self.net.getLane(lane_id)
        if lane_id.startswith(":") or next_edge_id is None:
            inside = self._inside_yield(lane_id)
            if inside is not None:
                self.cross_gap = self._nearest_crossing(frame, inside)
                return signal + [0.0, 1.0, self._foe_state(frame, inside)]
            return signal + [1.0, -1.0, -1.0]
        self._yield_connection = None
        path = Path(_shape(lane))
        reference = path.project(frame.center)
        if reference is None:
            return signal + [1.0, -1.0, -1.0]
        distance = path.length - reference[0]
        connection = next((c for c in lane.getOutgoing() if c.getTo().getID() == next_edge_id), None)
        if (skip_short_m > 0.0 and connection is not None and route_after
                and (connection.getTLSID() or connection.getState() not in YIELD_CONNECTION_STATES)):
            # (팀14, 11/26) 짧은 도로 너머의 교차로도 보기 (TEAM14_JUNCTION_SKIP_SHORT_M): 현재 차로 끝 교차로
            #   (예: 신호)에 양보할 게 없고 바로 다음 도로가 skip_short_m 이하로 짧으면, 그 너머 교차로(예: 신호
            #   10 m 뒤 의왕역 회전교차로 진입)를 대신 관측한다. 지도 정보(차로 연결·우선순위)만 쓰고, 교차 차량은
            #   아래와 같이 ToF로 본다. 경로에서 바뀌는 곳: 0.73 km, 0.77 km(회전교차로), 12.37 km.
            nxt = connection.getToLane()
            if nxt is not None and nxt.getLength() <= skip_short_m:
                via = connection.getViaLaneID()
                ahead = distance + (self.net.getLane(via).getLength() if via else 0.0) + nxt.getLength()
                beyond = next((c for c in nxt.getOutgoing() if c.getTo().getID() == route_after[0]), None)
                if beyond is None:
                    beyond = next((c for l in nxt.getEdge().getLanes() for c in l.getOutgoing()
                                   if c.getTo().getID() == route_after[0]), None)
                if (beyond is not None and not beyond.getTLSID()
                        and beyond.getState() in YIELD_CONNECTION_STATES and ahead <= self.junction_range):
                    connection, distance = beyond, ahead
        if (distance > self.junction_range or connection is None or connection.getTLSID()
                or connection.getState() not in YIELD_CONNECTION_STATES):
            return signal + [1.0, -1.0, -1.0]
        if self.keep_inside:
            self._yield_connection = connection
        self.cross_gap = self._nearest_crossing(frame, connection)
        return signal + [distance / self.junction_range, 1.0, self._foe_state(frame, connection)]

    def _inside_yield(self, lane_id):
        """(팀14) 지금 내부 차선이 바로 전에 다가가던 양보 교차로 안이면 그 연결을 돌려준다."""
        if not (self.keep_inside and self._yield_connection is not None and lane_id.startswith(":")):
            return None
        node = self._yield_connection.getJunction().getID()
        return self._yield_connection if lane_id.startswith(f":{node}_") else None

    def _nearest_crossing(self, frame, connection):
        """내 길과 충돌하는 진입로·교차로 안 경로 위에 있고 ToF로 보이는 차 중 ego 중심에서 가장 가까운 것.
        (중심 사이 거리, 그 차 길이)를 돌려준다. 보상(TEAM14_CROSS_GAP_W)에서만 쓰고 관측 벡터에는 넣지 않는다."""
        best = None
        for other, _stop, width in self._conflicting_approaches(connection):
            for track in frame.tracks.values():
                result = other.project(track.center, track.direction)
                if result is None or result[1] > width:
                    continue
                gap = hypot(track.center[0] - frame.center[0], track.center[1] - frame.center[1])
                if best is None or gap < best[0]:
                    best = (gap, track.length)
        return best

    def _foe_state(self, frame, connection):
        """교차 진입로에서 ToF로 보이는 차가 다가오면 +1, 진입로가 다 보이고 비었으면 −1, 가려서 모르면 0.
        진입로 경로는 교차로 안 구간까지 이어져 있어, 이미 교차로에 들어선 차도 잡힌다."""
        paths = self._conflicting_approaches(connection)
        clear = bool(paths)
        for other, stop, width in paths:
            for track in frame.tracks.values():
                result = other.project(track.center, track.direction)
                if result is None:
                    continue
                position, lateral = result
                if lateral <= width and stop - position <= max(8.0, 4.0 * (track.speed or 0.0)):
                    return 1.0
            for back in (1.0, 10.0, 20.0, 30.0, 40.0):
                point = other.point_at(max(0.0, stop - back))
                clear = clear and point is not None and frame.visible(point)
        return -1.0 if clear else 0.0
