"""ข้อมูลของสิ่งต่าง ๆ ในเกม: คน รถ โดรน แอ่ง ไฟ อนุภาค ข้อความ

การชนกันระหว่างของต่างชนิดอยู่ใน simulation.py ที่เดียว
"""

import math
import random
from dataclasses import dataclass

from game_config import (
    BLOOD,
    BLOOD_HIGHLIGHT,
    CAR_COLORS,
    CROSSING_START_X,
    CROSSING_END_X,
    LANE_DIRECTION,
    LANE_HEIGHT,
    LANE_SPEED,
    PERSON_TYPES,
    ROAD_BOTTOM,
    ROAD_TOP,
    SCREEN_WIDTH,
    VEHICLE_COLORS,
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
        self.path = []
        self.alive = True
        self.saved = False
        self.is_walking = False
        # ตัวนับถอยหลังทั้งหมดเป็นวินาที
        self.cooldown = 0.0
        self.dash = 0.0
        self.tired = 0.0
        self.slip_time = 0.0
        self.slip_velocity = (0.0, 0.0)
        self.slip_immune = 0.0
        # ลิงก์สองทาง: คนอุ้มชี้ไปที่คนถูกอุ้ม และกลับกัน
        self.carrying = None
        self.carried_by = None
        self.fuel = False
        self.alone_time = 0.0
        self.panic = False
        self.wander_direction = (0.0, 0.0)
        self.wander_time = 0.0
        self.sign_time = 0.0
        # สุ่มจังหวะเริ่ม ขาจะได้ไม่แกว่งพร้อมกันทุกคน
        self.walk_phase = random.random() * 10
        self.moving = False
        self.facing = 1
        # HP และท่าทาง
        self.maximum_health = PERSON_TYPES[kind]["health"]
        self.health = float(self.maximum_health)
        self.hurt_time = 0.0  # กะพริบแดงหลังโดนตี
        self.invulnerable_time = 0.0  # อมตะชั่วคราวหลังโดนรถ
        self.down_time = 0.0  # ล้มอยู่ ขยับไม่ได้
        self.burn_time = 0.0  # ติดไฟ
        self.charring_level = 0.0  # 0..1 ตัวไหม้แค่ไหน
        self.pose = 0.0  # 0 = ยืน, π/2 = นอน
        self.fall_direction = 1
        self.death_time = 0.0
        self.death_cause = None
        self.drip_time = 0.0

    @property
    def information(self):
        return PERSON_TYPES[self.kind]

    @property
    # ยังสั่งได้: มีชีวิต ยังไม่ถึง และไม่ได้ถูกอุ้ม
    def active(self):
        return self.alive and not self.saved and self.carried_by is None

    @property
    # บาดเจ็บหนัก = HP ต่ำกว่า 40%
    def injured(self):
        return self.health < self.maximum_health * 0.4

    def speed(self):
        if self.down_time > 0:
            return 0.0
        # ตัวคูณซ้อนกันได้ เช่น บาดเจ็บ + อุ้มคน = 0.6 × 0.8
        current_speed = self.information["speed"]
        if self.injured:
            current_speed *= 0.6
        if self.burn_time > 0:
            current_speed *= 1.25  # ติดไฟแล้ววิ่ง
        if self.dash > 0:
            current_speed *= 2.2
        elif self.tired > 0:
            current_speed *= 0.55
        if self.carrying:
            current_speed *= 0.8
        return current_speed

    def set_target(self, target_x, target_y):
        """วางจุดเดินให้ข้ามถนนเฉพาะในทางม้าลาย"""
        target_y = clamp(target_y, 16, WORLD_BOTTOM - 10)
        target_x = clamp(target_x, 12, SCREEN_WIDTH - 12)
        if in_road(target_y):
            target_x = clamp(target_x, CROSSING_START_X + 8, CROSSING_END_X - 8)
        waypoints = []
        # ต้นทางหรือปลายทางอยู่นอกถนน ต้องเดินไปเข้าทางม้าลายก่อน
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
        self.color = random.choice(VEHICLE_COLORS.get(kind, CAR_COLORS))
        self.cargo = random.choice(["passenger", "crates", "bottles"])  # ของในพ่วงข้าง
        self.fuse = 0.0  # รถน้ำมัน: วินาทีก่อนระเบิด
        self.burnt = False
        self.skid_points = None  # ตำแหน่งล้อเฟรมก่อน ใช้ต่อรอยเบรก
        # ความเร็ว = ความเร็วเลน × ความยาก × ชนิดรถ ± 10%
        self.base_speed = LANE_SPEED[lane] * level_settings["speed"] * speed_multiplier * random.uniform(0.9, 1.1)
        self.speed = self.base_speed
        # เกิดนอกจอฝั่งที่รถวิ่งเข้ามา
        self.x = -self.length if self.direction > 0 else SCREEN_WIDTH + self.length
        self.y = lane_center(lane)
        self.base_angle = 0.0 if self.direction > 0 else math.pi
        self.angle = self.base_angle
        self.lateral_speed = 0.0
        self.skid = 0.0  # ไถลบนเลือด
        self.stall = 0.0  # เบรกหลังชนคน
        self.wreck = False  # เป็นซาก ขวางถนน
        self.towed = False  # ถูกโดรนเกี่ยว
        self.lift = 0.0  # ความสูงตอนถูกยก
        self.rider_color = random.choice([(200, 60, 50), (50, 120, 200), (230, 200, 60)])

    def blocks(self, lane_index):
        """ซากรถขวางทุกเลนที่ทับอยู่ รถที่วิ่งปกติขวางแค่เลนตัวเอง"""
        if not self.wreck:
            return self.lane == lane_index
        return abs(lane_center(lane_index) - self.y) < self.width / 2 + LANE_HEIGHT / 2 - 6

    # ใช้มุมที่อยู่ล่างสุดเป็นความลึก รถยาวที่เอียงจะได้ทับของข้างหลังถูก
    def depth(self):
        return max(corner[1] for corner in box_corners(self.x, self.y, self.length, self.width, self.angle))

    # ซากกับรถที่ถูกยกชนคนไม่ได้
    def dangerous(self):
        return not self.wreck and not self.towed and (self.speed > 25 or self.skid > 0)

    def hits(self, person_x, person_y, radius=8):
        # หมุนตำแหน่งคนกลับเข้าแกนของรถ แล้วเช็กแค่กรอบสี่เหลี่ยม
        cosine_angle, sine_angle = math.cos(-self.angle), math.sin(-self.angle)
        delta_x = person_x - self.x
        delta_y = person_y - self.y
        local_x = delta_x * cosine_angle - delta_y * sine_angle
        local_y = delta_x * sine_angle + delta_y * cosine_angle
        return abs(local_x) < self.length / 2 + radius and abs(local_y) < self.width / 2 + radius


class Drone:
    """โดรนยกซาก: บินเข้า → หย่อนสาย → ยก → บินออก"""
    def __init__(self, car):
        self.car = car
        # เข้าจากฝั่งที่ใกล้กว่า เริ่มนอกจอด้านบน
        exit_side = -1 if car.x < SCREEN_WIDTH / 2 else 1
        self.x = car.x + exit_side * 420
        self.y = -60.0
        self.z = 150.0
        self.exit_x = -260 if exit_side < 0 else SCREEN_WIDTH + 260
        self.state = "fly"
        self.time_elapsed = 0.0
        self.cable_extension = 0.0
        self.done = False

    def update(self, delta_time):
        target_car = self.car
        self.time_elapsed += delta_time
        if self.state == "fly":
            delta_x = target_car.x - self.x
            delta_y = target_car.y - self.y
            distance = math.hypot(delta_x, delta_y)
            step = 380 * delta_time
            # ค่อย ๆ ปรับความสูงเข้าหา 120 (สัดส่วนไม่เกิน 1 จะได้ไม่เลย)
            self.z += (120 - self.z) * min(1.0, 2 * delta_time)
            if distance <= step:
                self.x, self.y = target_car.x, target_car.y
                self.state = "hook"
                self.time_elapsed = 0.0
            else:
                self.x += delta_x / distance * step
                self.y += delta_y / distance * step
        elif self.state == "hook":
            # หย่อนสายจนสุดใน 0.6 วิ
            self.cable_extension = min(1.0, self.time_elapsed / 0.6)
            if self.time_elapsed > 0.7:
                target_car.towed = True  # ไม่ขวางถนนแล้ว
                self.state = "lift"
                self.time_elapsed = 0.0
        elif self.state == "lift":
            # ยกขึ้น 70 ใน 0.8 วิ
            lift_progress = min(1.0, self.time_elapsed / 0.8)
            target_car.lift = 70 * lift_progress
            self.z = 120 + 40 * lift_progress
            if lift_progress >= 1:
                self.state = "away"
                self.time_elapsed = 0.0
        else:  # away
            delta_x = self.exit_x - self.x
            delta_y = -120 - self.y
            distance = math.hypot(delta_x, delta_y) or 1
            # เร่งจาก 80 ขึ้น 300 ต่อวินาที สูงสุด 320
            fly_speed = min(320, 80 + self.time_elapsed * 300)
            self.x += delta_x / distance * fly_speed * delta_time
            self.y += delta_y / distance * fly_speed * delta_time
            self.z += 20 * delta_time
            target_car.lift += 20 * delta_time
            target_car.x, target_car.y = self.x, self.y
            if distance < 30 or self.x < -240 or self.x > SCREEN_WIDTH + 240:
                self.done = True


class Puddle:
    def __init__(self, x, y, radius=24, color=BLOOD, highlight_color=BLOOD_HIGHLIGHT):
        self.x, self.y, self.radius = x, y, radius
        self.color, self.highlight_color = color, highlight_color
        self.life = 10.0
        # รถที่เหยียบแอ่งนี้ไปแล้ว ลื่นได้ครั้งเดียวต่อแอ่ง
        self.hit_cars = set()
        # วงกลมหลายวงซ้อนกัน แอ่งจะได้ไม่กลมเป๊ะ
        self.blobs = [
            (random.uniform(-radius * 0.5, radius * 0.5),
             random.uniform(-radius * 0.4, radius * 0.4),
             random.uniform(radius * 0.45, radius * 0.85))
            for _ in range(5)
        ]
        self.blobs.append((0, 0, radius * 0.8))


class Fire:
    def __init__(self, x, y, radius=55):
        self.x, self.y, self.radius = x, y, radius
        self.life = 4.0


class Particle:
    def __init__(self, x, y, z, color, size, life, velocity_x=0.0, velocity_y=0.0, velocity_z=0.0, gravity=500, shape="dot"):
        self.x, self.y, self.z = x, y, z
        self.velocity_x = velocity_x
        self.velocity_y = velocity_y
        self.velocity_z = velocity_z
        self.color, self.size = color, size
        # เก็บอายุตอนเริ่มไว้ ใช้คำนวณความจางตอนวาด
        self.life = self.maximum_life = life
        # gravity บวก = ตก, ลบ = ลอยขึ้น (ควัน เปลวไฟ)
        self.gravity = gravity
        self.shape = shape  # "dot", "chunk" (ชิ้นส่วนรถ) หรือ "wheel"
        self.angle = random.uniform(0, math.tau)
        self.spin = random.uniform(-12, 12)


@dataclass
class FloatingText:
    """ข้อความเล็กที่ลอยขึ้นจากจุดในโลก เช่น ลื่น! หรือ -12"""
    x: float
    y: float
    height: float
    text: str
    life: float
    color: tuple


@dataclass
class Toast:
    """ข้อความแจ้งเตือนกลางจอด้านบน"""
    text: str
    life: float
    color: tuple


@dataclass
class ImpactText:
    """คำใหญ่ตอนชน เช่น โครม!"""
    x: float
    y: float
    text: str
    life: float
    color: tuple
    size: float
    rotation: float
    offset_z: float
