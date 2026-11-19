"""Planar, ego-mounted ToF visibility and temporal vehicle tracking."""

from dataclasses import dataclass
from math import cos, floor, hypot, inf, radians, sin
import xml.etree.ElementTree as ET


def heading(angle):
    """SUMO navigational angle to an XY unit vector."""
    angle = radians(angle)
    return (sin(angle), cos(angle))


def offset(point, direction, distance):
    return (point[0] + direction[0] * distance, point[1] + direction[1] * distance)


def _intersects(origin, target, wall):
    x, y = origin
    dx, dy = target[0] - x, target[1] - y
    ax, ay, bx, by = wall
    sx, sy = bx - ax, by - ay
    divisor = dx * sy - dy * sx
    if abs(divisor) < 1e-9:
        return False
    ray = ((ax - x) * sy - (ay - y) * sx) / divisor
    segment = ((ax - x) * dy - (ay - y) * dx) / divisor
    return 1e-6 < ray < 1.0 - 1e-6 and 0.0 <= segment <= 1.0


def _walls(points):
    return tuple((*a, *b) for a, b in zip(points, (*points[1:], points[0])) if a != b)


_CELL_SIZE = 25


def _box_cells(start, end):
    for x in range(floor(min(start[0], end[0]) / _CELL_SIZE),
                   floor(max(start[0], end[0]) / _CELL_SIZE) + 1):
        for y in range(floor(min(start[1], end[1]) / _CELL_SIZE),
                       floor(max(start[1], end[1]) / _CELL_SIZE) + 1):
            yield x, y


def _ray_cells(start, end):
    """Walk the grid cells touched by a ray, including corner contacts."""
    x, y = (floor(coord / _CELL_SIZE) for coord in start)
    end_x, end_y = (floor(coord / _CELL_SIZE) for coord in end)
    dx, dy = end[0] - start[0], end[1] - start[1]
    step_x = 1 if dx > 0 else -1
    step_y = 1 if dy > 0 else -1
    yield x, y
    while (x, y) != (end_x, end_y):
        tx = (((x + (step_x > 0)) * _CELL_SIZE - start[0]) / dx
              if x != end_x else inf)
        ty = (((y + (step_y > 0)) * _CELL_SIZE - start[1]) / dy
              if y != end_y else inf)
        if abs(tx - ty) <= 1e-12:
            yield x + step_x, y
            yield x, y + step_y
            x += step_x
            y += step_y
        elif tx < ty:
            x += step_x
        else:
            y += step_y
        yield x, y


class BuildingOccluders:
    """Solid planar OSM building footprints, indexed in 25 m cells."""

    def __init__(self, filename):
        self.cells = {}
        if filename is None:
            return
        for polygon in ET.parse(filename).getroot().iter("poly"):
            points = tuple(tuple(map(float, xy.split(","))) for xy in polygon.get("shape").split())
            if len(points) < 3:
                continue
            for wall in _walls(points):
                for cell in _box_cells(wall[:2], wall[2:]):
                    self.cells.setdefault(cell, []).append(wall)

    def blocks(self, start, end):
        tested = set()
        for cell in _ray_cells(start, end):
            for wall in self.cells.get(cell, ()):
                if wall not in tested:
                    if _intersects(start, end, wall):
                        return True
                    tested.add(wall)
        return False


@dataclass
class _Target:
    center: tuple
    direction: tuple
    length: float
    walls: tuple
    radius: float

    @classmethod
    def from_pose(cls, front, angle, length, width):
        direction = heading(angle)
        center = offset(front, direction, -length / 2)
        rear = offset(front, direction, -length)
        side = (-direction[1], direction[0])
        corners = (
            offset(front, side, width / 2), offset(rear, side, width / 2),
            offset(rear, side, -width / 2), offset(front, side, -width / 2),
        )
        return cls(center, direction, length, _walls(corners), hypot(length, width) / 2)


@dataclass
class Track:
    center: tuple
    direction: tuple
    length: float
    speed: float | None


class ToFFrame:
    """One geometric scan from front and two rear-quarter G32-inspired heads."""

    def __init__(self, front, angle, length, samples, buildings, config, previous, dt):
        self.direction = heading(angle)
        self.center = offset(front, self.direction, -length / 2)
        self.range = config["range_m"]
        self.cos_half_fov = cos(radians(config["horizontal_fov_deg"] / 2))
        self.headings = tuple(heading(angle + yaw) for yaw in config["azimuths_deg"])
        self.buildings = buildings
        self.targets = {key: _Target.from_pose(*pose) for key, pose in samples.items()}
        self.target_cells = {}
        for key, target in self.targets.items():
            x, y = target.center
            radius = target.radius
            for cell in _box_cells((x - radius, y - radius), (x + radius, y + radius)):
                self.target_cells.setdefault(cell, []).append(key)
        self.tracks = {}
        self.positions = {}
        for key, target in self.targets.items():
            sample_points = (target.center,
                             offset(target.center, target.direction, target.length * 0.4),
                             offset(target.center, target.direction, -target.length * 0.4))
            if not any(self.visible(point, ignore=key) for point in sample_points):
                continue
            old = previous.get(key)
            speed = None if old is None or dt <= 0 else hypot(
                target.center[0] - old[0], target.center[1] - old[1]) / dt
            self.positions[key] = target.center
            self.tracks[key] = Track(target.center, target.direction, target.length, speed)

    def visible(self, point, *, ignore=None, front_only=False):
        dx, dy = point[0] - self.center[0], point[1] - self.center[1]
        distance = hypot(dx, dy)
        directions = self.headings[:1] if front_only else self.headings
        if distance > self.range or not any(
            dx * x + dy * y >= distance * self.cos_half_fov for x, y in directions
        ):
            return False
        if self.buildings.blocks(self.center, point):
            return False
        tested = {ignore}
        for cell in _ray_cells(self.center, point):
            for key in self.target_cells.get(cell, ()):
                if key not in tested:
                    if any(_intersects(self.center, point, wall) for wall in self.targets[key].walls):
                        return False
                    tested.add(key)
        return True
