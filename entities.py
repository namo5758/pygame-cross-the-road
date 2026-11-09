"""Game-world entities and their local behavior.

These classes hold mutable state. Cross-object interactions remain in Game's
simulation methods so collision and level rules have one owner.
"""

import math
import random

from game_config import (
    BLOOD,
    BLOOD_HIGHLIGHT,
    CAR_COLORS,
    CROSSING_START_X,
    CROSSING_END_X,
    ICECREAM_COLORS,
    LANE_DIRECTION,
    LANE_HEIGHT,
    LANE_SPEED,
    MOTORCYCLE_COLORS,
    PERSON_TYPES,
    ROAD_BOTTOM,
    ROAD_TOP,
    SCREEN_WIDTH,
    SIDECAR_COLORS,
    TRUCK_COLORS,
    VEHICLES,
    WORLD_BOTTOM,
)
from geometry import box_corners, clamp, in_band, in_road, lane_center


# ---------------------------------------------------------------- entities
class Person:
    def __init__(self, kind, x, y, index):
        self.kind = kind
        self.index = index
        self.x, self.y = x, y
        # Waypoints are visited in order; an empty list means there is no walking destination.
        self.path = []
        self.alive = True
        self.saved = False
        self.is_walking = False
        # Countdown values use seconds. The simulation subtracts delta_time until an effect expires.
        # เวลาคงเหลือใช้หน่วยวินาที และลดลงตามเวลาที่ผ่านไปในแต่ละเฟรม
        self.cooldown = 0.0
        self.dash = 0.0
        self.tired = 0.0
        self.slip_time = 0.0
        self.slip_velocity = (0.0, 0.0)
        self.slip_immune = 0.0
        # Carrying links work both ways: the carrier points to the passenger, and the passenger to the carrier.
        self.carrying = None
        self.carried_by = None
        self.fuel = False
        self.alone_time = 0.0
        self.panic = False
        self.wander_direction = (0.0, 0.0)
        self.wander_time = 0.0
        self.sign_time = 0.0
        # Random starting phases stop every character from swinging their legs in perfect synchronization.
        self.walk_phase = random.random() * 10
        self.moving = False
        self.facing = 1
        # health & animation state
        self.maximum_health = PERSON_TYPES[kind]["health"]
        self.health = float(self.maximum_health)
        self.hurt_time = 0.0            # red flash after taking damage
        self.invulnerable_time = 0.0    # short grace period after a car hit
        self.down_time = 0.0            # knocked down, can't move
        self.burn_time = 0.0            # on fire
        self.charring_level = 0.0           # 0..1 how burnt the body looks
        self.pose = 0.0                 # 0 = standing, pi/2 = lying flat
        self.fall_direction = 1
        self.death_time = 0.0
        self.death_cause = None
        self.drip_time = 0.0

    @property
    def information(self):
        return PERSON_TYPES[self.kind]

    @property
    # Only living, unsaved people who are not being carried can respond independently.
    def active(self):
        return self.alive and not self.saved and self.carried_by is None

    @property
    # Severe injury means remaining health is below 40% of starting health.
    def injured(self):
        return self.health < self.maximum_health * 0.4

    def speed(self):
        if self.down_time > 0:
            return 0.0
        # Start with the character speed, then multiply by injury, fire, sprint, fatigue, and carrying effects.
        # Multipliers combine: for example, injury and carrying give base_speed * 0.6 * 0.8.
        # ตัวคูณมีผลต่อเนื่องกัน เช่น บาดเจ็บและอุ้มคนจะเหลือความเร็ว 0.6 × 0.8 = 48% ของปกติ
        current_speed = self.information["speed"]
        if self.injured:
            current_speed *= 0.6
        if self.burn_time > 0:
            current_speed *= 1.25            # running while on fire
        if self.dash > 0:
            current_speed *= 2.2
        elif self.tired > 0:
            current_speed *= 0.55
        if self.carrying:
            current_speed *= 0.8
        return current_speed

    def set_target(self, target_x, target_y):
        """Plan waypoints so people only cross the road on the zebra crossing."""
        target_y = clamp(target_y, 16, WORLD_BOTTOM - 10)
        target_x = clamp(target_x, 12, SCREEN_WIDTH - 12)
        if in_road(target_y):
            target_x = clamp(target_x, CROSSING_START_X + 8, CROSSING_END_X - 8)
        waypoints = []
        # Classify start and destination by curb position so the route can include crossing-entry waypoints.
        start_side = "near" if self.y >= ROAD_BOTTOM else "far" if self.y <= ROAD_TOP else "road"
        destination_side = "near" if target_y >= ROAD_BOTTOM else "far" if target_y <= ROAD_TOP else "road"
        if start_side != destination_side:
            if start_side != "road" and not in_band(self.x):
                curb_y = ROAD_BOTTOM + 10 if start_side == "near" else ROAD_TOP - 10
                waypoints.append((clamp(self.x, CROSSING_START_X + 8, CROSSING_END_X - 8), curb_y))
            if destination_side != "road" and not in_band(target_x):
                curb_y = ROAD_BOTTOM + 10 if destination_side == "near" else ROAD_TOP - 10
                base_x = waypoints[-1][0] if waypoints else clamp(self.x, CROSSING_START_X + 8, CROSSING_END_X - 8)
                waypoints.append((base_x, curb_y))
        waypoints.append((target_x, target_y))
        self.path = waypoints
