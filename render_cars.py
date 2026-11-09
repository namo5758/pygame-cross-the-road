"""วาดรถทุกชนิด"""

import pygame

from game_config import BAD_COLOR, GLASS_COLOR, SKIN_COLOR, WHITE
from geometry import draw_box, local, project, shade

TIRE_COLOR = (26, 26, 30)


def draw_car(surface, car, warning_font):
    if car.kind == "sidecar":
        draw_sidecar(surface, car)
        return
    if car.kind == "moto":
        draw_moto(surface, car)
        return

    draw_wheels(surface, car, (-car.length * 0.32, car.length * 0.32))
    if car.kind == "tanker":
        draw_tanker(surface, car, warning_font)
    elif car.kind == "icecream":
        draw_icecream_van(surface, car)
    elif car.kind == "truck":
        draw_truck(surface, car)
    else:
        draw_sedan(surface, car)

    if car.wreck:
        draw_dents(surface, car)
    else:
        draw_lights(surface, car)


def glass_color(car):
    return (40, 46, 52) if car.wreck else GLASS_COLOR


def camera_side(car):
    return 1 if car.direction > 0 else -1


def draw_wheels(surface, car, offsets_along):
    for along in offsets_along:
        for across in (-car.width / 2 + 3, car.width / 2 - 3):
            wheel_x, wheel_y = local(car.x, car.y, car.angle, along, across)
            draw_box(surface, wheel_x, wheel_y, 15, 6, car.lift, car.lift + 10, car.angle, TIRE_COLOR, outline=False)


def draw_rider(surface, car, across):
    angle, lift = car.angle, car.lift
    rider_x, rider_y = local(car.x, car.y, angle, -3, across)
    draw_box(surface, rider_x, rider_y, 11, 10, lift + 15, lift + 32, angle, car.rider_color)
    helmet = project(*local(car.x, car.y, angle, -1, across), lift + 38)
    pygame.draw.circle(surface, (240, 240, 240), helmet, 6)
    pygame.draw.circle(surface, (60, 60, 70), helmet, 6, 1)


def draw_moto(surface, car):
    draw_box(surface, car.x, car.y, car.length, car.width * 0.6, car.lift + 4, car.lift + 15, car.angle, car.color)
    if not car.wreck:
        draw_rider(surface, car, 0)


def draw_sidecar(surface, car):
    angle, lift = car.angle, car.lift
    side = 9 * camera_side(car)

    tub_x, tub_y = local(car.x, car.y, angle, -2, side)
    draw_box(surface, tub_x, tub_y, 14, 6, lift, lift + 9, angle, TIRE_COLOR, outline=False)
    draw_box(surface, tub_x, tub_y, 32, 18, lift + 6, lift + 17, angle, car.color)
    nose = [project(*local(car.x, car.y, angle, 12, side + offset), lift + 17) for offset in (-9, 9)]
    nose.append(project(*local(car.x, car.y, angle, 18, side), lift + 21))
    pygame.draw.polygon(surface, shade(car.color, 1.25), nose)
    if not car.wreck:
        draw_sidecar_cargo(surface, car, side)

    bike_x, bike_y = local(car.x, car.y, angle, 0, -side)
    draw_box(surface, bike_x, bike_y, 38, 9, lift + 4, lift + 15, angle, (40, 40, 46))
    if not car.wreck:
        draw_rider(surface, car, -side)


def draw_sidecar_cargo(surface, car, side):
    angle, lift = car.angle, car.lift
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


def draw_cab(surface, car, cab_color, cab_along, cab_length, glass_along, glass_length):
    angle, lift, height = car.angle, car.lift, car.height
    cab_x, cab_y = local(car.x, car.y, angle, car.length * cab_along, 0)
    draw_box(surface, cab_x, cab_y, car.length * cab_length, car.width * 0.94, lift + 6, lift + height * 0.72, angle, cab_color)
    glass_x, glass_y = local(car.x, car.y, angle, car.length * glass_along, 0)
    draw_box(surface, glass_x, glass_y, car.length * glass_length, car.width * 0.8, lift + height * 0.42, lift + height * 0.7,
             angle, glass_color(car), top_color=shade(cab_color, 1.1), outline=False)


def draw_tanker(surface, car, warning_font):
    angle, lift, height = car.angle, car.lift, car.height
    side = car.width * 0.45 * camera_side(car)
    draw_wheels(surface, car, (-car.length * 0.1, car.length * 0.08))
    cab_color = (52, 48, 46) if car.burnt else (200, 50, 40)
    draw_cab(surface, car, cab_color, 0.39, 0.2, 0.45, 0.08)

    tank_x, tank_y = local(car.x, car.y, angle, -car.length * 0.12, 0)
    draw_box(surface, tank_x, tank_y, car.length * 0.7, car.width * 0.4, lift + 6, lift + 12, angle, (40, 40, 44), outline=False)
    draw_box(surface, tank_x, tank_y, car.length * 0.7, car.width * 0.9, lift + 12, lift + height, angle, car.color, top_color=shade(car.color, 1.08))
    for along in (-car.length * 0.38, -car.length * 0.12, car.length * 0.14):
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

    if car.fuse > 0 and int(car.fuse * 12) % 2 == 0:
        warning = warning_font.render("!", True, BAD_COLOR)
        surface.blit(warning, warning.get_rect(center=project(car.x, car.y, lift + height + 22)))


def draw_icecream_van(surface, car):
    angle, lift, height = car.angle, car.lift, car.height
    cream = (250, 250, 246)
    draw_box(surface, car.x, car.y, car.length, car.width, lift + 5, lift + height * 0.8, angle, car.color, top_color=cream)
    glass_x, glass_y = local(car.x, car.y, angle, car.length * 0.4, 0)
    draw_box(surface, glass_x, glass_y, car.length * 0.14, car.width * 0.82, lift + height * 0.35, lift + height * 0.72,
             angle, glass_color(car), top_color=cream, outline=False)

    side = car.width * 0.5 * camera_side(car)
    for index in range(5):
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


def draw_truck(surface, car):
    draw_cab(surface, car, car.color, 0.36, 0.26, 0.43, 0.1)
    cargo_x, cargo_y = local(car.x, car.y, car.angle, -car.length * 0.14, 0)
    cargo_color = shade((222, 220, 210), 0.75 if car.wreck else 1)
    draw_box(surface, cargo_x, cargo_y, car.length * 0.7, car.width, car.lift + 8, car.lift + car.height, car.angle, cargo_color)


def draw_sedan(surface, car):
    angle, lift, height = car.angle, car.lift, car.height
    draw_box(surface, car.x, car.y, car.length, car.width, lift + 5, lift + height * 0.52, angle, car.color)
    cabin_x, cabin_y = local(car.x, car.y, angle, -car.length * 0.06, 0)
    roof = height * (0.85 if car.wreck else 1.0)
    draw_box(surface, cabin_x, cabin_y, car.length * 0.5, car.width * 0.84, lift + height * 0.52, lift + roof,
             angle, glass_color(car), top_color=shade(car.color, 1.15))


def draw_dents(surface, car):
    z = car.lift + car.height * 0.52
    for along, across in ((car.length * 0.38, car.width * 0.2), (-car.length * 0.3, -car.width * 0.25), (car.length * 0.1, car.width * 0.3)):
        pygame.draw.circle(surface, shade(car.color, 0.55), project(*local(car.x, car.y, car.angle, along, across), z), 4)


def draw_lights(surface, car):
    z = car.lift + car.height * 0.33
    for across in (-car.width * 0.3, car.width * 0.3):
        pygame.draw.circle(surface, (255, 236, 160), project(*local(car.x, car.y, car.angle, car.length / 2, across), z), 3)
        pygame.draw.circle(surface, (220, 40, 40), project(*local(car.x, car.y, car.angle, -car.length / 2, across), z), 3)
