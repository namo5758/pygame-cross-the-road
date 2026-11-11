"""คณิตศาสตร์ที่ใช้ร่วมกันทั้งเกม: แปลงพิกัดโลก <-> จอ, หมุนจุด, ผสมสี, วาดกล่อง 3 มิติ"""

import math
import pygame

from game_config import (
    CROSSING_START_X,
    CROSSING_END_X,
    HEIGHT_SCALE,
    LANE_HEIGHT,
    ORIGIN_Y,
    ROAD_BOTTOM,
    ROAD_TOP,
    VERTICAL_SCALE,
)


def clamp(value, minimum_value, maximum_value):
    return minimum_value if value < minimum_value else maximum_value if value > maximum_value else value


def shade(color, factor):
    """factor < 1 = เข้มขึ้น, > 1 = สว่างขึ้น (ตัดให้อยู่ใน 0..255)"""
    return tuple(max(0, min(255, int(channel * factor))) for channel in color[:3])


def mix(first_color, second_color, blend_ratio):
    """ผสมสีตามสัดส่วน: 0 = สีแรก, 1 = สีที่สอง"""
    return tuple(int(first_color[index] + (second_color[index] - first_color[index]) * blend_ratio) for index in range(3))


def project(world_x, world_y, world_z=0.0):
    """พิกัดโลก (x, y, z) -> พิกัดจอ"""
    return world_x, ORIGIN_Y + world_y * VERTICAL_SCALE - world_z * HEIGHT_SCALE


def lane_center(lane_index):
    return ROAD_TOP + LANE_HEIGHT * (lane_index + 0.5)


def paired_lane(lane_index):
    """เลนข้าง ๆ ที่รถวิ่งทางเดียวกัน: 0 กับ 1, 2 กับ 3"""
    return lane_index + 1 if lane_index % 2 == 0 else lane_index - 1


def lane_of(world_y):
    """เลนที่ y นี้อยู่ (นับจาก 0) หรือ None ถ้าไม่ได้อยู่บนถนน"""
    return int((world_y - ROAD_TOP) // LANE_HEIGHT) if ROAD_TOP <= world_y < ROAD_BOTTOM else None


def in_road(world_y):
    return ROAD_TOP < world_y < ROAD_BOTTOM


def in_band(world_x):
    """อยู่ในแนวทางม้าลายไหม"""
    return CROSSING_START_X <= world_x <= CROSSING_END_X


def box_corners(center_x, center_y, length, width, angle):
    """มุมทั้ง 4 ของสี่เหลี่ยมที่หมุน angle เรเดียน (ใช้ rotation matrix: cos/sin)"""
    cosine_angle, sine_angle = math.cos(angle), math.sin(angle)
    half_length = length / 2
    half_width = width / 2
    return [
        (center_x + local_x * cosine_angle - local_y * sine_angle,
         center_y + local_x * sine_angle + local_y * cosine_angle)
        for local_x, local_y in (
            (half_length, half_width),
            (-half_length, half_width),
            (-half_length, -half_width),
            (half_length, -half_width)
        )
    ]


def local(center_x, center_y, angle, local_x, local_y):
    """จุดที่เยื้อง (local_x, local_y) จากจุดกลางของวัตถุที่หมุนอยู่ -> พิกัดโลก"""
    cosine_angle, sine_angle = math.cos(angle), math.sin(angle)
    return center_x + local_x * cosine_angle - local_y * sine_angle, center_y + local_x * sine_angle + local_y * cosine_angle


def draw_box(surface, center_x, center_y, length, width, z_bottom, z_top, angle, color, top_color=None, outline=True):
    """กล่อง 3 มิติ: วาดเฉพาะด้านข้างที่หันเข้ากล้อง (back-face culling) แล้วปิดด้วยฝาบน"""
    corners = box_corners(center_x, center_y, length, width, angle)
    for index in range(4):
        corner_start = corners[index]
        corner_end = corners[(index + 1) % 4]
        normal_x = corner_end[1] - corner_start[1]
        normal_y = -(corner_end[0] - corner_start[0])
        midpoint_x = (corner_start[0] + corner_end[0]) / 2 - center_x
        midpoint_y = (corner_start[1] + corner_end[1]) / 2 - center_y
        if normal_x * midpoint_x + normal_y * midpoint_y < 0:
            normal_x, normal_y = -normal_x, -normal_y
        normal_length = math.hypot(normal_x, normal_y) or 1
        normal_x, normal_y = normal_x / normal_length, normal_y / normal_length
        if normal_y > 0.01:
            side_face = [
                project(corner_start[0], corner_start[1], z_bottom),
                project(corner_end[0], corner_end[1], z_bottom),
                project(corner_end[0], corner_end[1], z_top),
                project(corner_start[0], corner_start[1], z_top)
            ]
            pygame.draw.polygon(surface, shade(color, 0.64 + 0.16 * normal_x), side_face)
    top_face = [project(corner[0], corner[1], z_top) for corner in corners]
    pygame.draw.polygon(surface, top_color or shade(color, 1.1), top_face)
    if outline:
        pygame.draw.polygon(surface, shade(color, 0.45), top_face, 1)
