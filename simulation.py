"""Simulation, collision, and outcome rules for Cross the Road.

GameSimulation mutates the Game state supplied by the coordinator. Rendering and
input stay out of this module so frame rules can be read top-to-bottom here.
"""

import math
import random

import pygame

from entities import Car, Drone, Fire, Particle, Puddle
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
    ROAD_BOTTOM,
    ROAD_TOP,
    SCREEN_WIDTH,
    VEHICLES,
    WORLD_BOTTOM,
)
from geometry import clamp, in_band, in_road, lane_center, local, project, shade


class GameSimulation:
    # One simulation frame: update traffic and animation, then active gameplay, then temporary effects.
    # delta_time is elapsed seconds; speed * delta_time gives movement for this frame.
    # ระยะที่เคลื่อนในเฟรมนี้ = ความเร็ว × เวลาที่ผ่านไป เช่น 60 หน่วย/วินาที × 1/60 วินาที = 1 หน่วย
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
        else:
            self.end_screen_timer += delta_time

        for puddle in self.blood_puddles:
            puddle.life -= delta_time
        self.blood_puddles = [puddle for puddle in self.blood_puddles if puddle.life > 0]

        for fire in self.fires:
            fire.life -= delta_time
            if random.random() < 0.6:
                angle = random.uniform(0, math.tau)
                radius = random.uniform(0, fire.radius * 0.8)
                self.particles.append(Particle(
                    fire.x + math.cos(angle) * radius,
                    fire.y + math.sin(angle) * radius * 0.6,
                    4,
                    0,
                    0,
                    random.uniform(40, 90),
                    random.choice([(255, 150, 40), (255, 90, 30), (255, 210, 80)]),
                    random.uniform(2, 4),
                    0.6,
                    gravity=-20
                ))
        self.fires = [fire for fire in self.fires if fire.life > 0]

        for particle in self.particles:
            particle.life -= delta_time
            # Euler integration: position += velocity * time, then vertical velocity -= gravity * time.
            # อัปเดตตำแหน่งจากความเร็วก่อน แล้วปรับความเร็วแนวดิ่งด้วยแรงโน้มถ่วง
            particle.x += particle.velocity_x * delta_time
            particle.y += particle.velocity_y * delta_time
            particle.z += particle.velocity_z * delta_time
            particle.velocity_z -= particle.gravity * delta_time
            particle.angle += particle.spin * delta_time
            if particle.z < 0:
                if particle.shape != "dot" and particle.velocity_z < -90:      # car parts bounce
                    # Reverse the downward velocity and keep 40% for a smaller bounce; reduce horizontal motion too.
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
            impact_message[3] -= delta_time
        self.impact_messages = [impact_message for impact_message in self.impact_messages if impact_message[3] > 0]

        self.skid_mark_fade_timer += delta_time
        if self.skid_mark_fade_timer > 0.5:                      # skid marks slowly fade away
            self.skid_mark_fade_timer = 0
            # Multiplicative fading scales alpha by 246/255 every half-second while keeping the color channels unchanged.
            self.skid_mark_surface.fill((255, 255, 255, 246), special_flags=pygame.BLEND_RGBA_MULT)

        for floater in self.floating_messages:
            floater[4] -= delta_time
            if floater[3]:
                floater[2] += 30 * delta_time
        self.floating_messages = [floater for floater in self.floating_messages if floater[4] > 0]

        for toast_entry in self.toast_messages:
            toast_entry[1] -= delta_time
        self.toast_messages = [toast_entry for toast_entry in self.toast_messages if toast_entry[1] > 0]

    def update_traffic(self, delta_time, pre_warm=False):
        level_settings = self.current_level
        for lane_index in range(LANES):
            self.lane_freeze_timers[lane_index] = max(0.0, self.lane_freeze_timers[lane_index] - delta_time)
            self.spawn_timers[lane_index] -= delta_time
            if self.spawn_timers[lane_index] <= 0:
                # Weighted selection: chance of a kind = its mix weight / sum of all mix weights.
                # โอกาสสุ่มรถแต่ละชนิด = น้ำหนักของชนิดนั้น / ผลรวมน้ำหนักรถทั้งหมด
                vehicle_kind = random.choices(list(level_settings["mix"]), weights=list(level_settings["mix"].values()))[0]
                new_car = Car(lane_index, vehicle_kind, level_settings)
                # A new vehicle needs center separation >= half both lengths + 40 units of entry clearance.
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
                continue                                  # the drone moves it
            if car.wreck:
                car.wreck_time += delta_time
                if car.fuse > 0:
                    car.fuse -= delta_time
                    if random.random() < 0.6:            # leaking fuel sparks
                        self.particles.append(Particle(
                            car.x + random.uniform(-car.length / 3, car.length / 3),
                            car.y,
                            8,
                            random.uniform(-40, 40),
                            random.uniform(-20, 20),
                            random.uniform(60, 140),
                            random.choice([(255, 200, 60), (255, 120, 30)]),
                            2,
                            0.4
                        ))
                    if car.fuse <= 0:
                        car.burnt = True
                        car.color = (52, 48, 46)
                        self.explode(car.x, car.y, power=1.8)
                if random.random() < 0.25:
                    self.particles.append(Particle(
                        car.x + random.uniform(-car.length / 4, car.length / 4),
                        car.y,
                        car.height,
                        random.uniform(-6, 6),
                        0,
                        random.uniform(25, 45),
                        random.choice([(80, 80, 84), (110, 110, 114)]),
                        random.uniform(3, 6),
                        1.6,
                        gravity=-8
                    ))
                continue

            if car.skid > 0:
                # sliding sideways on blood: keeps going forward, drifts into the next lane
                car.skid -= delta_time
                car.speed *= (1 - 0.5 * delta_time)
                car.y = clamp(car.y + car.lateral_speed * delta_time, ROAD_TOP + car.width / 2 + 2, ROAD_BOTTOM - car.width / 2 - 2)
                wobble = math.sin(car.skid * 18) * 0.08
                # atan2(sideways_speed, forward_speed) turns the car toward its movement; sine adds skid wobble.
                car.heading = math.atan2(car.lateral_speed * 0.6, car.direction * max(car.speed, 1)) + wobble
                if car.skid <= 0:
                    car.lateral_speed = 0
                    # Bitwise XOR with 1 swaps paired lanes: 0 <-> 1 and 2 <-> 3. Choose the closer lane center.
                    # XOR ด้วย 1 ใช้สลับเลนคู่กัน เช่น 0 กับ 1 และ 2 กับ 3 แล้วเลือกเลนที่อยู่ใกล้กว่า
                    car.lane = min((car.lane, car.lane ^ 1), key=lambda lane_index: abs(lane_center(lane_index) - car.y))
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
                        # Multiply by direction so a positive distance always means ahead, even for left-moving cars.
                        distance_ahead = (other_car.x - car.x) * car.direction
                        if distance_ahead > 0:
                            # Front-to-back clearance = center distance - half the combined vehicle lengths.
                            gap_distance = distance_ahead - (other_car.length + car.length) / 2
                            if gap_distance < gap:
                                ahead_car, gap = other_car, gap_distance
                    if ahead_car:
                        # Braking formula d = v^2 / (2*a), using deceleration 480, plus a 16-unit safety margin.
                        # ระยะเบรกใช้สูตร v² / (2a): รถเร็วขึ้นสองเท่าจะต้องใช้ระยะเบรกสี่เท่า เมื่อความหน่วงเท่าเดิม
                        stop_distance = car.speed * car.speed / (2 * 480) + 16      # distance needed to stop
                        if gap < stop_distance + 30:
                            target_speed = min(target_speed, 0 if (gap < stop_distance or ahead_car.wreck) else ahead_car.speed * 0.9)
                # Approach target speed with a per-frame acceleration limit; braking is stronger than acceleration.
                speed_delta = target_speed - car.speed
                rate = 520 if speed_delta < 0 else 200
                car.speed += clamp(speed_delta, -rate * delta_time, rate * delta_time)
                # ease back into the lane and point straight again
                # Easing formula: current += (target - current) * fraction. Capping the fraction prevents overshoot.
                # นำระยะที่ยังห่างจากเป้าหมายมาคูณสัดส่วน แล้วบวกกลับเข้าตำแหน่งปัจจุบัน
                car.y += (lane_center(car.lane) - car.y) * min(1.0, 2.5 * delta_time)
                car.heading += (car.base_angle - car.heading) * min(1.0, 4 * delta_time)
            car.x += car.direction * car.speed * delta_time
            if (car.skid > 0 or (car.stall > 0 and car.speed > 30)) and not pre_warm:
                self.skid_marks(car)
            else:
                car.skid_points = None

            # slippery blood
            if car.skid <= 0 and car.speed > 40:
                for puddle in self.blood_puddles:
                    if id(car) in puddle.hit_car_identifiers:
                        continue
                    if math.hypot(car.x - puddle.x, car.y - puddle.y) < puddle.radius + car.width * 0.45:
                        puddle.hit_car_identifiers.add(id(car))
                        if puddle.radius < 20 and random.random() < 0.6:
                            continue              # small puddles only sometimes make a car slide
                        car.skid = 0.9
                        other_lane = car.lane ^ 1
                        # Sideways speed = distance to the paired lane / skid duration, with a small random multiplier.
                        car.lateral_speed = (lane_center(other_lane) - car.y) / 0.9 * random.uniform(0.8, 1.15)
                        self.float_text(car.x, car.y, "ลื่น!", ACCENT_COLOR)
                        if not pre_warm:
                            self.toast("รถลื่นคราบเลือด!", ACCENT_COLOR)
                        break

        # crashes between cars
        for first_index, first_car in enumerate(active_road_cars):
            # Compare each car pair once by taking only cars after the current index.
            # ตรวจรถแต่ละคู่ครั้งเดียว เช่น ตรวจคู่ A-B แล้วไม่ต้องตรวจ B-A ซ้ำ
            for second_car in active_road_cars[first_index + 1:]:
                if first_car.wreck and second_car.wreck:
                    continue
                if first_car.skid <= 0 and second_car.skid <= 0:
                    continue                      # normal traffic keeps its distance; only skids crash
                if (abs(first_car.x - second_car.x) < (first_car.length + second_car.length) / 2 - 6 and abs(first_car.y - second_car.y) < (first_car.width + second_car.width) / 2 - 4):
                    self.crash(first_car, second_car)

        for drone in self.drones:
            drone.update(delta_time)
        done_car_identifiers = {id(drone.car) for drone in self.drones if drone.done}
        self.drones = [drone for drone in self.drones if not drone.done]
        self.cars = [
            car for car in self.cars
            if id(car) not in done_car_identifiers and (car.wreck or car.towed or -car.length * 2 < car.x < SCREEN_WIDTH + car.length * 2)
        ]

    # Combine impact effects by taking the strongest active value, so weaker hits do not cancel stronger ones.
    def juice(self, shake_strength=0.0, hitstop_seconds=0.0, flash_intensity=0.0):
        self.active_surface_shake_strength = max(self.active_surface_shake_strength, shake_strength)
        self.hitstop_remaining = max(self.hitstop_remaining, hitstop_seconds)
        self.flash_intensity = max(self.flash_intensity, flash_intensity)
