"""Project visible ego sensor tracks onto local navigation-map geometry."""

from math import hypot

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
        for start, length, a, tangent in self.segments:
            if start <= position <= start + length:
                return offset(a, tangent, position - start)
        return None


def _shape(lane):
    return tuple(lane.getShape())


def _connection_shape(connection, net):
    via = connection.getViaLaneID()
    return _shape(net.getLane(via)) if via else ()


class ToFObservation:
    def __init__(self, net, visibility, nominal_spacing, junction_range):
        self.net = net
        self.window = visibility
        self.spacing = nominal_spacing
        self.junction_range = junction_range
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

    def lanes(self, frame, lane_id, offsets, ego_length, ego_speed):
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
        for track in frame.tracks.values():
            possible = []
            for side, (path, ref, width) in windows.items():
                position = path.project(track.center, track.direction)
                if position is None:
                    continue
                along, lateral = position
                delta = along - ref
                if lateral <= width / 2 and abs(delta) <= self.window:
                    possible.append((lateral, abs(side), side, delta))
            if possible:
                _, _, side, delta = min(possible)
                gap = max(0.0, abs(delta) - (ego_length + track.length) / 2)
                speed = ego_speed if track.speed is None else track.speed
                hits[side].append((delta, gap, speed))

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
