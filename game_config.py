"""ค่าคงที่ทั้งหมดของเกม: ขนาดจอ ถนน ด่าน สี รถ และตัวละคร"""

# ขนาดหน้าต่าง (พิกเซล) และ FPS
SCREEN_WIDTH, SCREEN_HEIGHT = 1024, 720
FRAMES_PER_SECOND = 60

# กล้อง 2.5D ดู geometry.project()
ORIGIN_Y = 54
VERTICAL_SCALE = 0.8
HEIGHT_SCALE = 0.8

# y น้อย = ไกล ฝั่งปลอดภัยอยู่เหนือถนน
GOAL_Y = 120
ROAD_TOP, ROAD_BOTTOM = 120, 480
LANES = 4
# 4 เลนลึกเท่ากัน
LANE_HEIGHT = (ROAD_BOTTOM - ROAD_TOP) / LANES
WORLD_BOTTOM = 620
# ช่วง x ของทางม้าลาย คนลงถนนได้เฉพาะตรงนี้
CROSSING_START_X, CROSSING_END_X = 420, 604
# y บนจอที่แถบล่าง (HUD) เริ่ม
HEADS_UP_DISPLAY_Y = 568

# ทิศรถแต่ละเลน 1 = ไปขวา, -1 = ไปซ้าย ความเร็วเป็นหน่วยโลกต่อวินาที
LANE_DIRECTION = [1, 1, -1, -1]
LANE_SPEED = [175, 215, 230, 165]

# ด่าน: speed = ตัวคูณความเร็ว, gap = ช่วงสุ่มระหว่างรถ (วินาที), target = ต้องรอดกี่คน
# mix เป็นน้ำหนักการสุ่ม ไม่ใช่จำนวนรถ
LEVELS = [
    dict(name="ด่าน 1 · ถนนสุขุมวิทชานเมือง", speed=1.0, gap=(3.0, 5.5), target=6,
         mix=dict(car=55, truck=6, moto=6, sidecar=14, icecream=12, tanker=7)),
    dict(name="ด่าน 2 · ถนนสุขุมวิทชั้นใน", speed=1.15, gap=(2.3, 4.4), target=6,
         mix=dict(car=45, truck=10, moto=18, sidecar=10, icecream=8, tanker=9)),
    dict(name="ด่าน 3 · แยกอโศกชั่วโมงเร่งด่วน", speed=1.35, gap=(1.7, 3.4), target=7,
         mix=dict(car=40, truck=12, moto=20, sidecar=8, icecream=8, tanker=12)),
]

# สี (R, G, B)
# ถนน ทางเท้า ฝั่งปลอดภัย
BACKGROUND_COLOR = (30, 33, 40)
ASPHALT = (62, 65, 72)
ASPHALT_SPECK = (70, 73, 80)
PAVEMENT_COLOR = (201, 194, 178)
PAVEMENT_LINE_COLOR = (182, 175, 160)
GOAL_PAVEMENT_COLOR = (178, 208, 168)
GOAL_LINE_COLOR = (160, 190, 150)
SLAB_FRONT_COLOR = (120, 114, 104)
# เส้นถนนและรายละเอียดตัวละคร
WHITE = (238, 238, 232)
YELLOW = (240, 190, 40)
SKIN_COLOR = (238, 198, 160)
BLOOD = (128, 10, 18)
BLOOD_HIGHLIGHT = (178, 36, 42)
GLASS_COLOR = (70, 96, 120)
# สี UI: เขียว = ดี, เหลือง = เน้น, แดง = อันตราย
PANEL_COLOR = (23, 26, 32)
PANEL_2_COLOR = (36, 40, 49)
TEXT_COLOR = (232, 232, 226)
MUTED_COLOR = (150, 154, 162)
ACCENT_COLOR = (250, 204, 60)
GOOD_COLOR = (110, 200, 120)
BAD_COLOR = (230, 80, 70)

# สีรถแต่ละชนิด สุ่มตอนรถเกิด
CAR_COLORS = [(214, 62, 58), (58, 120, 210), (236, 236, 230), (40, 44, 52),
              (230, 170, 40), (70, 160, 120), (160, 166, 176)]
TRUCK_COLORS = [(60, 110, 170), (200, 90, 40), (90, 140, 70)]
MOTORCYCLE_COLORS = [(30, 30, 36), (180, 30, 40), (40, 70, 160)]
SIDECAR_COLORS = [(70, 120, 90), (60, 90, 150), (150, 110, 60)]
ICECREAM_COLORS = [(250, 196, 214), (190, 226, 246), (250, 236, 170)]
TANKER_COLORS = [(230, 232, 228)]
VEHICLE_COLORS = {
    "truck": TRUCK_COLORS,
    "moto": MOTORCYCLE_COLORS,
    "sidecar": SIDECAR_COLORS,
    "icecream": ICECREAM_COLORS,
    "tanker": TANKER_COLORS,
}
# สีแอ่งไอติม (ลื่นเหมือนเลือด)
ICECREAM_GOO = [(250, 190, 212), (252, 246, 232), (140, 92, 62), (190, 230, 200)]

# ขนาดรถเป็นหน่วยโลก, speed คูณความเร็วเลน, damage = ความเสียหายพื้นฐานตอนชนคน
VEHICLES = {
    "car": dict(length=84, width=48, height=30, speed=1.0, damage=45),
    "truck": dict(length=150, width=58, height=58, speed=0.85, damage=70),
    "moto": dict(length=38, width=16, height=30, speed=1.3, damage=28),
    "sidecar": dict(length=44, width=40, height=30, speed=0.95, damage=32),
    "icecream": dict(length=96, width=50, height=46, speed=0.8, damage=40),
    "tanker": dict(length=172, width=56, height=56, speed=0.75, damage=80),
}

# ตัวละคร: HP ความเร็วเดิน cooldown (วินาที) และข้อความ
PERSON_TYPES = {
    "warden": dict(name="ตำรวจจราจร", health=100, short_name="ตำรวจ", color=(40, 86, 196), speed=70, cooldown=10.0,
                   skill_description="ยกป้ายหยุดรถ: หยุดรถเลนตัวเองและเลนถัดไปเป็นเวลา 3 วินาที"),
    "runner": dict(name="นักวิ่ง", health=80, short_name="นักวิ่ง", color=(40, 168, 92), speed=78, cooldown=6.0,
                   skill_description="วิ่งสปรินต์ x2.2 ชั่วคราว แต่จะเหนื่อยหลังจากนั้น"),
    "grandma": dict(name="คุณยาย", health=60, short_name="คุณยาย", color=(150, 92, 182), speed=36, cooldown=0.0,
                    skill_description="(ติดตัว) รถในระยะใกล้จะชะลอความเร็วลง"),
    "kid": dict(name="เด็ก", health=60, short_name="เด็ก", color=(236, 186, 36), speed=92, cooldown=0.0,
                skill_description="(ติดตัว) ถ้าอยู่คนเดียวเกิน 2 วิ จะตกใจเดินสะเปะสะปะ"),
    "strong": dict(name="คนแข็งแรง", health=150, short_name="จอมพลัง", color=(228, 118, 40), speed=64, cooldown=0.3,
                   skill_description="อุ้ม / วางคนอื่น (ช่วยพาคนเจ็บหรือเด็กข้ามถนนได้)"),
    "citizen": dict(name="ประชาชนทั่วไป", health=100, short_name="ทั่วไป", color=(124, 134, 146), speed=64, cooldown=0.0,
                    skill_description="คนเดินถนนทั่วไป บางคนอาจถือถังน้ำมัน"),
}
# 10 คนที่เกิดทุกด่าน ชนิดซ้ำ = มีหลายคน
ROSTER = ["warden", "runner", "grandma", "kid", "kid", "strong",
          "citizen", "citizen", "citizen", "citizen"]
