"""วาดพื้น: ภาพพื้นหลังที่สร้างครั้งเดียวต่อเกม และรอยเบรกที่สะสมบนถนน"""

import random

import pygame

from fonts import load_font
from game_config import (
    ASPHALT,
    ASPHALT_SPECK,
    BACKGROUND_COLOR,
    CROSSING_END_X,
    CROSSING_START_X,
    GOAL_LINE_COLOR,
    GOAL_PAVEMENT_COLOR,
    HEADS_UP_DISPLAY_Y,
    LANE_DIRECTION,
    LANE_HEIGHT,
    LANES,
    PAVEMENT_COLOR,
    PAVEMENT_LINE_COLOR,
    ROAD_BOTTOM,
    ROAD_TOP,
    SCREEN_WIDTH,
    SLAB_FRONT_COLOR,
    WHITE,
    WORLD_BOTTOM,
    YELLOW,
)
from geometry import draw_box, project, shade

HOUSE_COLORS = [(196, 160, 120), (170, 186, 196), (214, 196, 150), (186, 140, 130), (150, 170, 150), (210, 210, 200)]


def build_ground():
    surface = pygame.Surface((SCREEN_WIDTH, HEADS_UP_DISPLAY_Y))
    surface.fill(BACKGROUND_COLOR)
    # seed ตายตัว พื้นจึงออกมาเหมือนเดิมทุกครั้งที่เปิดเกม
    rng = random.Random(7)
    draw_shophouses(surface, rng)
    draw_safe_zone(surface)
    draw_trees(surface)
    draw_box(surface, SCREEN_WIDTH / 2, ROAD_TOP - 4, SCREEN_WIDTH + 40, 8, 0, 6, 0, (215, 210, 200), outline=False)
    draw_road(surface, rng)
    draw_lane_markings(surface)
    draw_crossing(surface)
    draw_near_sidewalk(surface)
    draw_ground_labels(surface)
    return surface


def draw_shophouses(surface, rng):
    building_x = -20
    while building_x < SCREEN_WIDTH + 20:
        house_width = rng.randint(90, 150)
        house_color = rng.choice(HOUSE_COLORS)
        house_height = rng.randint(70, 140)
        draw_box(surface, building_x + house_width / 2, -30, house_width - 4, 56, 0, house_height, 0, house_color, outline=False)
        top_y = project(0, -2, house_height)[1]
        bottom_y = project(0, -2, 0)[1]
        for window_y in range(int(max(top_y, 0)) + 6, int(bottom_y) - 14, 16):
            for window_x in range(int(building_x + 10), int(building_x + house_width - 18), 22):
                pygame.draw.rect(surface, shade(house_color, 0.55), (window_x, window_y, 12, 8))
        pygame.draw.rect(surface, shade(house_color, 0.4), (building_x + house_width / 2 - 14, bottom_y - 14, 28, 14))
        building_x += house_width


def fill_ground(surface, color, top, bottom):
    pygame.draw.polygon(surface, color, [project(0, top), project(SCREEN_WIDTH, top), project(SCREEN_WIDTH, bottom), project(0, bottom)])


def draw_tiles(surface, color, top, bottom):
    for grid_y in range(top, bottom, 24):
        pygame.draw.line(surface, color, project(0, grid_y), project(SCREEN_WIDTH, grid_y))
    for grid_x in range(0, SCREEN_WIDTH, 40):
        pygame.draw.line(surface, color, project(grid_x, top), project(grid_x, bottom))


def draw_safe_zone(surface):
    fill_ground(surface, GOAL_PAVEMENT_COLOR, 0, ROAD_TOP)
    draw_tiles(surface, GOAL_LINE_COLOR, 0, ROAD_TOP)


def draw_trees(surface):
    for tree_x in (70, 250, 770, 950):
        draw_box(surface, tree_x, 14, 8, 8, 0, 34, 0, (110, 80, 50), outline=False)
        for offset_x, offset_z, radius in ((-8, 40, 16), (8, 42, 15), (0, 52, 17)):
            leaf_x, leaf_y = project(tree_x + offset_x, 14, offset_z)
            pygame.draw.circle(surface, (60, 130, 70), (leaf_x, leaf_y), radius)
            pygame.draw.circle(surface, (80, 156, 86), (leaf_x - 4, leaf_y - 4), radius * 0.55)


def draw_road(surface, rng):
    fill_ground(surface, ASPHALT, ROAD_TOP, ROAD_BOTTOM)
    for _ in range(1600):
        speck_x, speck_y = project(rng.uniform(0, SCREEN_WIDTH), rng.uniform(ROAD_TOP, ROAD_BOTTOM))
        surface.set_at((int(speck_x), int(speck_y)), ASPHALT_SPECK)


def draw_lane_markings(surface):
    for lane_index in range(1, LANES):
        marking_y = ROAD_TOP + LANE_HEIGHT * lane_index
        # เลนสวนทางกันใช้เส้นเหลืองคู่ ถ้าวิ่งทางเดียวกันใช้เส้นขาวประ
        if LANE_DIRECTION[lane_index - 1] != LANE_DIRECTION[lane_index]:
            for line_offset in (-3, 3):
                for start_x, end_x in ((0, CROSSING_START_X - 40), (CROSSING_END_X + 40, SCREEN_WIDTH)):
                    pygame.draw.line(surface, YELLOW, project(start_x, marking_y + line_offset), project(end_x, marking_y + line_offset), 2)
        else:
            for dash_x in range(0, SCREEN_WIDTH, 60):
                if CROSSING_START_X - 40 < dash_x < CROSSING_END_X + 20:
                    continue
                pygame.draw.line(surface, WHITE, project(dash_x, marking_y), project(dash_x + 30, marking_y), 2)


def draw_crossing(surface):
    pygame.draw.line(surface, WHITE, project(CROSSING_START_X - 30, ROAD_TOP + 2), project(CROSSING_START_X - 30, ROAD_TOP + LANE_HEIGHT * 2), 4)
    pygame.draw.line(surface, WHITE, project(CROSSING_END_X + 30, ROAD_TOP + LANE_HEIGHT * 2), project(CROSSING_END_X + 30, ROAD_BOTTOM - 2), 4)
    stripe_y = ROAD_TOP + 8
    while stripe_y + 12 < ROAD_BOTTOM - 4:
        pygame.draw.polygon(surface, WHITE, [project(CROSSING_START_X, stripe_y), project(CROSSING_END_X, stripe_y),
                                             project(CROSSING_END_X, stripe_y + 13), project(CROSSING_START_X, stripe_y + 13)])
        stripe_y += 24


def draw_near_sidewalk(surface):
    fill_ground(surface, PAVEMENT_COLOR, ROAD_BOTTOM, WORLD_BOTTOM)
    draw_tiles(surface, PAVEMENT_LINE_COLOR, ROAD_BOTTOM, WORLD_BOTTOM)
    pygame.draw.line(surface, (226, 222, 212), project(0, ROAD_BOTTOM), project(SCREEN_WIDTH, ROAD_BOTTOM), 3)
    slab_y = project(0, WORLD_BOTTOM)[1]
    pygame.draw.rect(surface, SLAB_FRONT_COLOR, (0, slab_y, SCREEN_WIDTH, HEADS_UP_DISPLAY_Y - slab_y))


def draw_ground_labels(surface):
    label_safe = load_font(22, bold=True).render("ฝั่งปลอดภัย  SAFE ZONE", True, (140, 176, 130))
    surface.blit(label_safe, label_safe.get_rect(center=project(SCREEN_WIDTH / 2, 92)))
    label_start = load_font(18, bold=True).render("จุดเริ่มต้น", True, (176, 168, 150))
    surface.blit(label_start, (16, project(0, WORLD_BOTTOM - 22)[1]))


def draw_skid_marks(game):
    """simulation เก็บเส้นรอยเบรกและจำนวนครั้งที่ต้องจางไว้ ฟังก์ชันนี้วาดลง skid_mark_surface แล้วล้างคิว"""
    surface = game.skid_mark_surface
    for start, end, width in game.skid_segments:
        pygame.draw.line(surface, (22, 22, 26, 120), project(*start), project(*end), width)
    game.skid_segments.clear()
    for _ in range(game.skid_fades_pending):
        # คูณ alpha ด้วย 246/255 ทุกครึ่งวินาที รอยจึงค่อย ๆ จางหาย
        surface.fill((255, 255, 255, 246), special_flags=pygame.BLEND_RGBA_MULT)
    game.skid_fades_pending = 0
