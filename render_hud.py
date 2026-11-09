"""วาดแถบด้านล่าง (HUD) และกล่องกลางจอ (หน้าเริ่ม ชนะ แพ้ หยุดชั่วคราว)"""

import math

import pygame

from game_config import (
    ACCENT_COLOR,
    BAD_COLOR,
    GOOD_COLOR,
    HEADS_UP_DISPLAY_Y,
    MUTED_COLOR,
    PANEL_2_COLOR,
    PANEL_COLOR,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
    SKIN_COLOR,
    TEXT_COLOR,
)
from geometry import mix
from render_people import BURNT_COLOR, health_color

INFO_LEFT = 538


def roster_rectangles(people):
    result = []
    for index, person in enumerate(people):
        column, row = index % 5, index // 5
        result.append((person, pygame.Rect(250 + column * 54, HEADS_UP_DISPLAY_Y + 14 + row * 60, 50, 54)))
    return result


def draw_heads_up_display(game, surface):
    pygame.draw.rect(surface, PANEL_COLOR, (0, HEADS_UP_DISPLAY_Y, SCREEN_WIDTH, SCREEN_HEIGHT - HEADS_UP_DISPLAY_Y))
    pygame.draw.line(surface, PANEL_2_COLOR, (0, HEADS_UP_DISPLAY_Y), (SCREEN_WIDTH, HEADS_UP_DISPLAY_Y), 2)
    draw_level_stats(game, surface)
    for person, rectangle in roster_rectangles(game.people):
        draw_roster_card(game, surface, person, rectangle)
    draw_person_info(game, surface)
    draw_controls_help(game, surface)


def draw_level_stats(game, surface):
    top = HEADS_UP_DISPLAY_Y
    saved_count = sum(person.saved for person in game.people)
    dead_count = sum(not person.alive for person in game.people)
    target = game.current_level["target"]
    minutes, seconds = divmod(int(game.elapsed_time), 60)
    surface.blit(game.font_bold.render(game.current_level["name"], True, TEXT_COLOR), (18, top + 12))
    surface.blit(game.font_regular.render(f"ข้ามสำเร็จ  {saved_count} / {target}", True, GOOD_COLOR if saved_count >= target else TEXT_COLOR), (18, top + 44))
    surface.blit(game.font_regular.render(f"เสียชีวิต  {dead_count}", True, BAD_COLOR if dead_count else MUTED_COLOR), (18, top + 70))
    surface.blit(game.font_regular.render(f"เวลา  {minutes:02d}:{seconds:02d}", True, MUTED_COLOR), (18, top + 96))

    bar_x, bar_y, bar_width = 18, top + 124, 200
    pygame.draw.rect(surface, PANEL_2_COLOR, (bar_x, bar_y, bar_width, 8), border_radius=4)
    pygame.draw.rect(surface, GOOD_COLOR, (bar_x, bar_y, bar_width * min(1, saved_count / 10), 8), border_radius=4)
    target_x = bar_x + bar_width * target / 10
    pygame.draw.line(surface, ACCENT_COLOR, (target_x, bar_y - 3), (target_x, bar_y + 11), 2)


def draw_roster_card(game, surface, person, rectangle):
    is_active_walker = person.is_walking and person.active
    pygame.draw.rect(surface, PANEL_2_COLOR, rectangle, border_radius=6)
    if person.active and person in game.selected_people:
        pygame.draw.rect(surface, ACCENT_COLOR, rectangle.inflate(4, 4), 2, border_radius=7)
    if is_active_walker:
        pygame.draw.rect(surface, GOOD_COLOR, rectangle, 2, border_radius=6)
    if person is game.hovered_person():
        pygame.draw.rect(surface, (200, 200, 200), rectangle, 1, border_radius=6)

    body = mix(person.information["color"], BURNT_COLOR, person.charring_level) if person.alive else (70, 70, 76)
    pygame.draw.rect(surface, body, (rectangle.centerx - 7, rectangle.y + 18, 14, 16), border_radius=4)
    pygame.draw.circle(surface, SKIN_COLOR if person.alive else (90, 90, 96), (rectangle.centerx, rectangle.y + 12), 6)
    key_label = game.font_tiny.render(str((person.index + 1) % 10), True, GOOD_COLOR if is_active_walker else MUTED_COLOR)
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
    name = game.font_tiny.render(person.information["short_name"], True, MUTED_COLOR)
    surface.blit(name, name.get_rect(center=(rectangle.centerx, rectangle.bottom - 8)))

    if person.saved:
        pygame.draw.lines(surface, GOOD_COLOR, False, [(rectangle.x + 6, rectangle.y + 10), (rectangle.x + 10, rectangle.y + 14), (rectangle.x + 17, rectangle.y + 5)], 2)
    elif not person.alive:
        pygame.draw.line(surface, BAD_COLOR, (rectangle.x + 8, rectangle.y + 8), (rectangle.right - 8, rectangle.y + 40), 3)
        pygame.draw.line(surface, BAD_COLOR, (rectangle.right - 8, rectangle.y + 8), (rectangle.x + 8, rectangle.y + 40), 3)
    elif person.information["cooldown"] > 1 and person.cooldown > 0:
        fraction = person.cooldown / person.information["cooldown"]
        pygame.draw.rect(surface, (90, 94, 100), (rectangle.x + 4, rectangle.bottom - 3, (rectangle.width - 8) * fraction, 2))


def draw_person_info(game, surface):
    left, top = INFO_LEFT, HEADS_UP_DISPLAY_Y
    person = game.hovered_person()
    if person is None:
        mouse_x, mouse_y = pygame.mouse.get_pos()
        person = next((p for p, rect in roster_rectangles(game.people) if rect.collidepoint(mouse_x, mouse_y)), None)

    if not (person and person.alive):
        surface.blit(game.font_bold.render("คลิกที่คน = เดินข้าม / หยุด", True, ACCENT_COLOR), (left, top + 12))
        surface.blit(game.font_regular.render("คลิกขวาที่คน = ใช้ความสามารถ", True, TEXT_COLOR), (left, top + 40))
        surface.blit(game.font_small.render("ชี้เมาส์ที่คนเพื่อดู HP และความสามารถ", True, MUTED_COLOR), (left, top + 66))
        return

    title = f"{(person.index + 1) % 10}. {person.information['name']}" + ("  · ถังน้ำมัน!" if person.fuel else "")
    surface.blit(game.font_bold.render(title, True, BAD_COLOR if person.fuel else ACCENT_COLOR), (left, top + 12))
    fraction = max(0.0, person.health / person.maximum_health)
    status = f"HP {int(max(0, person.health))}/{person.maximum_health}  ·  {person_state_text(person)}"
    surface.blit(game.font_small.render(status, True, health_color(fraction)), (left, top + 40))
    surface.blit(game.font_regular.render(person.information["skill_description"], True, TEXT_COLOR), (left, top + 62))
    if person.information["cooldown"] > 1 and not person.saved:
        ready = person.cooldown <= 0
        text = "คลิกขวา = ใช้ความสามารถ (พร้อม)" if ready else f"ใช้ได้อีกใน {person.cooldown:0.1f} วินาที"
        surface.blit(game.font_small.render(text, True, GOOD_COLOR if ready else MUTED_COLOR), (left + 300, top + 40))


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


def draw_controls_help(game, surface):
    selected_count = sum(person.active for person in game.selected_people)
    lines = ["Shift+คลิก = เลือกกลุ่ม / คลิกซ้ำเอาออก | ปล่อย Shift = เดิน",
             f"เลือก {selected_count} คน | Esc = ล้าง | G = เดินทุกคน | Space = หยุด | P = พัก | R = ใหม่"]
    for index, line in enumerate(lines):
        surface.blit(game.font_small.render(line, True, MUTED_COLOR), (INFO_LEFT, HEADS_UP_DISPLAY_Y + 104 + index * 20))


def draw_overlay_card(game, surface):
    if game.state == "title":
        draw_title(game, surface)
    elif game.state in ("win", "lose"):
        draw_end(game, surface)
    elif game.paused:
        center_card(game, surface, ["หยุดชั่วคราว", "กด P เพื่อเล่นต่อ"])


def center_card(game, surface, lines, supporting_lines=None, width=520):
    cache = game.render_cache()
    if "dim" not in cache:
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
        font = game.font_heading if is_title else game.font_regular
        text = font.render(line, True, ACCENT_COLOR if is_title else TEXT_COLOR)
        surface.blit(text, text.get_rect(midtop=(rectangle.centerx, y)))
        y += 44 if is_title else 30
    if supporting_lines:
        y += 8
        for line in supporting_lines:
            surface.blit(game.font_small.render(line, True, MUTED_COLOR), (rectangle.x + 34, y))
            y += 26
    return rectangle


def draw_title(game, surface):
    center_card(
        game, surface,
        ["ข้ามถนน", "พาคนข้ามทางม้าลายไปฝั่งปลอดภัยให้ได้มากที่สุด",
         f"ต้องรอดอย่างน้อย {game.current_level['target']} จาก 10 คน"],
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


def draw_end(game, surface):
    saved_count = sum(person.saved for person in game.people)
    if game.state != "win":
        center_card(game, surface, ["ไม่ผ่าน", f"คนที่เหลือไม่พอ (ต้องรอด {game.current_level['target']} คน)"],
                    supporting_lines=["R = ลองอีกครั้ง"])
        return
    stars = 3 if saved_count == 10 else 2 if saved_count >= 8 else 1
    minutes, seconds = divmod(int(game.elapsed_time), 60)
    rectangle = center_card(
        game, surface,
        ["ผ่านด่าน!", f"รอด {saved_count} / 10 คน   ·   เวลา {minutes:02d}:{seconds:02d}", " "],
        supporting_lines=["N = ด่านถัดไป      R = เล่นด่านนี้อีกครั้ง"]
    )
    for index in range(3):
        points = star_points(rectangle.centerx + (index - 1) * 46, rectangle.y + 116)
        pygame.draw.polygon(surface, ACCENT_COLOR if index < stars else PANEL_2_COLOR, points)


def star_points(center_x, center_y, outer_radius=16, inner_radius=7):
    points = []
    for vertex in range(10):
        radius = outer_radius if vertex % 2 == 0 else inner_radius
        angle = -math.pi / 2 + vertex * math.pi / 5
        points.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)))
    return points
