"""ลำดับการวาด 1 เฟรม: แต่ละชั้นอยู่ในไฟล์ render_*.py"""

import random

import pygame

from game_config import BACKGROUND_COLOR, HEADS_UP_DISPLAY_Y, SCREEN_WIDTH
from render_cars import draw_car
from render_effects import (
    draw_decals,
    draw_drone,
    draw_fire,
    draw_floaters,
    draw_frozen_lanes,
    draw_impacts,
    draw_particles,
    draw_toasts,
)
from render_hud import draw_heads_up_display, draw_overlay_card, roster_rectangles
from render_people import draw_person


class GameRenderer:

    def draw(self):
        world = self.world_canvas
        self.active_surface = world
        self.draw_ground_layers(world)
        self.update_hover()
        self.draw_depth_sorted_objects(world)
        self.draw_flying_objects(world)
        draw_particles(world, self.particles)
        draw_floaters(world, self.floating_messages, self.font_bold)
        draw_impacts(self, world)
        self.draw_flash(world)

        screen = self.display_surface
        self.active_surface = screen
        self.present_world_with_shake(screen)
        draw_toasts(screen, self.toast_messages, self.font_bold)
        draw_heads_up_display(self, screen)
        draw_overlay_card(self, screen)
        pygame.display.flip()

    def hovered_person(self):
        return getattr(self, "hover", None)

    def render_cache(self):
        return self.__dict__.setdefault("_render_cache", {})

    def roster_rectangles(self):
        return roster_rectangles(self.people)

    def update_hover(self):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        over_world = self.state == "play" and mouse_y < HEADS_UP_DISPLAY_Y
        self.hover = self.person_at(mouse_x, mouse_y) if over_world else None

    def draw_ground_layers(self, surface):
        surface.blit(self.ground_surface, (0, 0))
        surface.blit(self.skid_mark_surface, (0, 0))
        draw_decals(self)
        surface.blit(self.decal_surface, (0, 0))
        draw_frozen_lanes(self, surface)

    def draw_depth_sorted_objects(self, surface):
        # painter's algorithm: วาดจาก y น้อย (ไกล) ไป y มาก (ใกล้) ของใกล้จึงทับของไกล
        items = []
        for car in self.cars:
            if not car.towed:
                items.append((car.depth(), "car", car))
        for person in self.people:
            if person.alive and person.carried_by is None:
                items.append((person.y, "person", person))
            elif not person.alive and person.death_time < 10:
                items.append((person.y - 0.5, "person", person))
        for fire in self.fires:
            items.append((fire.y + 1, "fire", fire))

        items.sort(key=lambda item: item[0])
        for _, kind, entity in items:
            if kind == "car":
                draw_car(surface, entity, self.font_bold)
            elif kind == "person":
                draw_person(surface, entity, self)
                if entity.carrying:
                    draw_person(surface, entity.carrying, self, carrier=entity)
            else:
                draw_fire(surface, entity)

    def draw_flying_objects(self, surface):
        for car in self.cars:
            if car.towed:
                draw_car(surface, car, self.font_bold)
        for drone in sorted(self.drones, key=lambda drone: drone.y):
            draw_drone(surface, drone)

    def draw_flash(self, surface):
        if self.flash_intensity > 0:
            self.flash_surface.fill((255, 250, 235, int(170 * self.flash_intensity)))
            surface.blit(self.flash_surface, (0, 0))

    def present_world_with_shake(self, screen):
        offset_x = offset_y = 0
        strength = self.active_surface_shake_strength
        if strength > 0.5:
            offset_x = random.uniform(-strength, strength)
            offset_y = random.uniform(-strength, strength) * 0.7
        screen.fill(BACKGROUND_COLOR)
        screen.blit(self.world_canvas, (offset_x, offset_y), (0, 0, SCREEN_WIDTH, HEADS_UP_DISPLAY_Y))
