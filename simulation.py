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
