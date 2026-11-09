"""วาดเกมลงจอ (presentation layer)

GameRenderer อ่านสถานะจาก Game แล้ววาดอย่างเดียว ไม่ขยับสิ่งของในเกมและไม่รับ input
ลำดับการวาด 1 เฟรมดูได้ที่ draw() ด้านล่าง
"""

import math
import random

import pygame

from fonts import load_font
from game_config import (
    ACCENT_COLOR,
    BACKGROUND_COLOR,
    BAD_COLOR,
    BLOOD_HIGHLIGHT,
    GLASS_COLOR,
    GOOD_COLOR,
    HEADS_UP_DISPLAY_Y,
    LANE_HEIGHT,
    MUTED_COLOR,
    PANEL_2_COLOR,
    PANEL_COLOR,
    ROAD_TOP,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SKIN_COLOR,
    TEXT_COLOR,
    VERTICAL_SCALE,
    WHITE,
)
from geometry import box_corners, draw_box, local, mix, project, shade

TIRE_COLOR = (26, 26, 30)
HELMET_COLOR = (240, 240, 240)
HELMET_EDGE_COLOR = (60, 60, 70)
BURNT_COLOR = (34, 28, 26)


def health_color(fraction):
    """สีแถบเลือด: เขียว > 60%, เหลือง > 40%, ที่เหลือแดง"""
    if fraction > 0.6:
        return GOOD_COLOR
    if fraction > 0.4:
        return ACCENT_COLOR
    return BAD_COLOR


def star_points(center_x, center_y, outer_radius=16, inner_radius=7):
    """ดาวห้าแฉก = 10 จุด สลับรัศมียาว (ปลายแฉก) กับสั้น (ร่อง) ทุก ๆ 36 องศา"""
    points = []
    for vertex in range(10):
        radius = outer_radius if vertex % 2 == 0 else inner_radius
        angle = -math.pi / 2 + vertex * math.pi / 5
        points.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)))
    return points


class PersonPose:
    """ตำแหน่งและท่าทางของคนหนึ่งคนในเฟรมนี้

    ทริกหลัก: อวัยวะทุกส่วนวางบน "แกนลำตัว" ที่เอียงได้ด้วยมุม pose
    pose = 0 คือยืน (ความสูงอยู่แกน z) ส่วน pose = pi/2 คือนอน (ความสูงกลายเป็นระยะแนวนอน)
    โค้ดชุดเดียวจึงวาดได้ทั้งยืน เดิน ล้ม นอน ถูกแบก และตาย
    """

    def __init__(self, person, carrier):
        if carrier:
            self.base_x, self.base_y, self.base_z = carrier.x + 2, carrier.y, 30
        else:
            self.base_x, self.base_y, self.base_z = person.x, person.y, 0
        self.scale = 0.76 if person.kind == "kid" else 1.0

        self.body_color = mix(person.information["color"], BURNT_COLOR, person.charring_level)
        self.skin_color = mix(SKIN_COLOR, (44, 34, 30), person.charring_level)
        if person.hurt_time > 0 and int(person.hurt_time * 18) % 2 == 0:     # กะพริบแดงตอนโดนชน
            self.body_color = mix(self.body_color, (255, 80, 70), 0.65)
            self.skin_color = mix(self.skin_color, (255, 80, 70), 0.65)

        angle = math.pi / 2 if carrier else person.pose
        self.is_lying = angle > 0.6
        self.facing = person.fall_direction if self.is_lying else person.facing
        self.is_alive = person.alive and not self.is_lying and not carrier
        self.is_moving = self.is_alive and person.moving

        # เดิน: |sin| ทำให้ตัวเด้งขึ้นลง ส่วน sin ที่มีเครื่องหมายทำให้ขาซ้ายขวาแกว่งสลับกัน
        phase = person.walk_phase * 10
        if self.is_moving and person.injured:                                # เดินกะเผลก
            self.bob = max(0.0, math.sin(phase)) * 4
        else:
            self.bob = abs(math.sin(phase)) * 2 if self.is_moving else 0
        self.swing = math.sin(phase) * 4 if self.is_moving else 0
        if person.slip_time > 0 and self.is_alive:
            self.swing = 6

        self.sin_pose, self.cos_pose = math.sin(angle), math.cos(angle)
        self.body_width = 18 if person.kind == "strong" else 13 * self.scale

    def point(self, height, offset=0.0):
        """จุดบนจอของตำแหน่งที่สูง height และเยื้องข้าง offset ตามแกนลำตัว"""
        return project(
            self.base_x + self.facing * self.sin_pose * height + offset * self.cos_pose,
            self.base_y + offset * self.sin_pose * 0.6,
            self.base_z + self.cos_pose * (height + self.bob)
        )


class GameRenderer:

    # ================================================================ 1 เฟรม
    def draw(self):
        """วาด 1 เฟรม จากชั้นล่างสุดขึ้นไปชั้นบนสุด"""
        self.active_surface = self.world_canvas
        self.draw_ground_layers()
        self.update_hover()
        self.draw_depth_sorted_objects()
        self.draw_flying_objects()
        self.draw_particles()
        self.draw_floaters()
        self.draw_impacts()
        self.draw_flash()
        self.present_world_with_shake()        # จากนี้ไปวาดลงจอจริง จึงไม่สั่นตาม
        self.draw_toasts()
        self.draw_heads_up_display()
        self.draw_overlay_card()
        pygame.display.flip()

    def hovered_person(self):
        return getattr(self, "hover", None)

    def render_cache(self):
        """ของที่หน้าตาไม่เปลี่ยน สร้างครั้งเดียวแล้วเก็บไว้ใช้ซ้ำทุกเฟรม"""
        return self.__dict__.setdefault("_render_cache", {})

    def update_hover(self):
        # คำนวณหลัง draw_decals() วงขาวใต้เท้าจึงตามเมาส์ช้าไป 1 เฟรม (พฤติกรรมเดิม)
        mouse_x, mouse_y = pygame.mouse.get_pos()
        over_world = self.state == "play" and mouse_y < HEADS_UP_DISPLAY_Y
        self.hover = self.person_at(mouse_x, mouse_y) if over_world else None

    # ================================================================ ชั้นพื้น
    def draw_ground_layers(self):
        surface = self.world_canvas
        surface.blit(self.ground_surface, (0, 0))       # ถนนวาดไว้ครั้งเดียวตอนเริ่มด่าน
        surface.blit(self.skid_mark_surface, (0, 0))    # รอยล้อสะสมไว้ ไม่ล้างทุกเฟรม
        self.draw_decals()
        surface.blit(self.decal_surface, (0, 0))
        self.draw_frozen_lanes()

    def draw_decals(self):
        """ของที่แปะอยู่บนพื้น: คราบเลือด รอยไหม้ เงา และวงบอกสถานะใต้เท้า"""
        decal_surface = self.decal_surface
        decal_surface.fill((0, 0, 0, 0))

        for puddle in self.blood_puddles:
            alpha = int(220 * min(1.0, puddle.life / 3.0))     # จางลงใน 3 วินาทีสุดท้าย
            for blob_x, blob_y, radius in puddle.blobs:
                center_x, center_y = project(puddle.x + blob_x, puddle.y + blob_y)
                pygame.draw.ellipse(
                    decal_surface, (*puddle.color, alpha),
                    (center_x - radius, center_y - radius * VERTICAL_SCALE, radius * 2, radius * 2 * VERTICAL_SCALE)
                )
            center_x, center_y = project(puddle.x - puddle.radius * 0.2, puddle.y - puddle.radius * 0.2)
            pygame.draw.ellipse(decal_surface, (*puddle.highlight_color, alpha // 2), (center_x - 6, center_y - 3, 12, 5))

        for fire in self.fires:
            center_x, center_y = project(fire.x, fire.y)
            squash = VERTICAL_SCALE * 0.75
            pygame.draw.ellipse(
                decal_surface, (20, 16, 14, 170),
                (center_x - fire.radius, center_y - fire.radius * squash, fire.radius * 2, fire.radius * 2 * squash)
            )

        for car in self.cars:
            shadow = box_corners(car.x + 5, car.y + 7, car.length, car.width, car.angle)
            pygame.draw.polygon(decal_surface, (0, 0, 0, 70 if car.lift < 5 else 40), [project(*corner) for corner in shadow])

        for drone in self.drones:
            center_x, center_y = project(drone.x, drone.y)
            pygame.draw.ellipse(decal_surface, (0, 0, 0, 50), (center_x - 26, center_y - 9, 52, 18))

        hover_person = self.hovered_person()
        for person in self.people:
            if not person.alive or person.carried_by:
                continue
            center_x, center_y = project(person.x + 2, person.y + 2)
            pygame.draw.ellipse(decal_surface, (0, 0, 0, 80), (center_x - 10, center_y - 4, 20, 8))
            center_x, center_y = project(person.x, person.y)
            if person.active and person in self.selected_people:              # ทอง = อยู่ในกลุ่ม Shift
                pygame.draw.ellipse(decal_surface, (*ACCENT_COLOR, 240), (center_x - 20, center_y - 10, 40, 20), 3)
            if person is hover_person:                                         # ขาว = เมาส์ชี้อยู่
                pygame.draw.ellipse(decal_surface, (255, 255, 255, 200), (center_x - 16, center_y - 8, 32, 16), 2)
            if person.is_walking and not person.saved:                         # เขียว = กำลังเดิน
                pygame.draw.ellipse(decal_surface, (*GOOD_COLOR, 200), (center_x - 13, center_y - 6, 26, 12), 2)

    def draw_frozen_lanes(self):
        """เลนที่ตำรวจยกป้ายหยุด ทาแดงโปร่ง ๆ แล้วจางลงในวินาทีสุดท้าย"""
        overlay = self.overlay_surface
        overlay.fill((0, 0, 0, 0))
        any_frozen = False
        for lane_index, freeze_time in enumerate(self.lane_freeze_timers):
            if freeze_time <= 0:
                continue
            any_frozen = True
            top = ROAD_TOP + LANE_HEIGHT * lane_index
            bottom = top + LANE_HEIGHT
            alpha = int(60 * min(1.0, freeze_time))
            corners = [project(0, top), project(SCREEN_WIDTH, top), project(SCREEN_WIDTH, bottom), project(0, bottom)]
            pygame.draw.polygon(overlay, (230, 60, 50, alpha), corners)
        if any_frozen:
            self.active_surface.blit(overlay, (0, 0))

    # ================================================================ ของที่บังกันได้
    def draw_depth_sorted_objects(self):
        """Painter's algorithm: เรียงตาม y แล้ววาดจากไกล (y น้อย) มาใกล้ ของที่ใกล้จึงทับของที่ไกล"""
        items = []
        for car in self.cars:
            if not car.towed:
                items.append((car.depth(), self.draw_car, car))
        for person in self.people:
            if person.alive and person.carried_by is None:
                items.append((person.y, self.draw_person_with_load, person))
            elif not person.alive and person.death_time < 10:
                items.append((person.y - 0.5, self.draw_person_with_load, person))   # ศพอยู่ใต้คนยืนจุดเดียวกัน
        for fire in self.fires:
            items.append((fire.y + 1, self.draw_fire, fire))

        items.sort(key=lambda item: item[0])
        for _, draw_function, entity in items:
            draw_function(entity)

    def draw_person_with_load(self, person):
        self.draw_person(person)
        if person.carrying:
            self.draw_person(person.carrying, carrier=person)

    def draw_flying_objects(self):
        """รถที่ถูกยกกับโดรนลอยอยู่เหนือทุกอย่าง จึงวาดหลังสุดโดยไม่ต้องเรียงกับของบนพื้น"""
        for car in self.cars:
            if car.towed:
                self.draw_car(car)
        for drone in sorted(self.drones, key=lambda drone: drone.y):
            self.draw_drone(drone)

    # ================================================================ รถ
    def draw_car(self, car):
        """รถประกอบจากกล่องหลายชิ้น ตำแหน่งทุกชิ้นอ้างอิงจุดกลางรถผ่าน local()
        รถหมุน ทุกชิ้นก็หมุนตาม และ lift ยกทั้งคันขึ้นตอนโดรนยก"""
        if car.kind == "sidecar":
            self.draw_sidecar(car)
            return
        if car.kind == "moto":
            self.draw_moto(car)
            return

        self.draw_wheels(car, (-car.length * 0.32, car.length * 0.32))
        if car.kind == "tanker":
            self.draw_tanker(car)
        elif car.kind == "icecream":
            self.draw_icecream_van(car)
        elif car.kind == "truck":
            self.draw_truck(car)
        else:
            self.draw_sedan(car)

        if car.wreck:
            self.draw_dents(car)
        else:
            self.draw_lights(car)

    @staticmethod
    def glass_color(car):
        return (40, 46, 52) if car.wreck else GLASS_COLOR

    @staticmethod
    def camera_side(car):
        """ด้านของรถที่หันเข้ากล้อง (+1 หรือ -1) ใช้วางลายข้างรถให้อยู่ฝั่งที่มองเห็น"""
        return 1 if car.direction > 0 else -1

    def draw_wheels(self, car, offsets_along):
        for along in offsets_along:
            for across in (-car.width / 2 + 3, car.width / 2 - 3):
                wheel_x, wheel_y = local(car.x, car.y, car.angle, along, across)
                draw_box(self.active_surface, wheel_x, wheel_y, 15, 6, car.lift, car.lift + 10, car.angle, TIRE_COLOR, outline=False)

    def draw_rider(self, car, across):
        surface, angle, lift = self.active_surface, car.angle, car.lift
        rider_x, rider_y = local(car.x, car.y, angle, -3, across)
        draw_box(surface, rider_x, rider_y, 11, 10, lift + 15, lift + 32, angle, car.rider_color)
        helmet = project(*local(car.x, car.y, angle, -1, across), lift + 38)
        pygame.draw.circle(surface, HELMET_COLOR, helmet, 6)
        pygame.draw.circle(surface, HELMET_EDGE_COLOR, helmet, 6, 1)

    def draw_moto(self, car):
        draw_box(self.active_surface, car.x, car.y, car.length, car.width * 0.6, car.lift + 4, car.lift + 15, car.angle, car.color)
        if not car.wreck:
            self.draw_rider(car, 0)

    def draw_sidecar(self, car):
        """มอเตอร์ไซค์พ่วงข้าง: รถพ่วงอยู่ฝั่งกล้อง ตัวรถอยู่อีกฝั่ง"""
        surface, angle, lift = self.active_surface, car.angle, car.lift
        side = 9 * self.camera_side(car)

        tub_x, tub_y = local(car.x, car.y, angle, -2, side)
        draw_box(surface, tub_x, tub_y, 14, 6, lift, lift + 9, angle, TIRE_COLOR, outline=False)     # ล้อรถพ่วง
        draw_box(surface, tub_x, tub_y, 32, 18, lift + 6, lift + 17, angle, car.color)                # ตัวรถพ่วง
        nose = [project(*local(car.x, car.y, angle, 12, side + offset), lift + 17) for offset in (-9, 9)]
        nose.append(project(*local(car.x, car.y, angle, 18, side), lift + 21))
        pygame.draw.polygon(surface, shade(car.color, 1.25), nose)
        if not car.wreck:
            self.draw_sidecar_cargo(car, side)

        bike_x, bike_y = local(car.x, car.y, angle, 0, -side)
        draw_box(surface, bike_x, bike_y, 38, 9, lift + 4, lift + 15, angle, (40, 40, 46))
        if not car.wreck:
            self.draw_rider(car, -side)

    def draw_sidecar_cargo(self, car, side):
        surface, angle, lift = self.active_surface, car.angle, car.lift
        if car.cargo == "passenger":
            passenger_x, passenger_y = local(car.x, car.y, angle, -4, side)
            draw_box(surface, passenger_x, passenger_y, 9, 9, lift + 17, lift + 28, angle, (210, 120, 60))
            pygame.draw.circle(surface, SKIN_COLOR, project(passenger_x, passenger_y, lift + 33), 5)
        elif car.cargo == "crates":
            for index, along in enumerate((-8, 4)):
                crate_x, crate_y = local(car.x, car.y, angle, along, side)
                draw_box(surface, crate_x, crate_y, 10, 12, lift + 17, lift + 26 + index * 4, angle, (176, 130, 76))
        else:
            for along in (-10, -4, 2, 8):
                bottle_x, bottle_y = local(car.x, car.y, angle, along, side)
                draw_box(surface, bottle_x, bottle_y, 4, 4, lift + 17, lift + 29, angle, (90, 170, 110), outline=False)

    def draw_cab(self, car, cab_color, cab_along, cab_length, glass_along, glass_length):
        """หัวรถ (ห้องคนขับ + กระจกหน้า) ใช้ร่วมกันระหว่างรถบรรทุกกับรถน้ำมัน"""
        surface, angle, lift, height = self.active_surface, car.angle, car.lift, car.height
        cab_x, cab_y = local(car.x, car.y, angle, car.length * cab_along, 0)
        draw_box(surface, cab_x, cab_y, car.length * cab_length, car.width * 0.94, lift + 6, lift + height * 0.72, angle, cab_color)
        glass_x, glass_y = local(car.x, car.y, angle, car.length * glass_along, 0)
        draw_box(surface, glass_x, glass_y, car.length * glass_length, car.width * 0.8, lift + height * 0.42, lift + height * 0.7,
                 angle, self.glass_color(car), top_color=shade(cab_color, 1.1), outline=False)

    def draw_tanker(self, car):
        """รถน้ำมัน: หัวแดง ถังเงิน มีป้ายวัตถุอันตราย"""
        surface, angle, lift, height = self.active_surface, car.angle, car.lift, car.height
        side = car.width * 0.45 * self.camera_side(car)
        self.draw_wheels(car, (-car.length * 0.1, car.length * 0.08))                   # ล้อคู่กลาง
        cab_color = (52, 48, 46) if car.burnt else (200, 50, 40)
        self.draw_cab(car, cab_color, 0.39, 0.2, 0.45, 0.08)

        tank_x, tank_y = local(car.x, car.y, angle, -car.length * 0.12, 0)
        draw_box(surface, tank_x, tank_y, car.length * 0.7, car.width * 0.4, lift + 6, lift + 12, angle, (40, 40, 44), outline=False)
        draw_box(surface, tank_x, tank_y, car.length * 0.7, car.width * 0.9, lift + 12, lift + height, angle, car.color, top_color=shade(car.color, 1.08))
        for along in (-car.length * 0.38, -car.length * 0.12, car.length * 0.14):       # เส้นแบ่งถัง
            rib_x, rib_y = local(car.x, car.y, angle, along, side)
            pygame.draw.line(surface, shade(car.color, 0.7), project(rib_x, rib_y, lift + 12), project(rib_x, rib_y, lift + height), 2)

        if not car.burnt:
            stripe_z = lift + height * 0.35
            stripe_start = project(*local(car.x, car.y, angle, -car.length * 0.46, side), stripe_z)
            stripe_end = project(*local(car.x, car.y, angle, car.length * 0.22, side), stripe_z)
            pygame.draw.line(surface, (240, 140, 30), stripe_start, stripe_end, 3)
            sign_x, sign_y = project(*local(car.x, car.y, angle, -car.length * 0.12, side), lift + height * 0.62)
            diamond = [(sign_x, sign_y - 8), (sign_x + 8, sign_y), (sign_x, sign_y + 8), (sign_x - 8, sign_y)]
            pygame.draw.polygon(surface, (230, 60, 40), diamond)
            pygame.draw.polygon(surface, WHITE, diamond, 1)

        if car.fuse > 0 and int(car.fuse * 12) % 2 == 0:                                 # กำลังจะระเบิด: "!" กะพริบ
            warning = self.font_bold.render("!", True, BAD_COLOR)
            surface.blit(warning, warning.get_rect(center=project(car.x, car.y, lift + height + 22)))

    def draw_icecream_van(self, car):
        """รถไอติม: ตัวรถสีพาสเทล กันสาดลายทาง มีโคนยักษ์บนหลังคา"""
        surface, angle, lift, height = self.active_surface, car.angle, car.lift, car.height
        cream = (250, 250, 246)
        draw_box(surface, car.x, car.y, car.length, car.width, lift + 5, lift + height * 0.8, angle, car.color, top_color=cream)
        glass_x, glass_y = local(car.x, car.y, angle, car.length * 0.4, 0)
        draw_box(surface, glass_x, glass_y, car.length * 0.14, car.width * 0.82, lift + height * 0.35, lift + height * 0.72,
                 angle, self.glass_color(car), top_color=cream, outline=False)

        side = car.width * 0.5 * self.camera_side(car)
        for index in range(5):                                                           # กันสาด 5 ช่อง สลับแดงขาว
            start_along = -car.length * 0.35 + index * car.length * 0.12
            start = local(car.x, car.y, angle, start_along, side)
            end = local(car.x, car.y, angle, start_along + car.length * 0.12, side)
            color = (230, 70, 90) if index % 2 == 0 else cream
            top_z, bottom_z = lift + height * 0.72, lift + height * 0.58
            pygame.draw.polygon(surface, color, [project(*start, top_z), project(*end, top_z), project(*end, bottom_z), project(*start, bottom_z)])

        if not car.wreck:
            cone_x, cone_y = local(car.x, car.y, angle, -car.length * 0.1, 0)
            roof_z = lift + height * 0.8
            cone = [project(cone_x, cone_y, roof_z + 2), project(cone_x - 9, cone_y, roof_z + 24), project(cone_x + 9, cone_y, roof_z + 24)]
            pygame.draw.polygon(surface, (214, 160, 90), cone)
            pygame.draw.polygon(surface, (170, 120, 60), cone, 1)
            scoop_x, scoop_y = project(cone_x, cone_y, roof_z + 30)
            pygame.draw.circle(surface, (250, 180, 205), (scoop_x, scoop_y), 11)
            pygame.draw.circle(surface, (252, 246, 232), (scoop_x - 4, scoop_y - 9), 7)
            pygame.draw.circle(surface, (220, 40, 50), (scoop_x + 2, scoop_y - 16), 3)

    def draw_truck(self, car):
        self.draw_cab(car, car.color, 0.36, 0.26, 0.43, 0.1)
        cargo_x, cargo_y = local(car.x, car.y, car.angle, -car.length * 0.14, 0)
        cargo_color = shade((222, 220, 210), 0.75 if car.wreck else 1)
        draw_box(self.active_surface, cargo_x, cargo_y, car.length * 0.7, car.width, car.lift + 8, car.lift + car.height, car.angle, cargo_color)

    def draw_sedan(self, car):
        surface, angle, lift, height = self.active_surface, car.angle, car.lift, car.height
        draw_box(surface, car.x, car.y, car.length, car.width, lift + 5, lift + height * 0.52, angle, car.color)
        cabin_x, cabin_y = local(car.x, car.y, angle, -car.length * 0.06, 0)
        roof = height * (0.85 if car.wreck else 1.0)                                     # ซากรถหลังคายุบ
        draw_box(surface, cabin_x, cabin_y, car.length * 0.5, car.width * 0.84, lift + height * 0.52, lift + roof,
                 angle, self.glass_color(car), top_color=shade(car.color, 1.15))

    def draw_dents(self, car):
        z = car.lift + car.height * 0.52
        for along, across in ((car.length * 0.38, car.width * 0.2), (-car.length * 0.3, -car.width * 0.25), (car.length * 0.1, car.width * 0.3)):
            pygame.draw.circle(self.active_surface, shade(car.color, 0.55), project(*local(car.x, car.y, car.angle, along, across), z), 4)

    def draw_lights(self, car):
        z = car.lift + car.height * 0.33
        for across in (-car.width * 0.3, car.width * 0.3):
            pygame.draw.circle(self.active_surface, (255, 236, 160), project(*local(car.x, car.y, car.angle, car.length / 2, across), z), 3)
            pygame.draw.circle(self.active_surface, (220, 40, 40), project(*local(car.x, car.y, car.angle, -car.length / 2, across), z), 3)

    # ================================================================ โดรน ไฟ อนุภาค
    def draw_drone(self, drone):
        surface = self.active_surface
        time_seconds = pygame.time.get_ticks() / 1000

        if drone.state != "fly":                                   # สลิงหย่อนลงไปเกี่ยวหลังคารถ
            roof_z = drone.car.lift + drone.car.height
            hook_z = drone.z - (drone.z - roof_z) * drone.cable_extension
            hook = project(drone.x, drone.y, hook_z)
            pygame.draw.line(surface, (40, 40, 44), project(drone.x, drone.y, drone.z), hook, 2)
            pygame.draw.circle(surface, (230, 190, 40), hook, 3)

        for arm_x, arm_y in ((-22, -16), (22, -16), (-22, 16), (22, 16)):
            pygame.draw.line(surface, (50, 52, 58), project(drone.x, drone.y, drone.z + 6), project(drone.x + arm_x, drone.y + arm_y, drone.z + 8), 3)
            rotor_x, rotor_y = project(drone.x + arm_x, drone.y + arm_y, drone.z + 10)
            rotor_width = 16 + 3 * math.sin(time_seconds * 40 + arm_x)              # ความกว้างแกว่ง = ดูเหมือนใบพัดหมุน
            pygame.draw.ellipse(surface, (170, 176, 186), (rotor_x - rotor_width, rotor_y - 3, rotor_width * 2, 6), 1)
            blade = rotor_width * math.cos(time_seconds * 50)
            pygame.draw.line(surface, (90, 94, 100), (rotor_x - blade, rotor_y), (rotor_x + blade, rotor_y), 2)

        draw_box(surface, drone.x, drone.y, 28, 20, drone.z, drone.z + 9, 0, (240, 190, 40))
        draw_box(surface, drone.x, drone.y, 14, 10, drone.z + 9, drone.z + 13, 0, (40, 42, 48))
        if int(time_seconds * 4) % 2 == 0:
            pygame.draw.circle(surface, (255, 60, 50), project(drone.x + 14, drone.y + 10, drone.z + 6), 2)

    def draw_fire(self, fire):
        """เปลวไฟ 9 ลูก เรียงเป็นวง แต่ละลูกสูงต่ำตาม sin ของเวลา ไฟใกล้ดับจะกระพือน้อยลง"""
        surface = self.active_surface
        time_seconds = pygame.time.get_ticks() / 1000
        for index in range(9):
            angle = index * 2.4
            radius = fire.radius * 0.55 * ((index % 3) / 3 + 0.3)
            flame_x = fire.x + math.cos(angle) * radius
            flame_y = fire.y + math.sin(angle) * radius * 0.6
            height = 18 + 10 * math.sin(time_seconds * 9 + index) * min(1.0, fire.life / 2)
            base_x, base_y = project(flame_x, flame_y)
            pygame.draw.polygon(surface, (255, 120, 30), [(base_x - 7, base_y), (base_x + 7, base_y), project(flame_x, flame_y, height + 14)])
            pygame.draw.polygon(surface, (255, 220, 90), [(base_x - 3, base_y), (base_x + 3, base_y), project(flame_x, flame_y, height)])

    def draw_particles(self):
        surface = self.world_canvas
        for particle in self.particles:
            screen_x, screen_y = project(particle.x, particle.y, particle.z)
            if particle.shape == "chunk":                                  # เศษสี่เหลี่ยมหมุนได้
                half_w, half_h = particle.size, particle.size * 0.6
                cos_a, sin_a = math.cos(particle.angle), math.sin(particle.angle)
                points = [(screen_x + dx * cos_a - dy * sin_a, screen_y + dx * sin_a + dy * cos_a)
                          for dx, dy in ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h))]
                pygame.draw.polygon(surface, particle.color, points)
                pygame.draw.polygon(surface, shade(particle.color, 0.5), points, 1)
            elif particle.shape == "wheel":                                # ล้อกลิ้ง มีจุดดุมหมุนตาม
                pygame.draw.circle(surface, particle.color, (screen_x, screen_y), particle.size)
                hub = (screen_x + math.cos(particle.angle) * 2, screen_y + math.sin(particle.angle) * 2)
                pygame.draw.circle(surface, (150, 150, 156), hub, 2)
            else:                                                          # จุด หดลงตามอายุที่เหลือ
                life_left = particle.life / particle.maximum_life
                pygame.draw.circle(surface, particle.color, (screen_x, screen_y), max(1, int(particle.size * (0.5 + life_left * 0.5))))

    # ================================================================ เอฟเฟกต์
    def draw_floaters(self):
        """ข้อความลอยขึ้นเหนือหัว และวงคลื่นตอนคลิก (ข้อความว่าง = วาดวง)"""
        for source_x, source_y, height_z, text, life_time, color in self.floating_messages:
            if not text:
                center_x, center_y = project(source_x, source_y)
                radius = 14 * (1 - life_time / 0.5) + 4
                pygame.draw.ellipse(self.active_surface, color, (center_x - radius, center_y - radius * 0.5, radius * 2, radius), 1)
                continue
            text_surface = self.font_bold.render(text, True, color)
            text_surface.set_alpha(int(255 * min(1.0, life_time / 0.5)))
            self.active_surface.blit(text_surface, text_surface.get_rect(center=project(source_x, source_y, height_z + 20)))

    def draw_impacts(self):
        """คำว่า "ปั้ก!" "โครม!": เด้งใหญ่ตอนแรกแล้วยุบลงเหลือขนาดจริง ลอยขึ้น แล้วจางหาย"""
        if self.font_impact is None:
            self.font_impact = load_font(44, bold=True)
        for source_x, source_y, text, life_time, color, size_scale, rotation, offset_z in self.impact_messages:
            progress = 1 - life_time / 0.9                                    # 0 ตอนเกิด → 1 ตอนหาย
            pop = size_scale * (1.7 - 0.7 * min(1.0, progress * 6))
            label = pygame.transform.rotozoom(self.impact_label(text, color), rotation, pop * 0.6)
            label.set_alpha(int(255 * min(1.0, life_time / 0.3)))
            self.active_surface.blit(label, label.get_rect(center=project(source_x, source_y, 50 + offset_z + progress * 30)))

    def impact_label(self, text, color):
        """ป้ายคำพร้อมขอบดำ 5 ชั้น ทำครั้งเดียวต่อคำต่อสี (ขนาด/การหมุนยังทำใหม่ทุกเฟรมเพราะเปลี่ยนตามเวลา)"""
        cache = self.render_cache()
        key = ("impact", text, color)
        if key not in cache:
            image = self.font_impact.render(text, True, color)
            outline = self.font_impact.render(text, True, (20, 16, 14))
            label = pygame.Surface((image.get_width() + 6, image.get_height() + 6), pygame.SRCALPHA)
            for offset in ((0, 3), (3, 0), (3, 6), (6, 3), (5, 5)):               # ขอบดำหนา ๆ แบบการ์ตูน
                label.blit(outline, offset)
            label.blit(image, (3, 3))
            cache[key] = label
        return cache[key]

    def draw_flash(self):
        if self.flash_intensity > 0:
            self.flash_surface.fill((255, 250, 235, int(170 * self.flash_intensity)))
            self.world_canvas.blit(self.flash_surface, (0, 0))

    def present_world_with_shake(self):
        """โลกถูกวาดบน world_canvas ก่อน แล้วค่อยแปะลงจอโดยเลื่อนแบบสุ่ม = จอสั่น
        HUD วาดหลังขั้นนี้ลงจอโดยตรง จึงนิ่งอยู่กับที่"""
        self.active_surface = self.display_surface
        offset_x = offset_y = 0
        strength = self.active_surface_shake_strength
        if strength > 0.5:
            offset_x = random.uniform(-strength, strength)
            offset_y = random.uniform(-strength, strength) * 0.7
        self.display_surface.fill(BACKGROUND_COLOR)
        self.display_surface.blit(self.world_canvas, (offset_x, offset_y), (0, 0, SCREEN_WIDTH, HEADS_UP_DISPLAY_Y))

    def draw_toasts(self):
        """แถบข้อความแจ้งเตือนกลางจอด้านบน ซ้อนลงมาทีละอัน"""
        y = 64
        for text, life_time, color in self.toast_messages:
            opacity = min(1.0, life_time / 0.4)
            text_surface = self.font_bold.render(text, True, color)
            background = pygame.Surface((text_surface.get_width() + 24, text_surface.get_height() + 8), pygame.SRCALPHA)
            background.fill((15, 17, 22, int(200 * opacity)))
            rectangle = background.get_rect(center=(SCREEN_WIDTH / 2, y))
            self.active_surface.blit(background, rectangle)
            text_surface.set_alpha(int(255 * opacity))
            self.active_surface.blit(text_surface, text_surface.get_rect(center=rectangle.center))
            y += rectangle.height + 4

    # ================================================================ HUD ด้านล่าง
    def roster_rectangles(self):
        """ช่องรายชื่อ 10 คน เรียง 5 คอลัมน์ x 2 แถว (ใช้ทั้งตอนวาดและตอนเช็กเมาส์)"""
        result = []
        for index, person in enumerate(self.people):
            column, row = index % 5, index // 5
            result.append((person, pygame.Rect(250 + column * 54, HEADS_UP_DISPLAY_Y + 14 + row * 60, 50, 54)))
        return result

    def draw_heads_up_display(self):
        surface = self.active_surface
        pygame.draw.rect(surface, PANEL_COLOR, (0, HEADS_UP_DISPLAY_Y, SCREEN_WIDTH, SCREEN_HEIGHT - HEADS_UP_DISPLAY_Y))
        pygame.draw.line(surface, PANEL_2_COLOR, (0, HEADS_UP_DISPLAY_Y), (SCREEN_WIDTH, HEADS_UP_DISPLAY_Y), 2)
        self.draw_level_stats()
        for person, rectangle in self.roster_rectangles():
            self.draw_roster_card(person, rectangle)
        self.draw_person_info()
        self.draw_controls_help()

    def draw_level_stats(self):
        surface, top = self.active_surface, HEADS_UP_DISPLAY_Y
        saved_count = sum(person.saved for person in self.people)
        dead_count = sum(not person.alive for person in self.people)
        target = self.current_level["target"]
        minutes, seconds = divmod(int(self.elapsed_time), 60)
        surface.blit(self.font_bold.render(self.current_level["name"], True, TEXT_COLOR), (18, top + 12))
        surface.blit(self.font_regular.render(f"ข้ามสำเร็จ  {saved_count} / {target}", True, GOOD_COLOR if saved_count >= target else TEXT_COLOR), (18, top + 44))
        surface.blit(self.font_regular.render(f"เสียชีวิต  {dead_count}", True, BAD_COLOR if dead_count else MUTED_COLOR), (18, top + 70))
        surface.blit(self.font_regular.render(f"เวลา  {minutes:02d}:{seconds:02d}", True, MUTED_COLOR), (18, top + 96))

        # แถบความคืบหน้า: เต็มแถบ = รอด 10 คน, ขีดเหลือง = เป้าหมายของด่าน
        bar_x, bar_y, bar_width = 18, top + 124, 200
        pygame.draw.rect(surface, PANEL_2_COLOR, (bar_x, bar_y, bar_width, 8), border_radius=4)
        pygame.draw.rect(surface, GOOD_COLOR, (bar_x, bar_y, bar_width * min(1, saved_count / 10), 8), border_radius=4)
        target_x = bar_x + bar_width * target / 10
        pygame.draw.line(surface, ACCENT_COLOR, (target_x, bar_y - 3), (target_x, bar_y + 11), 2)

    def draw_roster_card(self, person, rectangle):
        surface = self.active_surface
        is_active_walker = person.is_walking and person.active
        pygame.draw.rect(surface, PANEL_2_COLOR, rectangle, border_radius=6)
        if person.active and person in self.selected_people:
            pygame.draw.rect(surface, ACCENT_COLOR, rectangle.inflate(4, 4), 2, border_radius=7)
        if is_active_walker:
            pygame.draw.rect(surface, GOOD_COLOR, rectangle, 2, border_radius=6)
        if person is self.hovered_person():
            pygame.draw.rect(surface, (200, 200, 200), rectangle, 1, border_radius=6)

        # ตัวคนเล็ก ๆ ในช่อง
        body = mix(person.information["color"], BURNT_COLOR, person.charring_level) if person.alive else (70, 70, 76)
        pygame.draw.rect(surface, body, (rectangle.centerx - 7, rectangle.y + 18, 14, 16), border_radius=4)
        pygame.draw.circle(surface, SKIN_COLOR if person.alive else (90, 90, 96), (rectangle.centerx, rectangle.y + 12), 6)
        key_label = self.font_tiny.render(str((person.index + 1) % 10), True, GOOD_COLOR if is_active_walker else MUTED_COLOR)
        surface.blit(key_label, (rectangle.x + 4, rectangle.y + 2))

        if person.alive and not person.saved:
            fraction = max(0.0, person.health / person.maximum_health)
            bar = (rectangle.x + 5, rectangle.y + 37, rectangle.width - 10)
            pygame.draw.rect(surface, (16, 18, 22), (bar[0], bar[1], bar[2], 4))
            pygame.draw.rect(surface, health_color(fraction), (bar[0], bar[1], bar[2] * fraction, 4))
            if person.burn_time > 0:
                pygame.draw.rect(surface, (255, 130, 40), rectangle, 2, border_radius=6)
        if person.fuel:
            pygame.draw.rect(surface, (206, 40, 32), (rectangle.right - 12, rectangle.y + 6, 7, 8))
        name = self.font_tiny.render(person.information["short_name"], True, MUTED_COLOR)
        surface.blit(name, name.get_rect(center=(rectangle.centerx, rectangle.bottom - 8)))

        if person.saved:                                                       # ✓
            pygame.draw.lines(surface, GOOD_COLOR, False, [(rectangle.x + 6, rectangle.y + 10), (rectangle.x + 10, rectangle.y + 14), (rectangle.x + 17, rectangle.y + 5)], 2)
        elif not person.alive:                                                 # ✗
            pygame.draw.line(surface, BAD_COLOR, (rectangle.x + 8, rectangle.y + 8), (rectangle.right - 8, rectangle.y + 40), 3)
            pygame.draw.line(surface, BAD_COLOR, (rectangle.right - 8, rectangle.y + 8), (rectangle.x + 8, rectangle.y + 40), 3)
        elif person.information["cooldown"] > 1 and person.cooldown > 0:      # แถบคูลดาวน์สกิล
            fraction = person.cooldown / person.information["cooldown"]
            pygame.draw.rect(surface, (90, 94, 100), (rectangle.x + 4, rectangle.bottom - 3, (rectangle.width - 8) * fraction, 2))

    def draw_person_info(self):
        """ข้อมูลของคนที่เมาส์ชี้ (บนถนนหรือในช่องรายชื่อ) ถ้าไม่ได้ชี้ใครให้แสดงวิธีเล่นแทน"""
        surface, left, top = self.active_surface, 538, HEADS_UP_DISPLAY_Y
        person = self.hovered_person()
        if person is None:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            person = next((p for p, rect in self.roster_rectangles() if rect.collidepoint(mouse_x, mouse_y)), None)

        if not (person and person.alive):
            surface.blit(self.font_bold.render("คลิกที่คน = เดินข้าม / หยุด", True, ACCENT_COLOR), (left, top + 12))
            surface.blit(self.font_regular.render("คลิกขวาที่คน = ใช้ความสามารถ", True, TEXT_COLOR), (left, top + 40))
            surface.blit(self.font_small.render("ชี้เมาส์ที่คนเพื่อดู HP และความสามารถ", True, MUTED_COLOR), (left, top + 66))
            return

        title = f"{(person.index + 1) % 10}. {person.information['name']}" + ("  · ถังน้ำมัน!" if person.fuel else "")
        surface.blit(self.font_bold.render(title, True, BAD_COLOR if person.fuel else ACCENT_COLOR), (left, top + 12))
        fraction = max(0.0, person.health / person.maximum_health)
        status = f"HP {int(max(0, person.health))}/{person.maximum_health}  ·  {self.person_state_text(person)}"
        surface.blit(self.font_small.render(status, True, health_color(fraction)), (left, top + 40))
        surface.blit(self.font_regular.render(person.information["skill_description"], True, TEXT_COLOR), (left, top + 62))
        if person.information["cooldown"] > 1 and not person.saved:
            ready = person.cooldown <= 0
            text = "คลิกขวา = ใช้ความสามารถ (พร้อม)" if ready else f"ใช้ได้อีกใน {person.cooldown:0.1f} วินาที"
            surface.blit(self.font_small.render(text, True, GOOD_COLOR if ready else MUTED_COLOR), (left + 300, top + 40))

    @staticmethod
    def person_state_text(person):
        if person.fuel:
            return "ปลอดภัยแล้ว" if person.saved else "กำลังไฟไหม้!"
        if person.down_time > 0:
            return "ล้มอยู่"
        if person.injured:
            return "บาดเจ็บหนัก (เดินช้า)"
        if person.is_walking:
            return "กำลังเดิน"
        return "รออยู่"

    def draw_controls_help(self):
        selected_count = sum(person.active for person in self.selected_people)
        lines = ["Shift+คลิก = เลือกกลุ่ม / คลิกซ้ำเอาออก | ปล่อย Shift = เดิน",
                 f"เลือก {selected_count} คน | Esc = ล้าง | G = เดินทุกคน | Space = หยุด | P = พัก | R = ใหม่"]
        for index, line in enumerate(lines):
            self.active_surface.blit(self.font_small.render(line, True, MUTED_COLOR), (538, HEADS_UP_DISPLAY_Y + 104 + index * 20))

    # ================================================================ กล่องกลางจอ
    def draw_overlay_card(self):
        if self.state == "title":
            self.draw_title()
        elif self.state in ("win", "lose"):
            self.draw_end()
        elif self.paused:
            self.center_card(["หยุดชั่วคราว", "กด P เพื่อเล่นต่อ"])

    def center_card(self, lines, supporting_lines=None, width=520):
        """หรี่จอทั้งจอ แล้ววาดกล่องกลางจอ: บรรทัดแรกเป็นหัวข้อ บรรทัดถัดไปเป็นเนื้อหา"""
        surface = self.active_surface
        cache = self.render_cache()
        if "dim" not in cache:                                  # ฉากหรี่จอ สร้างครั้งเดียว
            cache["dim"] = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            cache["dim"].fill((10, 12, 16, 150))
        surface.blit(cache["dim"], (0, 0))

        card_height = 70 + 34 * (len(lines) - 1) + (len(supporting_lines) * 26 + 20 if supporting_lines else 0) + 10
        rectangle = pygame.Rect(0, 0, width, card_height)
        rectangle.center = (SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 40)
        pygame.draw.rect(surface, PANEL_COLOR, rectangle, border_radius=12)
        pygame.draw.rect(surface, PANEL_2_COLOR, rectangle, 2, border_radius=12)

        y = rectangle.y + 24
        for index, line in enumerate(lines):
            is_title = index == 0
            font = self.font_heading if is_title else self.font_regular
            text = font.render(line, True, ACCENT_COLOR if is_title else TEXT_COLOR)
            surface.blit(text, text.get_rect(midtop=(rectangle.centerx, y)))
            y += 44 if is_title else 30
        if supporting_lines:
            y += 8
            for line in supporting_lines:
                surface.blit(self.font_small.render(line, True, MUTED_COLOR), (rectangle.x + 34, y))
                y += 26
        return rectangle

    def draw_title(self):
        self.center_card(
            ["ข้ามถนน", "พาคนข้ามทางม้าลายไปฝั่งปลอดภัยให้ได้มากที่สุด",
             f"ต้องรอดอย่างน้อย {self.current_level['target']} จาก 10 คน"],
            supporting_lines=["ตำรวจจราจร – ยกป้ายหยุดรถทีละเลน",
                              "นักวิ่ง – วิ่งเร็วชั่วครู่      คุณยาย – รถใกล้ ๆ ชะลอ",
                              "เด็ก – อยู่คนเดียวจะตกใจ      คนแข็งแรง – แบกคนอื่นได้",
                              "คนถือถังน้ำมัน (สีแดง) – ถ้าโดนชนจะระเบิด",
                              "ทุกคนมี HP: โดนรถชนจะกระเด็น ล้มลง แล้วลุกขึ้นมาเดินกะเผลก",
                              "ไฟไหม้จะลด HP ต่อเนื่องจนกว่าไฟจะดับ",
                              "คราบเลือดทำให้รถลื่นไปชนกัน แล้วโดรนจะมายกซากออก",
                              "คลิกที่คน = เดิน/หยุด   คลิกขวา = ใช้ความสามารถ",
                              "Shift+คลิกเลือกหลายคน ปล่อย Shift = ข้ามพร้อมกัน",
                              "คลิกซ้ำขณะกด Shift = เอาออกจากกลุ่ม   Esc = ล้างกลุ่ม",
                              "คลิกหรือกดปุ่มใดก็ได้เพื่อเริ่ม"],
            width=560
        )

    def draw_end(self):
        saved_count = sum(person.saved for person in self.people)
        if self.state != "win":
            self.center_card(["ไม่ผ่าน", f"คนที่เหลือไม่พอ (ต้องรอด {self.current_level['target']} คน)"],
                             supporting_lines=["R = ลองอีกครั้ง"])
            return
        stars = 3 if saved_count == 10 else 2 if saved_count >= 8 else 1
        minutes, seconds = divmod(int(self.elapsed_time), 60)
        rectangle = self.center_card(
            ["ผ่านด่าน!", f"รอด {saved_count} / 10 คน   ·   เวลา {minutes:02d}:{seconds:02d}", " "],
            supporting_lines=["N = ด่านถัดไป      R = เล่นด่านนี้อีกครั้ง"]
        )
        for index in range(3):
            points = star_points(rectangle.centerx + (index - 1) * 46, rectangle.y + 116)
            pygame.draw.polygon(self.active_surface, ACCENT_COLOR if index < stars else PANEL_2_COLOR, points)

    # ================================================================ คน
    def draw_person(self, person, carrier=None):
        pose = PersonPose(person, carrier)
        time_seconds = pygame.time.get_ticks() / 1000
        self.draw_legs(person, pose)
        neck = self.draw_torso(person, pose)
        self.draw_arms(person, pose, time_seconds)
        head, head_radius = self.draw_head(person, pose)
        self.draw_held_items(person, pose, head, neck)
        if person.burn_time > 0 and person.alive:
            self.draw_body_flames(pose, time_seconds)
        if carrier or not person.alive:
            return
        status_top = head[1] - head_radius - 8
        self.draw_status_icon(person, head, status_top, time_seconds)
        self.draw_overhead_bars(person, head, status_top)

    def draw_legs(self, person, pose):
        leg_color = mix((44, 46, 58), (30, 26, 24), person.charring_level)
        for side in (-1, 1):
            is_stiff = person.injured and side == 1 and pose.is_moving                   # ขาข้างเจ็บแกว่งน้อย
            swing = pose.swing * side * (0.2 if is_stiff else 0.6)
            foot = pose.point(0, side * 3 * pose.scale + swing)
            hip = pose.point(11 * pose.scale, side * 3 * pose.scale)
            pygame.draw.line(self.active_surface, leg_color, foot, hip, 3)

    def draw_torso(self, person, pose):
        """ลำตัวเป็นแคปซูล: เส้นหนา 2 ชั้น (ขอบเข้ม + สีตัว) ปิดหัวท้ายด้วยวงกลม"""
        surface = self.active_surface
        hip, neck = pose.point(11 * pose.scale), pose.point(25 * pose.scale)
        pygame.draw.line(surface, shade(pose.body_color, 0.6), hip, neck, int(pose.body_width) + 2)
        pygame.draw.line(surface, pose.body_color, hip, neck, int(pose.body_width))
        for end in (hip, neck):
            pygame.draw.circle(surface, pose.body_color, end, int(pose.body_width / 2))
        if person.injured and person.alive:
            pygame.draw.circle(surface, BLOOD_HIGHLIGHT, pose.point(18 * pose.scale, 2), 3)
        return neck

    def draw_arms(self, person, pose, time_seconds):
        scale, half_width = pose.scale, pose.body_width / 2
        for side in (-1, 1):
            shoulder = pose.point(23 * scale, side * (half_width + 1))
            if person.burn_time > 0 and pose.is_alive:                                    # ไฟไหม้: โบกแขนเหนือหัว
                hand = pose.point(36 * scale + 3 * math.sin(time_seconds * 20 + side), side * (half_width + 6))
            elif pose.is_lying:
                hand = pose.point(24 * scale, side * (half_width + 9))
            else:
                hand = pose.point(13 * scale, side * (half_width + 2) - pose.swing * side * 0.5)
            pygame.draw.line(self.active_surface, shade(pose.body_color, 0.8), shoulder, hand, 3)

    def draw_head(self, person, pose):
        surface, scale, kind = self.active_surface, pose.scale, person.kind
        head = pose.point(33 * scale)
        radius = int(7 * scale)
        if kind == "grandma":                                                              # มวยผม
            pygame.draw.circle(surface, mix((210, 210, 214), (40, 36, 34), person.charring_level), pose.point(36 * scale, -4 * pose.facing), 5)
        pygame.draw.circle(surface, pose.skin_color, head, radius)
        pygame.draw.circle(surface, shade(pose.skin_color, 0.7), head, radius, 1)
        if kind == "warden":                                                               # หมวกตำรวจ
            pygame.draw.circle(surface, mix((24, 50, 120), (30, 26, 24), person.charring_level), pose.point(39 * scale), 5)
        elif kind == "runner":                                                             # ผ้าคาดหัว
            pygame.draw.line(surface, (220, 40, 40), pose.point(36 * scale, -radius), pose.point(36 * scale, radius), 2)
        elif kind == "kid":                                                                # จุกผม
            pygame.draw.circle(surface, (60, 40, 30), pose.point(38 * scale), 4)
        if person.injured and person.alive:                                               # ผ้าพันแผล
            pygame.draw.line(surface, (240, 240, 240), pose.point(35 * scale, -radius), pose.point(35 * scale, radius), 3)
        if not person.alive:                                                               # ตา x_x
            for eye_dx in (-3, 3):
                eye_x, eye_y = head[0] + eye_dx, head[1] - 1
                pygame.draw.line(surface, (40, 30, 30), (eye_x - 2, eye_y - 2), (eye_x + 2, eye_y + 2), 1)
                pygame.draw.line(surface, (40, 30, 30), (eye_x - 2, eye_y + 2), (eye_x + 2, eye_y - 2), 1)
        return head, radius

    def draw_held_items(self, person, pose, head, neck):
        surface = self.active_surface
        if person.fuel and not pose.is_lying:                                              # ถังน้ำมันในมือ
            fuel_x = pose.base_x + 10 * person.facing
            draw_box(surface, fuel_x, pose.base_y + 2, 7, 6, pose.base_z + 6, pose.base_z + 17, 0, (206, 40, 32))
            pygame.draw.line(surface, (40, 40, 40), project(fuel_x, pose.base_y + 2, pose.base_z + 17), project(fuel_x, pose.base_y + 2, pose.base_z + 20), 2)
        if person.kind == "grandma" and pose.is_alive:                                     # ไม้เท้า
            cane_x = head[0] + 10 * person.facing
            pygame.draw.line(surface, (120, 80, 40), (cane_x, pose.point(20)[1]), (cane_x + 2 * person.facing, pose.point(0)[1]), 2)
        if person.kind == "warden" and person.sign_time > 0 and pose.is_alive:            # ป้ายหยุด
            pole_x, pole_y = neck[0] + pose.body_width / 2 + 4, neck[1]
            pygame.draw.line(surface, (90, 90, 90), (pole_x, pole_y + 14), (pole_x, pole_y - 22), 2)
            # แปดเหลี่ยม: 8 จุดห่างกัน 45° หมุนไป 22.5° ให้ขอบบนแบนเหมือนป้ายจริง
            octagon = [(pole_x + 9 * math.cos(math.pi / 8 + i * math.pi / 4), pole_y - 30 + 9 * math.sin(math.pi / 8 + i * math.pi / 4)) for i in range(8)]
            pygame.draw.polygon(surface, (210, 30, 30), octagon)
            pygame.draw.polygon(surface, WHITE, octagon, 1)

    def draw_body_flames(self, pose, time_seconds):
        for index, height in enumerate((6, 15, 24, 33)):
            flame_x, flame_y = pose.point(height * pose.scale, (index % 2 * 2 - 1) * 4)
            flame_height = 10 + 6 * math.sin(time_seconds * 14 + index * 1.7)
            pygame.draw.polygon(self.active_surface, (255, 120, 30), [(flame_x - 5, flame_y), (flame_x + 5, flame_y), (flame_x + 1, flame_y - flame_height)])
            pygame.draw.polygon(self.active_surface, (255, 220, 90), [(flame_x - 2, flame_y), (flame_x + 2, flame_y), (flame_x, flame_y - flame_height * 0.55)])

    def draw_status_icon(self, person, head, top, time_seconds):
        """ไอคอนเหนือหัว: ดาวหมุน = มึน, ! = ตกใจ, ✓ = ข้ามแล้ว, ลูกศร = กำลังเดิน, || = รออยู่"""
        surface, head_x = self.active_surface, head[0]
        if person.down_time > 0:
            for index in range(3):                                                         # ดาว 3 ดวงห่างกัน 120°
                angle = time_seconds * 6 + index * math.tau / 3
                pygame.draw.circle(surface, ACCENT_COLOR, (head_x + math.cos(angle) * 10, head[1] - 10 + math.sin(angle) * 3), 2)
        elif person.panic:
            warning = self.font_bold.render("!", True, BAD_COLOR)
            surface.blit(warning, warning.get_rect(center=(head_x, top - 10)))
        elif person.saved:
            pygame.draw.lines(surface, GOOD_COLOR, False, [(head_x - 5, top), (head_x - 1, top + 4), (head_x + 6, top - 4)], 2)
        elif person.is_walking:
            pygame.draw.polygon(surface, GOOD_COLOR, [(head_x - 5, top - 8), (head_x + 5, top - 8), (head_x, top - 15)])
        else:
            pygame.draw.rect(surface, ACCENT_COLOR, (head_x - 5, top - 15, 3, 8))
            pygame.draw.rect(surface, ACCENT_COLOR, (head_x + 2, top - 15, 3, 8))

    def draw_overhead_bars(self, person, head, top):
        """แถบเลือดเหนือหัว (โชว์เมื่อเลือดไม่เต็มหรือเมาส์ชี้), จุดสกิลพร้อมใช้, คำว่าเหนื่อย"""
        surface = self.active_surface
        is_hovered = person is self.hovered_person()
        if not person.saved and (person.health < person.maximum_health or is_hovered):
            fraction = max(0.0, person.health / person.maximum_health)
            bar_width = 28
            bar_x, bar_y = head[0] - bar_width / 2, top - 2
            pygame.draw.rect(surface, (20, 20, 24), (bar_x - 1, bar_y - 1, bar_width + 2, 6))
            pygame.draw.rect(surface, health_color(fraction), (bar_x, bar_y, bar_width * fraction, 4))
            if is_hovered:
                number = self.font_tiny.render(str((person.index + 1) % 10), True, TEXT_COLOR)
                surface.blit(number, number.get_rect(midright=(bar_x - 3, bar_y + 2)))
        if not person.saved and person.information["cooldown"] > 1:
            pygame.draw.circle(surface, GOOD_COLOR if person.cooldown <= 0 else (90, 94, 100), (head[0] + 18, top), 3)
        if person.tired > 0:
            tired = self.font_small.render("เหนื่อย", True, MUTED_COLOR)
            surface.blit(tired, tired.get_rect(center=(head[0], top - 12)))
