"""Mix full-route episodes with short junction approaches during training."""

import gymnasium as gym


class JunctionCurriculum(gym.Wrapper):
    track_junction_focus = True

    def __init__(self, env, *, share, seed, focus_steps=80, target_lane=None, safe_pass_bonus=0.0):
        super().__init__(env)
        self.share = share
        self.seed = seed
        self.focus_steps = focus_steps
        self.target_lane = target_lane
        self.approach_edge = target_lane.rsplit("_", 1)[0] if target_lane else None
        self.safe_pass_bonus = safe_pass_bonus
        self.total = 0
        self.focus_total = 0
        self.elapsed = 0
        self.focused = False
        self.exit_edge = None
        self.on_approach = False
        self.braked_for_hazard = False
        self.safe_entry = False

    def reset(self, *, seed=None, options=None):
        prefer_focus = self.total == 0 or self.focus_total < self.share * self.total
        if self.total == 0 and seed is None:
            seed = self.seed
        reset_options = {**(options or {}), "tof_junction_focus": prefer_focus}
        if prefer_focus and self.target_lane:
            reset_options["tof_junction_focus_lane"] = self.target_lane
        obs, info = self.env.reset(seed=seed, options=reset_options)
        self.focused = info.get("tof_junction_focus", False)
        self.exit_edge = info.get("tof_junction_focus_exit_edge")
        self.on_approach = self.safe_pass_bonus > 0.0 and self.exit_edge is not None
        self.braked_for_hazard = False
        self.safe_entry = False
        self.elapsed = 0
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self.total += 1
        if self.focused:
            self.focus_total += 1
            self.elapsed += 1
            info["tof_junction_focus"] = True
            road = info["road_id"]
            if self.on_approach:
                if road == self.approach_edge:
                    self.braked_for_hazard |= (info["tof_yield_hazard"] and info["tof_yield_decelerated"]
                                               and info["accel_raw"] < 0.0)
                else:
                    self.on_approach = False
                    # The hazard flag records the observation before the entry action.
                    enters_junction = road is not None and (road.startswith(":") or road == self.exit_edge)
                    self.safe_entry = enters_junction and self.braked_for_hazard and not info["tof_yield_hazard"]
            cleared = (self.exit_edge is not None and not (terminated or truncated)
                       and road == self.exit_edge)
            if cleared:
                info["tof_junction_focus_crossed"] = True
                if self.safe_entry and not (info["collided"] or info["teleported"]):
                    reward += self.safe_pass_bonus
                    info["tof_junction_safe_pass_bonus"] = self.safe_pass_bonus
                    self.safe_entry = False
            if not terminated and (cleared or self.elapsed >= self.focus_steps):
                truncated = True
        return obs, reward, terminated, truncated, info
