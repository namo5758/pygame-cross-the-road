"""วาดของบนพื้น โดรน ไฟ เศษชิ้นส่วน และข้อความลอย"""

import math

import pygame

from fonts import load_font
from game_config import ACCENT_COLOR, GOOD_COLOR, LANE_HEIGHT, ROAD_TOP, SCREEN_WIDTH, VERTICAL_SCALE
from geometry import box_corners, draw_box, project, shade


def draw_decals(game):
    surface = game.decal_surface
    surface.fill((0, 0, 0, 0))

    for puddle in game.puddles:
        alpha = int(220 * min(1.0, puddle.life / 3.0))
        for blob_x, blob_y, radius in puddle.blobs:
            center_x, center_y = project(puddle.x + blob_x, puddle.y + blob_y)
            pygame.draw.ellipse(
                surface, (*puddle.color, alpha),
                (center_x - radius, center_y - radius * VERTICAL_SCALE, radius * 2, radius * 2 * VERTICAL_SCALE)
            )
        center_x, center_y = project(puddle.x - puddle.radius * 0.2, puddle.y - puddle.radius * 0.2)
        pygame.draw.ellipse(surface, (*puddle.highlight_color, alpha // 2), (center_x - 6, center_y - 3, 12, 5))

    for fire in game.fires:
        center_x, center_y = project(fire.x, fire.y)
        squash = VERTICAL_SCALE * 0.75
        pygame.draw.ellipse(
            surface, (20, 16, 14, 170),
            (center_x - fire.radius, center_y - fire.radius * squash, fire.radius * 2, fire.radius * 2 * squash)
        )

    for car in game.cars:
        shadow = box_corners(car.x + 5, car.y + 7, car.length, car.width, car.angle)
        pygame.draw.polygon(surface, (0, 0, 0, 70 if car.lift < 5 else 40), [project(*corner) for corner in shadow])

    for drone in game.drones:
        center_x, center_y = project(drone.x, drone.y)
        pygame.draw.ellipse(surface, (0, 0, 0, 50), (center_x - 26, center_y - 9, 52, 18))

    hover_person = game.hovered_person()
    for person in game.people:
        if not person.alive or person.carried_by:
            continue
        center_x, center_y = project(person.x + 2, person.y + 2)
        pygame.draw.ellipse(surface, (0, 0, 0, 80), (center_x - 10, center_y - 4, 20, 8))
        center_x, center_y = project(person.x, person.y)
        if person.active and person in game.selected_people:
            pygame.draw.ellipse(surface, (*ACCENT_COLOR, 240), (center_x - 20, center_y - 10, 40, 20), 3)
        if person is hover_person:
            pygame.draw.ellipse(surface, (255, 255, 255, 200), (center_x - 16, center_y - 8, 32, 16), 2)
        if person.is_walking and not person.saved:
            pygame.draw.ellipse(surface, (*GOOD_COLOR, 200), (center_x - 13, center_y - 6, 26, 12), 2)


def draw_frozen_lanes(game, surface):
    overlay = game.overlay_surface
    overlay.fill((0, 0, 0, 0))
    any_frozen = False
    for lane_index, freeze_time in enumerate(game.lane_freeze_timers):
        if freeze_time <= 0:
            continue
        any_frozen = True
        top = ROAD_TOP + LANE_HEIGHT * lane_index
        bottom = top + LANE_HEIGHT
        alpha = int(60 * min(1.0, freeze_time))
        corners = [project(0, top), project(SCREEN_WIDTH, top), project(SCREEN_WIDTH, bottom), project(0, bottom)]
        pygame.draw.polygon(overlay, (230, 60, 50, alpha), corners)
    if any_frozen:
        surface.blit(overlay, (0, 0))


def draw_drone(surface, drone):
    time_seconds = pygame.time.get_ticks() / 1000

    if drone.state != "fly":
        roof_z = drone.car.lift + drone.car.height
        hook_z = drone.z - (drone.z - roof_z) * drone.cable_extension
        hook = project(drone.x, drone.y, hook_z)
        pygame.draw.line(surface, (40, 40, 44), project(drone.x, drone.y, drone.z), hook, 2)
        pygame.draw.circle(surface, (230, 190, 40), hook, 3)

    for arm_x, arm_y in ((-22, -16), (22, -16), (-22, 16), (22, 16)):
        pygame.draw.line(surface, (50, 52, 58), project(drone.x, drone.y, drone.z + 6), project(drone.x + arm_x, drone.y + arm_y, drone.z + 8), 3)
        rotor_x, rotor_y = project(drone.x + arm_x, drone.y + arm_y, drone.z + 10)
        rotor_width = 16 + 3 * math.sin(time_seconds * 40 + arm_x)
        pygame.draw.ellipse(surface, (170, 176, 186), (rotor_x - rotor_width, rotor_y - 3, rotor_width * 2, 6), 1)
        blade = rotor_width * math.cos(time_seconds * 50)
        pygame.draw.line(surface, (90, 94, 100), (rotor_x - blade, rotor_y), (rotor_x + blade, rotor_y), 2)

    draw_box(surface, drone.x, drone.y, 28, 20, drone.z, drone.z + 9, 0, (240, 190, 40))
    draw_box(surface, drone.x, drone.y, 14, 10, drone.z + 9, drone.z + 13, 0, (40, 42, 48))
    if int(time_seconds * 4) % 2 == 0:
        pygame.draw.circle(surface, (255, 60, 50), project(drone.x + 14, drone.y + 10, drone.z + 6), 2)


def draw_fire(surface, fire):
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


def draw_particles(surface, particles):
    for particle in particles:
        screen_x, screen_y = project(particle.x, particle.y, particle.z)
        if particle.shape == "chunk":
            half_w, half_h = particle.size, particle.size * 0.6
            cos_a, sin_a = math.cos(particle.angle), math.sin(particle.angle)
            points = [(screen_x + dx * cos_a - dy * sin_a, screen_y + dx * sin_a + dy * cos_a)
                      for dx, dy in ((-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h))]
            pygame.draw.polygon(surface, particle.color, points)
            pygame.draw.polygon(surface, shade(particle.color, 0.5), points, 1)
        elif particle.shape == "wheel":
            pygame.draw.circle(surface, particle.color, (screen_x, screen_y), particle.size)
            hub = (screen_x + math.cos(particle.angle) * 2, screen_y + math.sin(particle.angle) * 2)
            pygame.draw.circle(surface, (150, 150, 156), hub, 2)
        else:
            life_left = particle.life / particle.maximum_life
            pygame.draw.circle(surface, particle.color, (screen_x, screen_y), max(1, int(particle.size * (0.5 + life_left * 0.5))))


def draw_floaters(surface, messages, font):
    for floater in messages:
        text_surface = font.render(floater.text, True, floater.color)
        text_surface.set_alpha(int(255 * min(1.0, floater.life / 0.5)))
        surface.blit(text_surface, text_surface.get_rect(center=project(floater.x, floater.y, floater.height + 20)))


def draw_impacts(game, surface):
    if game.font_impact is None:
        game.font_impact = load_font(44, bold=True)
    for impact in game.impact_messages:
        progress = 1 - impact.life / 0.9
        pop = impact.size * (1.7 - 0.7 * min(1.0, progress * 6))
        label = pygame.transform.rotozoom(impact_label(game, impact.text, impact.color), impact.rotation, pop * 0.6)
        label.set_alpha(int(255 * min(1.0, impact.life / 0.3)))
        surface.blit(label, label.get_rect(center=project(impact.x, impact.y, 50 + impact.offset_z + progress * 30)))


def impact_label(game, text, color):
    cache = game.render_cache()
    key = ("impact", text, color)
    if key not in cache:
        image = game.font_impact.render(text, True, color)
        outline = game.font_impact.render(text, True, (20, 16, 14))
        label = pygame.Surface((image.get_width() + 6, image.get_height() + 6), pygame.SRCALPHA)
        for offset in ((0, 3), (3, 0), (3, 6), (6, 3), (5, 5)):
            label.blit(outline, offset)
        label.blit(image, (3, 3))
        cache[key] = label
    return cache[key]


def draw_toasts(surface, messages, font):
    y = 64
    for toast in messages:
        opacity = min(1.0, toast.life / 0.4)
        text_surface = font.render(toast.text, True, toast.color)
        background = pygame.Surface((text_surface.get_width() + 24, text_surface.get_height() + 8), pygame.SRCALPHA)
        background.fill((15, 17, 22, int(200 * opacity)))
        rectangle = background.get_rect(center=(SCREEN_WIDTH / 2, y))
        surface.blit(background, rectangle)
        text_surface.set_alpha(int(255 * opacity))
        surface.blit(text_surface, text_surface.get_rect(center=rectangle.center))
        y += rectangle.height + 4
