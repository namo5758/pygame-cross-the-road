"""วาดคน"""

import math

import pygame

from game_config import ACCENT_COLOR, BAD_COLOR, BLOOD_HIGHLIGHT, GOOD_COLOR, MUTED_COLOR, SKIN_COLOR, TEXT_COLOR, WHITE
from geometry import draw_box, mix, project, shade

BURNT_COLOR = (34, 28, 26)


def health_color(fraction):
    if fraction > 0.6:
        return GOOD_COLOR
    if fraction > 0.4:
        return ACCENT_COLOR
    return BAD_COLOR


class PersonPose:
    """ท่าทางของคนในเฟรมนี้ อวัยวะทุกส่วนวางบนแกนลำตัวที่เอียงด้วยมุม pose (0 = ยืน, pi/2 = นอน)"""

    def __init__(self, person, carrier):
        if carrier:
            self.base_x, self.base_y, self.base_z = carrier.x + 2, carrier.y, 30
        else:
            self.base_x, self.base_y, self.base_z = person.x, person.y, 0
        self.scale = 0.76 if person.kind == "kid" else 1.0

        self.body_color = mix(person.information["color"], BURNT_COLOR, person.charring_level)
        self.skin_color = mix(SKIN_COLOR, (44, 34, 30), person.charring_level)
        if person.hurt_time > 0 and int(person.hurt_time * 18) % 2 == 0:
            self.body_color = mix(self.body_color, (255, 80, 70), 0.65)
            self.skin_color = mix(self.skin_color, (255, 80, 70), 0.65)

        angle = math.pi / 2 if carrier else person.pose
        self.is_lying = angle > 0.6
        self.facing = person.fall_direction if self.is_lying else person.facing
        self.is_alive = person.alive and not self.is_lying and not carrier
        self.is_moving = self.is_alive and person.moving

        phase = person.walk_phase * 10
        if self.is_moving and person.injured:
            self.bob = max(0.0, math.sin(phase)) * 4
        else:
            self.bob = abs(math.sin(phase)) * 2 if self.is_moving else 0
        self.swing = math.sin(phase) * 4 if self.is_moving else 0
        if person.slip_time > 0 and self.is_alive:
            self.swing = 6

        self.sin_pose, self.cos_pose = math.sin(angle), math.cos(angle)
        self.body_width = 18 if person.kind == "strong" else 13 * self.scale

    def point(self, height, offset=0.0):
        return project(
            self.base_x + self.facing * self.sin_pose * height + offset * self.cos_pose,
            self.base_y + offset * self.sin_pose * 0.6,
            self.base_z + self.cos_pose * (height + self.bob)
        )


def draw_person(surface, person, game, carrier=None):
    pose = PersonPose(person, carrier)
    time_seconds = pygame.time.get_ticks() / 1000
    draw_legs(surface, person, pose)
    neck = draw_torso(surface, person, pose)
    draw_arms(surface, person, pose, time_seconds)
    head, head_radius = draw_head(surface, person, pose)
    draw_held_items(surface, person, pose, head, neck)
    if person.burn_time > 0 and person.alive:
        draw_body_flames(surface, pose, time_seconds)
    if carrier or not person.alive:
        return
    status_top = head[1] - head_radius - 8
    draw_status_icon(surface, person, head, status_top, time_seconds, game.font_bold)
    draw_overhead_bars(surface, person, head, status_top, game)


def draw_legs(surface, person, pose):
    leg_color = mix((44, 46, 58), (30, 26, 24), person.charring_level)
    for side in (-1, 1):
        is_stiff = person.injured and side == 1 and pose.is_moving
        swing = pose.swing * side * (0.2 if is_stiff else 0.6)
        foot = pose.point(0, side * 3 * pose.scale + swing)
        hip = pose.point(11 * pose.scale, side * 3 * pose.scale)
        pygame.draw.line(surface, leg_color, foot, hip, 3)


def draw_torso(surface, person, pose):
    hip, neck = pose.point(11 * pose.scale), pose.point(25 * pose.scale)
    pygame.draw.line(surface, shade(pose.body_color, 0.6), hip, neck, int(pose.body_width) + 2)
    pygame.draw.line(surface, pose.body_color, hip, neck, int(pose.body_width))
    for end in (hip, neck):
        pygame.draw.circle(surface, pose.body_color, end, int(pose.body_width / 2))
    if person.injured and person.alive:
        pygame.draw.circle(surface, BLOOD_HIGHLIGHT, pose.point(18 * pose.scale, 2), 3)
    return neck


def draw_arms(surface, person, pose, time_seconds):
    scale, half_width = pose.scale, pose.body_width / 2
    for side in (-1, 1):
        shoulder = pose.point(23 * scale, side * (half_width + 1))
        if person.burn_time > 0 and pose.is_alive:
            hand = pose.point(36 * scale + 3 * math.sin(time_seconds * 20 + side), side * (half_width + 6))
        elif pose.is_lying:
            hand = pose.point(24 * scale, side * (half_width + 9))
        else:
            hand = pose.point(13 * scale, side * (half_width + 2) - pose.swing * side * 0.5)
        pygame.draw.line(surface, shade(pose.body_color, 0.8), shoulder, hand, 3)


def draw_head(surface, person, pose):
    scale, kind = pose.scale, person.kind
    head = pose.point(33 * scale)
    radius = int(7 * scale)
    if kind == "grandma":
        pygame.draw.circle(surface, mix((210, 210, 214), (40, 36, 34), person.charring_level), pose.point(36 * scale, -4 * pose.facing), 5)
    pygame.draw.circle(surface, pose.skin_color, head, radius)
    pygame.draw.circle(surface, shade(pose.skin_color, 0.7), head, radius, 1)
    if kind == "warden":
        pygame.draw.circle(surface, mix((24, 50, 120), (30, 26, 24), person.charring_level), pose.point(39 * scale), 5)
    elif kind == "runner":
        pygame.draw.line(surface, (220, 40, 40), pose.point(36 * scale, -radius), pose.point(36 * scale, radius), 2)
    elif kind == "kid":
        pygame.draw.circle(surface, (60, 40, 30), pose.point(38 * scale), 4)
    if person.injured and person.alive:
        pygame.draw.line(surface, (240, 240, 240), pose.point(35 * scale, -radius), pose.point(35 * scale, radius), 3)
    if not person.alive:
        for eye_dx in (-3, 3):
            eye_x, eye_y = head[0] + eye_dx, head[1] - 1
            pygame.draw.line(surface, (40, 30, 30), (eye_x - 2, eye_y - 2), (eye_x + 2, eye_y + 2), 1)
            pygame.draw.line(surface, (40, 30, 30), (eye_x - 2, eye_y + 2), (eye_x + 2, eye_y - 2), 1)
    return head, radius


def draw_held_items(surface, person, pose, head, neck):
    if person.fuel and not pose.is_lying:
        fuel_x = pose.base_x + 10 * person.facing
        draw_box(surface, fuel_x, pose.base_y + 2, 7, 6, pose.base_z + 6, pose.base_z + 17, 0, (206, 40, 32))
        pygame.draw.line(surface, (40, 40, 40), project(fuel_x, pose.base_y + 2, pose.base_z + 17), project(fuel_x, pose.base_y + 2, pose.base_z + 20), 2)
    if person.kind == "grandma" and pose.is_alive:
        cane_x = head[0] + 10 * person.facing
        pygame.draw.line(surface, (120, 80, 40), (cane_x, pose.point(20)[1]), (cane_x + 2 * person.facing, pose.point(0)[1]), 2)
    if person.kind == "warden" and person.sign_time > 0 and pose.is_alive:
        pole_x, pole_y = neck[0] + pose.body_width / 2 + 4, neck[1]
        pygame.draw.line(surface, (90, 90, 90), (pole_x, pole_y + 14), (pole_x, pole_y - 22), 2)
        octagon = [(pole_x + 9 * math.cos(math.pi / 8 + i * math.pi / 4), pole_y - 30 + 9 * math.sin(math.pi / 8 + i * math.pi / 4)) for i in range(8)]
        pygame.draw.polygon(surface, (210, 30, 30), octagon)
        pygame.draw.polygon(surface, WHITE, octagon, 1)


def draw_body_flames(surface, pose, time_seconds):
    for index, height in enumerate((6, 15, 24, 33)):
        flame_x, flame_y = pose.point(height * pose.scale, (index % 2 * 2 - 1) * 4)
        flame_height = 10 + 6 * math.sin(time_seconds * 14 + index * 1.7)
        pygame.draw.polygon(surface, (255, 120, 30), [(flame_x - 5, flame_y), (flame_x + 5, flame_y), (flame_x + 1, flame_y - flame_height)])
        pygame.draw.polygon(surface, (255, 220, 90), [(flame_x - 2, flame_y), (flame_x + 2, flame_y), (flame_x, flame_y - flame_height * 0.55)])


def draw_status_icon(surface, person, head, top, time_seconds, font):
    head_x = head[0]
    if person.down_time > 0:
        for index in range(3):
            angle = time_seconds * 6 + index * math.tau / 3
            pygame.draw.circle(surface, ACCENT_COLOR, (head_x + math.cos(angle) * 10, head[1] - 10 + math.sin(angle) * 3), 2)
    elif person.panic:
        warning = font.render("!", True, BAD_COLOR)
        surface.blit(warning, warning.get_rect(center=(head_x, top - 10)))
    elif person.saved:
        pygame.draw.lines(surface, GOOD_COLOR, False, [(head_x - 5, top), (head_x - 1, top + 4), (head_x + 6, top - 4)], 2)
    elif person.is_walking:
        pygame.draw.polygon(surface, GOOD_COLOR, [(head_x - 5, top - 8), (head_x + 5, top - 8), (head_x, top - 15)])
    else:
        pygame.draw.rect(surface, ACCENT_COLOR, (head_x - 5, top - 15, 3, 8))
        pygame.draw.rect(surface, ACCENT_COLOR, (head_x + 2, top - 15, 3, 8))


def draw_overhead_bars(surface, person, head, top, game):
    is_hovered = person is game.hovered_person()
    if not person.saved and (person.health < person.maximum_health or is_hovered):
        fraction = max(0.0, person.health / person.maximum_health)
        bar_width = 28
        bar_x, bar_y = head[0] - bar_width / 2, top - 2
        pygame.draw.rect(surface, (20, 20, 24), (bar_x - 1, bar_y - 1, bar_width + 2, 6))
        pygame.draw.rect(surface, health_color(fraction), (bar_x, bar_y, bar_width * fraction, 4))
        if is_hovered:
            number = game.font_tiny.render(str((person.index + 1) % 10), True, TEXT_COLOR)
            surface.blit(number, number.get_rect(midright=(bar_x - 3, bar_y + 2)))
    if not person.saved and person.information["cooldown"] > 1:
        pygame.draw.circle(surface, GOOD_COLOR if person.cooldown <= 0 else (90, 94, 100), (head[0] + 18, top), 3)
    if person.tired > 0:
        tired = game.font_small.render("เหนื่อย", True, MUTED_COLOR)
        surface.blit(tired, tired.get_rect(center=(head[0], top - 12)))
