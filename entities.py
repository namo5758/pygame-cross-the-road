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


class Car:
    def __init__(self, lane, kind, level_settings):
        self.lane = lane
        self.direction = LANE_DIRECTION[lane]
        self.kind = kind
        vehicle_specification = VEHICLES[kind]
        self.length = vehicle_specification["length"]
        self.width = vehicle_specification["width"]
        self.height = vehicle_specification["height"]
        speed_multiplier = vehicle_specification["speed"]
        self.color = random.choice({
            "truck": TRUCK_COLORS,
            "moto": MOTORCYCLE_COLORS,
            "sidecar": SIDECAR_COLORS,
            "icecream": ICECREAM_COLORS,
            "tanker": [(230, 232, 228)],
        }.get(kind, CAR_COLORS))
        self.cargo = random.choice(["passenger", "crates", "bottles"])   # what's in the sidecar
        self.fuse = 0.0          # tanker: seconds until it blows up after a crash
        self.burnt = False
        self.skid_points = None  # last wheel positions, for skid marks
        # Actual speed = lane speed * level multiplier * vehicle multiplier * random variation of +/-10%.
        # ความเร็วจริงมาจากความเร็วเลน คูณความยาก คูณประเภทรถ แล้วสุ่มให้ต่างกันเล็กน้อย
        self.base_speed = LANE_SPEED[lane] * level_settings["speed"] * speed_multiplier * random.uniform(0.9, 1.1)
        self.speed = self.base_speed
        # Spawn beyond the incoming screen edge so the vehicle enters smoothly.
        self.x = -self.length if self.direction > 0 else SCREEN_WIDTH + self.length
        self.y = lane_center(lane)
        self.base_angle = 0.0 if self.direction > 0 else math.pi
        self.heading = self.base_angle
        self.lateral_speed = 0.0
        self.skid = 0.0          # sliding on blood
        self.stall = 0.0         # braking after hitting someone
        self.wreck = False       # crashed, blocking the road
        self.wreck_time = 0.0
        self.towed = False       # hooked by a drone
        self.lift = 0.0          # height while being carried away
        self.rider_color = random.choice([(200, 60, 50), (50, 120, 200), (230, 200, 60)])

    @property
    def angle(self):
        return self.heading

    def blocks(self, lane_index):
        """A wreck blocks every lane it overlaps; a moving car only its own lane."""
        if not self.wreck:
            return self.lane == lane_index
        # Overlap occurs when center separation is smaller than the sum of half-widths, with a small margin.
        return abs(lane_center(lane_index) - self.y) < self.width / 2 + LANE_HEIGHT / 2 - 6

    # Use the nearest ground corner for drawing order so a car can cover objects behind it.
    def depth(self):
        return max(corner[1] for corner in box_corners(self.x, self.y, self.length, self.width, self.angle))

    # Stationary wrecks and towed cars cannot hit people; moving or sliding cars can.
    def dangerous(self):
        return not self.wreck and not self.towed and (self.speed > 25 or self.skid > 0)

    def hits(self, person_x, person_y, radius=8):
        # Rotate the person by the negative car angle to express their position in the car frame.
        # Collision then becomes two simple bounds checks against a rectangle expanded by the person radius.
        # หมุนตำแหน่งคนกลับให้ตรงกับแนวรถก่อน จึงตรวจได้ง่ายว่าคนอยู่ในกรอบรถหรือไม่
        cosine_angle, sine_angle = math.cos(-self.angle), math.sin(-self.angle)
        delta_x = person_x - self.x
        delta_y = person_y - self.y
        local_x = delta_x * cosine_angle - delta_y * sine_angle
        local_y = delta_x * sine_angle + delta_y * cosine_angle
        return abs(local_x) < self.length / 2 + radius and abs(local_y) < self.width / 2 + radius
