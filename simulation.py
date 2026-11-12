"""กติกาเกม: การเคลื่อนที่ของรถและคน การชน ความเสียหาย และผลแพ้ชนะ

ไฟล์นี้ไม่ import pygame และไม่วาดอะไรเลย แค่เปลี่ยนค่าใน state ให้ render ไปวาด
"""

import math
import random

from entities import Car, Drone, Fire, FloatingText, ImpactText, Particle, Puddle, Toast
from game_config import (
    ACCENT_COLOR,
    BAD_COLOR,
    BLOOD,
    BLOOD_HIGHLIGHT,
    CROSSING_START_X,
    CROSSING_END_X,
    GOAL_Y,
    GOOD_COLOR,
    ICECREAM_GOO,
    LANES,
    MUTED_COLOR,
    ROAD_BOTTOM,
    ROAD_TOP,
    SCREEN_WIDTH,
    TEXT_COLOR,
    VEHICLES,
    WORLD_BOTTOM,
)
from geometry import clamp, in_band, in_road, lane_center, lane_of, local, paired_lane, shade


def pick(value):
    """(ต่ำ, สูง) -> สุ่มค่าในช่วงนั้น, ตัวเลขเดี่ยว -> ใช้ตามนั้น"""
    return random.uniform(*value) if isinstance(value, tuple) else value


class GameSimulation:
    # ทุกอย่างที่เคลื่อนที่คูณ delta_time (วินาที) ความเร็วจึงไม่ขึ้นกับ FPS
    def update(self, delta_time):
        if self.state == "title" or self.paused:
            return
        if self.state == "play":
            self.elapsed_time += delta_time
        self.update_traffic(delta_time)
        for person in self.people:
            self.animate_person(person, delta_time)
        if self.state == "play":
            for person in self.people:
                self.update_person(person, delta_time)
            self.check_hits()
            self.check_end()

        for puddle in self.puddles:
            puddle.life -= delta_time
        self.puddles = [puddle for puddle in self.puddles if puddle.life > 0]

        for fire in self.fires:
            fire.life -= delta_time
            if random.random() < 0.6:
                angle = random.uniform(0, math.tau)
                radius = random.uniform(0, fire.radius * 0.8)
                self.particles.append(Particle(
                    fire.x + math.cos(angle) * radius, fire.y + math.sin(angle) * radius * 0.6, 4,
                    velocity_z=random.uniform(40, 90),
                    color=random.choice([(255, 150, 40), (255, 90, 30), (255, 210, 80)]),
                    size=random.uniform(2, 4), life=0.6, gravity=-20,
                ))
        self.fires = [fire for fire in self.fires if fire.life > 0]

        for particle in self.particles:
            particle.life -= delta_time
            # Euler: ขยับตามความเร็ว แล้วค่อยลดความเร็วแนวดิ่งด้วยแรงโน้มถ่วง
            particle.x += particle.velocity_x * delta_time
            particle.y += particle.velocity_y * delta_time
            particle.z += particle.velocity_z * delta_time
            particle.velocity_z -= particle.gravity * delta_time
            particle.angle += particle.spin * delta_time
            if particle.z < 0:
                if particle.shape != "dot" and particle.velocity_z < -90:  # เศษรถตกแรงจะเด้ง
                    # เด้งกลับ 40% ของความเร็วตก
                    particle.z, particle.velocity_z = 0, -particle.velocity_z * 0.4
                    particle.velocity_x *= 0.6
                    particle.velocity_y *= 0.6
                    particle.spin *= 0.6
                else:
                    particle.z, particle.velocity_z = 0, 0
                    particle.velocity_x *= 0.5
                    particle.velocity_y *= 0.5
                    particle.spin *= 0.5
        self.particles = [particle for particle in self.particles if particle.life > 0]

        self.active_surface_shake_strength = max(0.0, self.active_surface_shake_strength - 45 * delta_time)
        self.flash_intensity = max(0.0, self.flash_intensity - 3 * delta_time)

        for impact_message in self.impact_messages:
            impact_message.life -= delta_time
        self.impact_messages = [impact_message for impact_message in self.impact_messages if impact_message.life > 0]

        self.skid_mark_fade_timer += delta_time
        if self.skid_mark_fade_timer > 0.5:  # render_ground.draw_skid_marks เป็นคนจางจริง
            self.skid_mark_fade_timer = 0
            self.skid_fades_pending += 1

        for floater in self.floating_messages:
            floater.life -= delta_time
            floater.height += 30 * delta_time
        self.floating_messages = [floater for floater in self.floating_messages if floater.life > 0]

        for toast_entry in self.toast_messages:
            toast_entry.life -= delta_time
        self.toast_messages = [toast_entry for toast_entry in self.toast_messages if toast_entry.life > 0]

    def update_traffic(self, delta_time, pre_warm=False):
        level_settings = self.current_level
        for lane_index in range(LANES):
            self.lane_freeze_timers[lane_index] = max(0.0, self.lane_freeze_timers[lane_index] - delta_time)
            self.spawn_timers[lane_index] -= delta_time
            if self.spawn_timers[lane_index] <= 0:
                # สุ่มชนิดรถตามน้ำหนักใน mix ของด่าน
                vehicle_kind = random.choices(list(level_settings["mix"]), weights=list(level_settings["mix"].values()))[0]
                new_car = Car(lane_index, vehicle_kind, level_settings)
                # เกิดได้เมื่อไม่ทับรถคันอื่นในเลน (เผื่อระยะ 40)
                edge_clear = all(
                    not (other_car.blocks(lane_index) and abs(other_car.x - new_car.x) < (other_car.length + new_car.length) / 2 + 40)
                    for other_car in self.cars if not other_car.towed
                )
                if edge_clear:
                    self.cars.append(new_car)
                    self.spawn_timers[lane_index] = random.uniform(*level_settings["gap"])
                else:
                    self.spawn_timers[lane_index] = 0.3

        grandmothers = [
            person for person in self.people
            if person.alive and not person.saved and person.kind == "grandma"
            and ROAD_TOP - 20 < person.y < ROAD_BOTTOM + 20
        ] if not pre_warm else []

        active_road_cars = [car for car in self.cars if not car.towed]
        for car in self.cars:
            if car.towed:
                continue  # โดรนเป็นคนขยับ
            if car.wreck:
                if car.fuse > 0:
                    car.fuse -= delta_time
                    if random.random() < 0.6:  # น้ำมันรั่ว มีประกายไฟ
                        self.particles.append(Particle(
                            car.x + random.uniform(-car.length / 3, car.length / 3), car.y, 8,
                            velocity_x=random.uniform(-40, 40),
                            velocity_y=random.uniform(-20, 20),
                            velocity_z=random.uniform(60, 140),
                            color=random.choice([(255, 200, 60), (255, 120, 30)]),
                            size=2, life=0.4,
                        ))
                    if car.fuse <= 0:
                        car.burnt = True
                        car.color = (52, 48, 46)
                        self.explode(car.x, car.y, power=1.8)
                if random.random() < 0.25:
                    self.particles.append(Particle(
                        car.x + random.uniform(-car.length / 4, car.length / 4), car.y, car.height,
                        velocity_x=random.uniform(-6, 6),
                        velocity_z=random.uniform(25, 45),
                        color=random.choice([(80, 80, 84), (110, 110, 114)]),
                        size=random.uniform(3, 6), life=1.6, gravity=-8,
                    ))
                continue

            if car.skid > 0:
                # ลื่นเลือด: ยังวิ่งไปข้างหน้า แต่ไถลไปทางเลนข้าง ๆ
                car.skid -= delta_time
                car.speed *= (1 - 0.5 * delta_time)
                car.y = clamp(car.y + car.lateral_speed * delta_time, ROAD_TOP + car.width / 2 + 2, ROAD_BOTTOM - car.width / 2 - 2)
                wobble = math.sin(car.skid * 18) * 0.08
                # หันหัวรถตามทิศที่ไถลจริง (atan2) แล้วส่ายนิดหน่อย
                car.angle = math.atan2(car.lateral_speed * 0.6, car.direction * max(car.speed, 1)) + wobble
                if car.skid <= 0:
                    car.lateral_speed = 0
                    # ไถลเสร็จ เลือกเลนที่ตัวรถอยู่ใกล้กว่าระหว่างเลนเดิมกับเลนคู่
                    car.lane = min((car.lane, paired_lane(car.lane)), key=lambda lane_index: abs(lane_center(lane_index) - car.y))
            else:
                if car.stall > 0:
                    car.stall -= delta_time
                    target_speed = 0
                else:
                    target_speed = car.base_speed
                    if self.lane_freeze_timers[car.lane] > 0:
                        target_speed = 0
                    for grandmother in grandmothers:
                        if abs(car.x - grandmother.x) < 170 and abs(car.y - grandmother.y) < 75:
                            target_speed *= 0.35
                    gap = 1e9
                    ahead_car = None
                    for other_car in active_road_cars:
                        if other_car is car or not other_car.blocks(car.lane):
                            continue
                        # คูณ direction ให้ค่าบวก = อยู่ข้างหน้า ทั้งรถที่วิ่งซ้ายและขวา
                        distance_ahead = (other_car.x - car.x) * car.direction
                        if distance_ahead > 0:
                            gap_distance = distance_ahead - (other_car.length + car.length) / 2
                            if gap_distance < gap:
                                ahead_car, gap = other_car, gap_distance
                    if ahead_car:
                        # ระยะเบรก v² / 2a (a = 480) บวกระยะเผื่อ 16
                        stop_distance = car.speed * car.speed / (2 * 480) + 16
                        if gap < stop_distance + 30:
                            target_speed = min(target_speed, 0 if (gap < stop_distance or ahead_car.wreck) else ahead_car.speed * 0.9)
                # เบรกแรงกว่าเร่ง (520 กับ 200 ต่อวินาที)
                speed_delta = target_speed - car.speed
                rate = 520 if speed_delta < 0 else 200
                car.speed += clamp(speed_delta, -rate * delta_time, rate * delta_time)
                # ค่อย ๆ กลับเข้ากลางเลนและหันตรง (ขยับทีละสัดส่วนของระยะที่เหลือ)
                car.y += (lane_center(car.lane) - car.y) * min(1.0, 2.5 * delta_time)
                car.angle += (car.base_angle - car.angle) * min(1.0, 4 * delta_time)
            car.x += car.direction * car.speed * delta_time
            if (car.skid > 0 or (car.stall > 0 and car.speed > 30)) and not pre_warm:
                self.skid_marks(car)
            else:
                car.skid_points = None

            # เหยียบแอ่งเลือด
            if car.skid <= 0 and car.speed > 40:
                for puddle in self.puddles:
                    if car in puddle.hit_cars:
                        continue
                    if math.hypot(car.x - puddle.x, car.y - puddle.y) < puddle.radius + car.width * 0.45:
                        puddle.hit_cars.add(car)
                        if puddle.radius < 20 and random.random() < 0.6:
                            continue  # แอ่งเล็กลื่นแค่บางครั้ง
                        car.skid = 0.9
                        other_lane = paired_lane(car.lane)
                        # ความเร็วด้านข้างพอให้ไถลถึงเลนคู่ภายใน 0.9 วิ
                        car.lateral_speed = (lane_center(other_lane) - car.y) / 0.9 * random.uniform(0.8, 1.15)
                        self.float_text(car.x, car.y, "ลื่น!", ACCENT_COLOR)
                        if not pre_warm:
                            self.toast("รถลื่นคราบเลือด!", ACCENT_COLOR)
                        break

        # รถชนกัน
        for first_index, first_car in enumerate(active_road_cars):
            # ตรวจแต่ละคู่ครั้งเดียว
            for second_car in active_road_cars[first_index + 1:]:
                if first_car.wreck and second_car.wreck:
                    continue
                if first_car.skid <= 0 and second_car.skid <= 0:
                    continue  # รถปกติเว้นระยะเองอยู่แล้ว ชนได้เฉพาะตอนไถล
                if (abs(first_car.x - second_car.x) < (first_car.length + second_car.length) / 2 - 6 and abs(first_car.y - second_car.y) < (first_car.width + second_car.width) / 2 - 4):
                    self.crash(first_car, second_car)

        for drone in self.drones:
            drone.update(delta_time)
        done_cars = {drone.car for drone in self.drones if drone.done}
        self.drones = [drone for drone in self.drones if not drone.done]
        self.cars = [
            car for car in self.cars
            if car not in done_cars and (car.wreck or car.towed or -car.length * 2 < car.x < SCREEN_WIDTH + car.length * 2)
        ]

    # ชนหลายครั้งพร้อมกัน เอาค่าที่แรงที่สุด ไม่บวกกัน
    def juice(self, shake_strength=0.0, hitstop_seconds=0.0, flash_intensity=0.0):
        self.active_surface_shake_strength = max(self.active_surface_shake_strength, shake_strength)
        self.hitstop_remaining = max(self.hitstop_remaining, hitstop_seconds)
        self.flash_intensity = max(self.flash_intensity, flash_intensity)

    def impact_text(self, world_x, world_y, text, color=ACCENT_COLOR, size=1.0):
        # ถ้ามีคำซ้อนอยู่แถวนี้ ดันคำใหม่ขึ้นไป 38 ต่อคำ
        stack = sum(1 for impact_message in self.impact_messages if abs(impact_message.x - world_x) < 120 and abs(impact_message.y - world_y) < 80)
        self.impact_messages.append(ImpactText(world_x, world_y, text, 0.9, color, size, random.uniform(-12, 12), stack * 38))

    def debris(self, car, count=8):
        """เศษรถกระเด็น: ชิ้นส่วนตัวถัง ล้อ 1–2 ล้อ และเศษกระจก"""
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed_value = random.uniform(80, 260)
            particle_color = random.choice([car.color, shade(car.color, 0.7), (60, 62, 66)])
            self.particles.append(Particle(
                car.x, car.y, car.height * 0.6,
                velocity_x=math.cos(angle) * speed_value,
                velocity_y=math.sin(angle) * speed_value * 0.6,
                velocity_z=random.uniform(150, 320),
                color=particle_color,
                size=random.uniform(4, 7), life=random.uniform(1.6, 2.6), gravity=700, shape="chunk",
            ))
        for _ in range(random.randint(1, 2)):
            angle = random.uniform(0, math.tau)
            self.particles.append(Particle(
                car.x, car.y, 10,
                velocity_x=math.cos(angle) * 200,
                velocity_y=math.sin(angle) * 120,
                velocity_z=260,
                color=(28, 28, 32), size=6, life=2.6, gravity=700, shape="wheel",
            ))
        self.burst(car.x, car.y, car.height * 0.8, 10, speed=(60, 200), rise=(60, 180),
                   colors=[(180, 220, 240), (230, 245, 255)], size=2, life=0.9)

    def burst(self, x, y, z, count, speed, rise, colors, size, life, speed_scale=1.0):
        """อนุภาคพุ่งออกรอบจุดเดียวในทิศสุ่ม ค่าที่เป็น (ต่ำ, สูง) จะสุ่มใหม่ทุกชิ้น"""
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed_value = pick(speed) * speed_scale
            self.particles.append(Particle(
                x, y, z,
                velocity_x=math.cos(angle) * speed_value,
                velocity_y=math.sin(angle) * speed_value * 0.6,
                velocity_z=pick(rise),
                color=random.choice(colors),
                size=pick(size),
                life=pick(life),
            ))

    # ต่อเส้นจากตำแหน่งล้อหลังเฟรมก่อน ส่วนการวาดอยู่ใน render_ground.draw_skid_marks
    def skid_marks(self, car):
        points = [local(car.x, car.y, car.angle, -car.length * 0.32, local_y) for local_y in (-car.width / 2 + 3, car.width / 2 - 3)]
        if car.skid_points:
            width = 4 if car.width > 30 else 2
            for old_point, new_point in zip(car.skid_points, points):
                self.skid_segments.append((old_point, new_point, width))
        car.skid_points = points

    def crash(self, *cars):
        # จุดกลางของการชน ใช้วางเศษกับคำว่า โครม!
        mean_x = sum(car.x for car in cars) / len(cars)
        mean_y = sum(car.y for car in cars) / len(cars)
        for car in cars:
            if car.wreck or car.towed:
                continue
            car.wreck = True
            car.speed, car.skid, car.lateral_speed = 0, 0, 0
            car.angle += random.uniform(-0.3, 0.3)
            car.color = shade(car.color, 0.7)
            self.drones.append(Drone(car))
            self.debris(car)
            if car.kind == "icecream":
                for _ in range(4):  # ไอติมหกเต็มถนน ลื่นเหมือนเลือด
                    goo_color = random.choice(ICECREAM_GOO)
                    self.puddles.append(Puddle(
                        car.x + random.uniform(-50, 50),
                        car.y + random.uniform(-25, 25),
                        random.uniform(20, 28),
                        goo_color,
                        shade(goo_color, 1.15)
                    ))
                self.burst(car.x, car.y, car.height + 20, 14, speed=150, rise=(150, 280),
                           colors=ICECREAM_GOO, size=(4, 7), life=1.4)
                self.impact_text(car.x, car.y - 20, "ไอติมเละ!", (250, 190, 212), 0.9)
            elif car.kind == "tanker":
                car.fuse = 0.9  # อีก 0.9 วิ ระเบิด
                self.impact_text(car.x, car.y - 20, "น้ำมันรั่ว!", BAD_COLOR, 0.9)
            elif car.kind in ("moto", "sidecar"):
                car.angle += random.uniform(0.6, 1.2) * random.choice([-1, 1])  # มอเตอร์ไซค์ล้ม
        self.juice(shake_strength=11, hitstop_seconds=0.09, flash_intensity=0.35)
        self.impact_text(mean_x, mean_y, "โครม!", ACCENT_COLOR, 1.2)
        self.burst(mean_x, mean_y, 20, 26, speed=(60, 220), rise=(80, 220),
                   colors=[(255, 220, 120), (200, 200, 205), (120, 170, 220), (60, 60, 64)], size=(2, 4), life=0.8)
        self.toast("รถชนกัน! โดรนกำลังมายกออก", ACCENT_COLOR)

    def update_person(self, person, delta_time):
        if not person.alive or person.carried_by:
            return
        person.cooldown = max(0.0, person.cooldown - delta_time)
        person.sign_time = max(0.0, person.sign_time - delta_time)
        person.slip_immune = max(0.0, person.slip_immune - delta_time)
        if person.dash > 0:
            person.dash -= delta_time
            if person.dash <= 0:
                person.tired = 1.2
        elif person.tired > 0:
            person.tired -= delta_time
        if person.down_time > 0:
            person.down_time -= delta_time
        old_position = (person.x, person.y)

        if person.slip_time > 0:
            person.slip_time -= delta_time
            person.x = clamp(person.x + person.slip_velocity[0] * delta_time, 10, SCREEN_WIDTH - 10)
            person.y = clamp(person.y + person.slip_velocity[1] * delta_time, 16, WORLD_BOTTOM - 10)
            # แรงเสียดทาน: ความเร็วลื่นลดลงทุกเฟรม
            person.slip_velocity = (person.slip_velocity[0] * (1 - 3 * delta_time), person.slip_velocity[1] * (1 - 3 * delta_time))
        elif person.down_time > 0:
            pass
        elif person.saved:
            self.step_towards(person, delta_time, person.speed() * 0.7)
        else:
            # เด็กตกใจถ้าไม่มีใครอยู่ใกล้
            if person.kind == "kid":
                near = any(
                    other_person is not person and other_person.alive and math.hypot(other_person.x - person.x, other_person.y - person.y) < 75
                    for other_person in self.people
                )
                person.alone_time = 0 if near else person.alone_time + delta_time
                if person.alone_time > 2.0 and not person.panic:
                    person.panic = True
                    self.toast("เด็กอยู่คนเดียว ตกใจเดินมั่ว!", BAD_COLOR)
                elif near and person.panic:
                    person.panic = False
                    person.path = []
            if person.panic:
                person.wander_time -= delta_time
                if person.wander_time <= 0:
                    wander_angle = random.uniform(0, math.tau)
                    person.wander_direction = (math.cos(wander_angle), math.sin(wander_angle))
                    person.wander_time = random.uniform(0.4, 0.9)
                walk_speed = person.speed() * 0.6
                self.move_constrained(
                    person,
                    person.x + person.wander_direction[0] * walk_speed * delta_time,
                    person.y + person.wander_direction[1] * walk_speed * delta_time
                )
            else:
                if person.is_walking and not person.path:
                    self.plan_crossing(person)  # ลุกขึ้นแล้วเดินต่อ
                self.step_towards(person, delta_time, person.speed())

        person.moving = math.hypot(person.x - old_position[0], person.y - old_position[1]) > 0.05
        if person.moving:
            person.walk_phase += delta_time * (1.6 if person.dash > 0 else 1)
            if abs(person.x - old_position[0]) > 0.05:
                person.facing = 1 if person.x > old_position[0] else -1

        # เหยียบเลือดลื่น
        if person.slip_time <= 0 and person.slip_immune <= 0 and person.moving and person.down_time <= 0:
            for puddle in self.puddles:
                if math.hypot(person.x - puddle.x, person.y - puddle.y) < puddle.radius * 0.8:
                    delta_x, delta_y = person.x - old_position[0], person.y - old_position[1]
                    # ลื่นไปทางที่กำลังเดินด้วยความเร็ว 190 (or 1 กันหารศูนย์)
                    distance = math.hypot(delta_x, delta_y) or 1
                    person.slip_time = 0.45
                    person.slip_immune = 1.2
                    person.slip_velocity = (delta_x / distance * 190, delta_y / distance * 190)
                    person.path = []
                    self.float_text(person.x, person.y, "ลื่น!", ACCENT_COLOR)
                    break

        # เดินผ่านไฟแล้วติดไฟ
        if not person.saved:
            for fire in self.fires:
                if math.hypot(person.x - fire.x, (person.y - fire.y) * 1.3) < fire.radius * 0.7:
                    if person.burn_time <= 0:
                        self.toast(f"{person.information['name']}ติดไฟ!", BAD_COLOR)
                    person.burn_time = max(person.burn_time, 1.2)
                    break

        # ถึงฝั่งปลอดภัย
        if not person.saved and person.y < GOAL_Y - 6:
            person.burn_time = 0
            self.save(person)

    def step_towards(self, person, delta_time, speed_value):
        if not person.path:
            return
        target_x, target_y = person.path[0]
        delta_x = target_x - person.x
        delta_y = target_y - person.y
        distance = math.hypot(delta_x, delta_y)
        # ใกล้จุดหมายกว่าระยะที่เดินได้ในเฟรมนี้ ก็วางลงบนจุดเลย จะได้ไม่เดินเลย
        step = speed_value * delta_time
        if distance <= step:
            self.move_constrained(person, target_x, target_y)
            person.path.pop(0)
        else:
            self.move_constrained(person, person.x + delta_x / distance * step, person.y + delta_y / distance * step)

    # คนลงถนนได้เฉพาะช่วงทางม้าลาย
    def move_constrained(self, person, next_x, next_y):
        next_x = clamp(next_x, 10, SCREEN_WIDTH - 10)
        next_y = clamp(next_y, 16, WORLD_BOTTOM - 10)
        if person.saved:
            person.x, person.y = next_x, min(next_y, GOAL_Y - 8)
            return
        if in_road(next_y):
            if not in_road(person.y) and not in_band(next_x):
                next_y = person.y  # ลงจากขอบทางนอกทางม้าลายไม่ได้
            elif in_road(person.y) and in_band(person.x):
                next_x = clamp(next_x, CROSSING_START_X + 4, CROSSING_END_X - 4)
        person.x, person.y = next_x, next_y

    def save(self, person):
        person.saved = True
        person.is_walking = False
        person.panic = False
        # คนที่ถึงแล้วไปยืนเรียงแถวละ 6
        saved_slot = sum(1 for other_person in self.people if other_person.saved)
        person.path = [(220 + (saved_slot % 6) * 100 + random.uniform(-10, 10), 40 + (saved_slot // 6) * 34)]
        self.float_text(person.x, person.y, "ปลอดภัย!", GOOD_COLOR)
        if person.carrying:
            carried_person = person.carrying
            person.carrying = None
            carried_person.carried_by = None
            carried_person.x, carried_person.y = person.x + 12, person.y
            self.save(carried_person)

    def check_hits(self):
        for car in self.cars:
            if not car.dangerous():
                continue
            for person in self.people:
                if (person.alive and not person.saved and person.carried_by is None and person.invulnerable_time <= 0
                        and car.hits(person.x, person.y, 7)):
                    self.car_hit(person, car)

    def car_hit(self, person, car):
        # ความเสียหายตามความเร็วรถ (0.5–1.4 เท่า) ถ้ารถไถลมาบวกอีก 10
        speed_factor = clamp(car.speed / 180, 0.5, 1.4)
        damage_amount = VEHICLES[car.kind]["damage"] * speed_factor + (10 if car.skid > 0 else 0)
        self.juice(shake_strength=5, hitstop_seconds=0.04)
        self.impact_text(person.x, person.y, "ปั้ก!", (255, 255, 255), 0.7)
        push_velocity = (car.direction * (140 + car.speed * 0.6), random.uniform(-70, 70))
        person.invulnerable_time = 1.6
        if car.skid <= 0:  # คนขับเหยียบเบรก
            car.speed *= 0.3
            car.stall = max(car.stall, 1.0)
        self.damage(person, damage_amount, "car", push_velocity)
        if person.fuel:  # ถังน้ำมันแตก
            person.fuel = False
            self.explode(person.x, person.y)

    def damage(self, person, amount, source, push_velocity=None):
        """source: "car" = โดนรถ, "fire" = ระเบิด, "burn" = ติดไฟ (เรียกทุกเฟรม)"""
        if not person.alive or person.saved:
            return
        person.health -= amount
        if source != "burn":
            person.hurt_time = 0.4
            self.float_text(person.x, person.y, f"-{int(amount)}", BAD_COLOR)
            self.burst(person.x, person.y, 18, 8, speed=(30, 120), rise=(60, 160),
                       colors=[BLOOD, BLOOD_HIGHLIGHT], size=(2, 3), life=0.8)
        if source == "car":
            self.puddles.append(Puddle(person.x, person.y, 15))
        if push_velocity:  # กระเด็นล้ม
            person.slip_time = 0.4
            person.slip_velocity = push_velocity
            person.slip_immune = 1.0
            person.down_time = 1.1
            person.fall_direction = 1 if push_velocity[0] >= 0 else -1
            person.path = []
            person.panic = False
            if person.carrying:
                carried_person = person.carrying
                person.carrying = None
                carried_person.carried_by = None
                carried_person.x = person.x + 14
                carried_person.y = person.y + 8
                carried_person.down_time = 1.0
                carried_person.fall_direction = person.fall_direction
        if person.health <= 0:
            self.die(person, source)
            return
        if source == "car":
            self.toast(f"{person.information['name']}โดนชน!  HP เหลือ {int(person.health)}", BAD_COLOR)
            if person.injured:
                self.float_text(person.x, person.y - 10, "บาดเจ็บหนัก", BAD_COLOR)

    def die(self, person, source):
        person.health = 0
        person.alive = False
        person.is_walking = False
        person.path = []
        person.burn_time = 0
        person.death_time = 0.0
        person.death_cause = "fire" if source in ("fire", "burn") else "car"
        if person.death_cause == "car":
            self.puddles.append(Puddle(person.x, person.y, 26))
            self.toast(f"{person.information['name']}เสียชีวิต", BAD_COLOR)
        else:
            person.charring_level = 1.0
            self.toast(f"{person.information['name']}ถูกไฟคลอกเสียชีวิต", BAD_COLOR)
        if person.carrying:
            carried_person = person.carrying
            person.carrying = None
            carried_person.carried_by = None
            carried_person.x = person.x + 16
            carried_person.y = person.y + 10
        if person.carried_by:
            person.carried_by.carrying = None
            person.carried_by = None
        if person.fuel:
            person.fuel = False
            self.explode(person.x, person.y)

    def explode(self, world_x, world_y, power=1.0):
        is_big = power > 1.2
        self.toast("รถขนน้ำมันระเบิด!" if is_big else "ถังน้ำมันระเบิด!", BAD_COLOR)
        self.fires.append(Fire(world_x, world_y, 58 * power))
        self.juice(shake_strength=16 * power, hitstop_seconds=0.12 * power, flash_intensity=0.6 if is_big else 0.45)
        self.impact_text(world_x, world_y, "ตูม!!", (255, 150, 40), 1.3 * power)
        # วงที่คนโดนจำกัดไว้ 1.35 เท่า ภาพระเบิดยังใหญ่ตาม power
        blast_radius = 90 * min(power, 1.35)
        self.burst(world_x, world_y, 10, int(60 * power), speed=(60, 320), speed_scale=power, rise=(100, 380),
                   colors=[(255, 210, 80), (255, 140, 30), (230, 70, 30), (90, 90, 90)], size=(3, 7), life=(0.6, 1.3))
        for person in self.people:
            distance = math.hypot(person.x - world_x, person.y - world_y)
            if person.alive and not person.saved and distance < blast_radius and person.carried_by is None:
                line_distance = distance or 1
                # ผลักออกจากจุดระเบิด
                push_velocity = ((person.x - world_x) / line_distance * 320, (person.y - world_y) / line_distance * 320)
                person.burn_time = max(person.burn_time, 1.5)
                had_fuel = person.fuel
                person.fuel = False
                # ใกล้จุดระเบิดเสีย 50 ที่ขอบวงเหลือราว 10
                self.damage(person, 10 + 40 * (1 - distance / blast_radius), "fire", push_velocity)
                if had_fuel:
                    self.explode(person.x, person.y)
        for car in list(self.cars):
            if car.towed or car.wreck:
                continue
            distance = math.hypot(car.x - world_x, car.y - world_y)
            if distance < 80 * power:
                self.crash(car)
            elif distance < 140 * power and car.skid <= 0:
                car.skid = 0.6
                car.lateral_speed = (car.y - world_y) / (distance or 1) * 120

    def animate_person(self, person, delta_time):
        """ท่าทาง กะพริบแดง ไฟไหม้ตัว และท่าตาย (ทำทั้งคนเป็นและคนตาย)"""
        person.hurt_time = max(0.0, person.hurt_time - delta_time)
        person.invulnerable_time = max(0.0, person.invulnerable_time - delta_time)
        if person.carried_by:
            body_x, body_y = person.carried_by.x, person.carried_by.y
        else:
            body_x, body_y = person.x, person.y
        if not person.alive:
            person.death_time += delta_time
            person.pose += (math.pi / 2 - person.pose) * min(1.0, delta_time * 6)
            if person.death_cause == "fire" and person.death_time < 3.5 and random.random() < 0.4:
                self.particles.append(Particle(
                    body_x + random.uniform(-12, 12), body_y, 6,
                    velocity_x=random.uniform(-8, 8),
                    velocity_z=random.uniform(20, 40),
                    color=(70, 70, 74), size=random.uniform(3, 6), life=1.4, gravity=-10,
                ))
            return
        is_lying = person.down_time > 0 or person.carried_by is not None
        # pose เป็นเรเดียน 0 = ยืน, π/2 = นอน
        target_pose = math.pi / 2 if is_lying else (0.22 if (person.dash > 0 or person.burn_time > 0) and person.moving else 0.0)
        person.pose += (target_pose - person.pose) * min(1.0, delta_time * (14 if is_lying else 6))
        if person.burn_time > 0 and not person.saved:
            person.burn_time -= delta_time
            person.charring_level = min(1.0, person.charring_level + delta_time * 0.2)
            if random.random() < 0.7:
                self.particles.append(Particle(
                    body_x + random.uniform(-7, 7), body_y + random.uniform(-3, 3), random.uniform(8, 30),
                    velocity_x=random.uniform(-10, 10),
                    velocity_z=random.uniform(40, 80),
                    color=random.choice([(255, 150, 40), (255, 90, 30), (255, 220, 90)]),
                    size=random.uniform(2, 4), life=0.45, gravity=-30,
                ))
            # ไฟลด HP 8 ต่อวินาที
            self.damage(person, 8 * delta_time, "burn")
        elif person.injured and not person.saved:
            person.drip_time -= delta_time
            if person.drip_time <= 0:
                person.drip_time = random.uniform(0.3, 0.7)
                self.particles.append(Particle(body_x + random.uniform(-4, 4), body_y, 14, color=BLOOD, size=2, life=1.2))

    def check_end(self):
        # แพ้เมื่อคนรอด + คนที่ยังช่วยได้ ไม่ถึงเป้า ชนะเมื่อไม่เหลือใครต้องข้าม
        saved_count = sum(person.saved for person in self.people)
        pending_count = sum(person.alive and not person.saved for person in self.people)
        target_count = self.current_level["target"]
        if saved_count + pending_count < target_count:
            self.state = "lose"
        elif pending_count == 0:
            self.state = "win"

    # ------------------------------------------------------------ player commands

    def toast(self, text, color=TEXT_COLOR):
        for toast_item in self.toast_messages:
            if toast_item.text == text:  # ข้อความเดิมซ้ำ ยืดเวลาแทนเพิ่มใหม่
                toast_item.life = 2.4
                return
        self.toast_messages.append(Toast(text, 2.4, color))
        self.toast_messages = self.toast_messages[-3:]

    def float_text(self, world_x, world_y, text, color):
        self.floating_messages.append(FloatingText(world_x, world_y, 40.0, text, 1.2, color))

    # คลิกซ้าย / ปุ่มเลข = เดินหรือหยุด
    def toggle_go(self, person):
        if not person.active:
            return
        person.is_walking = not person.is_walking
        if person.is_walking:
            self.plan_crossing(person)
            self.float_text(person.x, person.y, "ไป!", GOOD_COLOR)
        else:
            person.path = []
            self.float_text(person.x, person.y, "หยุด", ACCENT_COLOR)

    def plan_crossing(self, person):
        """เดินไปฝั่งปลอดภัยผ่านทางม้าลาย"""
        target_x = clamp(person.x, CROSSING_START_X + 14, CROSSING_END_X - 14)
        person.set_target(target_x, GOAL_Y - 30)

    def start_selected_crossing(self):
        # ทุกคนในกลุ่มเริ่มเดินในเฟรมเดียวกัน แต่ละคนใช้ความเร็วของตัวเอง
        self.selection_pending = False
        self.selected_people = {person for person in self.selected_people if person.active}
        for person in self.people:
            if person in self.selected_people:
                person.is_walking = True
                self.plan_crossing(person)
        if self.selected_people:
            self.toast(f"กลุ่ม {len(self.selected_people)} คนเริ่มข้าม!", GOOD_COLOR)

    def set_all(self, should_walk):
        for person in self.people:
            if person.active and person.is_walking != should_walk:
                person.is_walking = should_walk
                if should_walk:
                    self.plan_crossing(person)
                else:
                    person.path = []
        self.toast("ทุกคนเดิน!" if should_walk else "ทุกคนหยุด!", GOOD_COLOR if should_walk else ACCENT_COLOR)

    def use_ability(self, person):
        if not person.active or person.down_time > 0:
            return
        if person.cooldown > 0:
            self.float_text(person.x, person.y, f"รอ {person.cooldown:0.0f} วิ", MUTED_COLOR)
            return

        person_kind = person.kind
        if person_kind == "warden":
            lane = lane_of(person.y)
            if lane is None:
                lane = LANES - 1 if person.y >= ROAD_BOTTOM else 0
            # ป้ายหยุดเลนที่ยืนอยู่ และเลนถัดไปทางฝั่งปลอดภัย 3 วินาที
            target_lanes = [lane] + ([lane - 1] if lane > 0 and person.y < ROAD_BOTTOM else [])
            for lane_index in target_lanes:
                self.lane_freeze_timers[lane_index] = 3.0
            person.sign_time = 3.0
            person.cooldown = person.information["cooldown"]
            self.toast("ตำรวจจราจรยกป้ายหยุด · เลน " + ", ".join(str(lane_index + 1) for lane_index in sorted(target_lanes)), ACCENT_COLOR)
        elif person_kind == "runner":
            person.dash = 1.4
            person.cooldown = person.information["cooldown"]
            if not person.is_walking:
                person.is_walking = True
                self.plan_crossing(person)
            self.float_text(person.x, person.y, "วิ่ง!", GOOD_COLOR)
        elif person_kind == "strong":
            person.cooldown = person.information["cooldown"]
            if person.carrying:
                carried_person = person.carrying
                carried_person.carried_by = None
                person.carrying = None
                carried_person.x = person.x + 14
                carried_person.y = person.y + 4
                carried_person.path = []
                carried_person.is_walking = False
                self.float_text(person.x, person.y, "วางลง", TEXT_COLOR)
            else:
                candidates = [
                    other_person for other_person in self.people
                    if other_person is not person and other_person.active and other_person.carrying is None
                    and math.hypot(other_person.x - person.x, other_person.y - person.y) < 60
                ]
                if candidates:
                    carried_person = min(candidates, key=lambda other: math.hypot(other.x - person.x, other.y - person.y))
                    carried_person.carried_by = person
                    carried_person.down_time = 0
                    carried_person.path = []
                    carried_person.is_walking = False
                    carried_person.panic = False
                    person.carrying = carried_person
                    self.float_text(person.x, person.y, f"แบก{carried_person.information['name']}", TEXT_COLOR)
                else:
                    self.float_text(person.x, person.y, "ไม่มีใครอยู่ใกล้", MUTED_COLOR)
        else:
            self.float_text(person.x, person.y, "ความสามารถติดตัว", MUTED_COLOR)
