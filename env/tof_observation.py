"""Project visible ego sensor tracks onto local navigation-map geometry."""

from dataclasses import dataclass
from math import hypot, isfinite

from .tof_perception import offset


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
                 lead_hold_s=0.0, lead_gap_window=False):
        if not isfinite(lead_hold_s) or lead_hold_s < 0.0:
            raise ValueError("ToF lead_hold_s must be finite and non-negative")
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
                approach = Path(shape)
                path = Path(shape + _connection_shape(other, self.net))
                paths.append((path, approach.length, lane.getWidth() / 2))
        self.foe_paths[connection] = paths
        return paths

    def junction(self, frame, lane_id, next_edge_id, signals):
        # Distance and phase are a line-of-sight gated RGB signal proxy.
        # Preserve the pretrained policy's encoding when no signal is upcoming.
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
            return signal + [1.0, -1.0, -1.0]
        path = Path(_shape(lane))
        reference = path.project(frame.center)
        if reference is None:
            return signal + [1.0, -1.0, -1.0]
        distance = path.length - reference[0]
        connection = next((c for c in lane.getOutgoing() if c.getTo().getID() == next_edge_id), None)
        if (distance > self.junction_range or connection is None or connection.getTLSID()
                or connection.getState() not in {"m", "=", "s", "w", "Z"}):
            return signal + [1.0, -1.0, -1.0]
        paths = self._conflicting_approaches(connection)
        clear = bool(paths)
        for other, stop, width in paths:
            for track in frame.tracks.values():
                result = other.project(track.center, track.direction)
                if result is None:
                    continue
                position, lateral = result
                if lateral <= width and stop - position <= max(8.0, 4.0 * (track.speed or 0.0)):
                    return signal + [distance / self.junction_range, 1.0, 1.0]
            for back in (1.0, 10.0, 20.0, 30.0, 40.0):
                point = other.point_at(max(0.0, stop - back))
                clear = clear and point is not None and frame.visible(point)
        return signal + [distance / self.junction_range, 1.0, -1.0 if clear else 0.0]
