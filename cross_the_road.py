#!/usr/bin/env python3
"""
ข้ามถนน (Cross the Road) — 2.5D

พาคน 10 คนข้ามทางม้าลายไปฝั่งปลอดภัย แต่ละคนมีความสามารถไม่เหมือนกัน
ถ้าโดนรถชนจะทิ้งคราบเลือดไว้บนถนน รถที่วิ่งผ่านจะลื่นไถลออกนอกเลน
ถ้าไปชนคันอื่นจะกลายเป็นซากขวางถนน แล้วโดรนจะบินมายกออกไป

ทุกคนมี HP — โดนรถชนจะกระเด็น ล้มลง แล้วลุกขึ้นมาเดินกะเผลก
ถ้า HP หมดถึงจะตาย  ไฟไหม้จะลด HP ต่อเนื่องจนกว่าไฟจะดับ

Controls:
  คลิกซ้ายที่คน           เดินข้ามถนน / หยุดรอ
  Shift + คลิกซ้าย        เลือกหลายคน แล้วปล่อย Shift เพื่อเริ่มข้ามพร้อมกัน
  Escape                 ยกเลิกการเลือกกลุ่ม
  คลิกขวาที่คน           ใช้ความสามารถ
  1-9, 0                 เดิน / หยุด ตามหมายเลขคน  (Shift+เลข = ใช้ความสามารถ)
  G                      ทุกคนเดิน
  Space                  ทุกคนหยุด
  P                      หยุดเกมชั่วคราว
  R                      เริ่มด่านใหม่
  N                      ไปด่านถัดไป (หลังผ่านด่าน)

Run:  pip install pygame   then   python cross_the_road.py
"""
import math
import random
import sys

import pygame

from entities import Person
from fonts import load_font
from game_config import (
    FRAMES_PER_SECOND,
    HEADS_UP_DISPLAY_Y,
    LANES,
    LEVELS,
    ROSTER,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)
from geometry import project
from render_ground import build_ground
from rendering import GameRenderer
from simulation import GameSimulation


# ---------------------------------------------------------------- game
# Game รวม GameSimulation (กติกา) กับ GameRenderer (การวาด) ไว้บน state ชุดเดียวกัน คลาสนี้ดูแลแค่ setup กับอินพุต
class Game(GameSimulation, GameRenderer):
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("ข้ามถนน · Cross the Road (2.5D demo)")
        # วาดโลกลง world_canvas ก่อน แล้วค่อยแปะลงจอพร้อมจอสั่น
        self.display_surface = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.world_canvas = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        self.font_impact = None
        self.clock = pygame.time.Clock()
        self.font_tiny = load_font(13)
        self.font_small = load_font(15)
        self.font_regular = load_font(18)
        self.font_bold = load_font(20, bold=True)
        self.font_heading = load_font(26, bold=True)
        self.ground_surface = build_ground()
        # layer โปร่งใส (SRCALPHA) สำหรับคราบบนพื้น ไฮไลต์เลน แฟลช และรอยเบรก
        self.decal_surface = pygame.Surface((SCREEN_WIDTH, HEADS_UP_DISPLAY_Y), pygame.SRCALPHA)
        self.overlay_surface = pygame.Surface((SCREEN_WIDTH, HEADS_UP_DISPLAY_Y), pygame.SRCALPHA)
        self.flash_surface = pygame.Surface((SCREEN_WIDTH, HEADS_UP_DISPLAY_Y), pygame.SRCALPHA)
        self.skid_mark_surface = pygame.Surface((SCREEN_WIDTH, HEADS_UP_DISPLAY_Y), pygame.SRCALPHA)
        self.level_index = 0
        self.state = "title"
        self.reset()

    # ------------------------------------------------------------ setup
    def reset(self):
        self.current_level = LEVELS[self.level_index]
        self.people = []
        self.selected_people = set()
        self.selection_pending = False
        character_kinds = ROSTER[:]
        random.shuffle(character_kinds)
        for index, kind in enumerate(character_kinds):
            # เรียงจุดเริ่ม 5 คอลัมน์ × 2 แถว สุ่มเยื้องนิดหน่อยไม่ให้ดูเป็นตาราง
            column = index % 5
            row_index = index // 5
            person = Person(
                kind,
                360 + column * 76 + random.uniform(-8, 8),
                520 + row_index * 48 + random.uniform(-6, 6),
                index
            )
            self.people.append(person)

        citizens = [person for person in self.people if person.kind == "citizen"]
        for person in citizens:
            person.fuel = random.random() < 0.3
        # สุ่มแล้วไม่มีใครถือถังน้ำมันเลย ให้มีอย่างน้อย 1 คนทุกด่าน
        if not any(person.fuel for person in citizens):
            random.choice(citizens).fuel = True

        self.cars = []
        self.drones = []
        self.spawn_timers = [random.uniform(0, 1.5) for _ in range(LANES)]
        self.lane_freeze_timers = [0.0] * LANES
        self.puddles = []
        self.fires = []
        self.particles = []
        self.floating_messages = []
        self.toast_messages = []
        self.impact_messages = []  # คำใหญ่ตอนชน
        self.active_surface_shake_strength = 0.0  # พิกเซล
        self.hitstop_remaining = 0.0  # เวลาที่เกมช้าลงตอนชนแรง
        self.flash_intensity = 0.0
        self.skid_mark_surface.fill((0, 0, 0, 0))
        self.skid_segments = []
        self.skid_fades_pending = 0
        self.skid_mark_fade_timer = 0.0
        self.elapsed_time = 0.0
        self.paused = False

        # เดินรถล่วงหน้า 6 วินาที ให้ถนนมีรถตั้งแต่เฟรมแรก
        for _ in range(6 * 60):
            self.update_traffic(1 / 60, pre_warm=True)

    # ------------------------------------------------------------ input
    def person_at(self, screen_x, screen_y, pick_radius=28):
        closest_person = None
        closest_distance = pick_radius
        # เช็กคนที่อยู่หน้าสุดก่อน ถ้าระยะเท่ากันจะได้คนที่เห็นอยู่ข้างหน้า
        for person in sorted(self.people, key=lambda candidate: -candidate.y):
            if not person.active:
                continue
            projected_x, projected_y = project(person.x, person.y, 18)
            distance = math.hypot(projected_x - screen_x, projected_y - screen_y)
            if distance < closest_distance:
                closest_person = person
                closest_distance = distance
        return closest_person

    def toggle_person_selection(self, person):
        # Shift+คลิก แค่เพิ่ม/เอาออกจากกลุ่ม ยังไม่สั่งเดินจนกว่าจะปล่อย Shift
        if not person.active:
            return
        self.selection_pending = True
        if person in self.selected_people:
            self.selected_people.remove(person)
        else:
            self.selected_people.add(person)

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if self.state == "title":
            if event.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
                self.state = "play"
            return
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.reset()
                self.state = "play"
            elif event.key == pygame.K_n and self.state == "win":
                self.level_index = (self.level_index + 1) % len(LEVELS)
                self.reset()
                self.state = "play"
            elif event.key == pygame.K_p and self.state == "play":
                self.paused = not self.paused
                self.selection_pending = False

        if self.state != "play" or self.paused:
            return

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.selected_people.clear()
                self.selection_pending = False
            elif event.key == pygame.K_g:
                self.set_all(True)
            elif event.key == pygame.K_SPACE:
                self.set_all(False)
            elif pygame.K_0 <= event.key <= pygame.K_9:
                person_index = (event.key - pygame.K_1) % 10          # 1..9 -> 0..8, 0 -> 9
                if person_index < len(self.people):
                    person = self.people[person_index]
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        self.use_ability(person)
                    else:
                        self.toggle_go(person)
        elif event.type == pygame.KEYUP and event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
            # กด Shift สองข้าง ต้องปล่อยครบทั้งคู่ก่อนกลุ่มจึงเริ่มเดิน
            released_modifier = pygame.KMOD_LSHIFT if event.key == pygame.K_LSHIFT else pygame.KMOD_RSHIFT
            remaining_modifiers = getattr(event, "mod", pygame.key.get_mods()) & ~released_modifier
            if self.selection_pending and not remaining_modifiers & pygame.KMOD_SHIFT:
                self.start_selected_crossing()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
            if event.pos[1] >= HEADS_UP_DISPLAY_Y:
                person = next((other_person for other_person, rectangle in self.roster_rectangles() if rectangle.collidepoint(event.pos)), None)
            else:
                person = self.person_at(*event.pos)
            if person:
                if event.button == 1:
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        self.toggle_person_selection(person)
                    else:
                        self.toggle_go(person)
                else:
                    self.use_ability(person)

    # ------------------------------------------------------------ loop
    def run(self):
        while True:
            # จำกัด delta_time ไม่เกิน 1/30 วิ เฟรมที่กระตุกจะได้ไม่ทำให้ทุกอย่างกระโดดไกล
            delta_time = min(self.clock.tick(FRAMES_PER_SECOND) / 1000, 1 / 30)
            for event in pygame.event.get():
                self.handle_event(event)
            if self.hitstop_remaining > 0:
                self.hitstop_remaining -= delta_time
                # hitstop: เดินเวลาแค่ 10% ให้รู้สึกหนักตอนชน
                delta_time *= 0.1
            self.update(delta_time)
            self.draw()


if __name__ == "__main__":
    Game().run()
