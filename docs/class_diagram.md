# Class Diagram — Cross the Road

`Game` เป็นศูนย์กลางของเกม: รับอินพุต เก็บสถานะ และสืบทอดพฤติกรรมจาก `GameSimulation` กับ `GameRenderer` ส่วนตัวละคร รถ โดรน และเอฟเฟกต์เป็นออบเจ็กต์ที่เกมจัดการ

## 1. โครงสร้างหลัก — ใครควบคุมเกม

อ่านจากบนลงล่าง: คลาสแม่ให้พฤติกรรม แล้ว `Game` รวมพฤติกรรมเหล่านั้นบนสถานะเดียวกัน

```mermaid
classDiagram
    direction TB

    class GameSimulation {
        +update(delta_time)
        +update_traffic(delta_time, pre_warm)
        +check_hits()
        +damage(person, amount, source, push_velocity)
        +check_end()
        +toggle_go(person)
        +use_ability(person)
        +start_selected_crossing()
    }

    class GameRenderer {
        +draw()
        +update_hover()
        +draw_ground_layers(surface)
        +draw_depth_sorted_objects(surface)
        +draw_flying_objects(surface)
        +draw_flash(surface)
        +present_world_with_shake(screen)
        +render_cache() dict
    }

    class Game {
        +str state
        +int level_index
        +dict current_level
        +bool paused
        +reset()
        +handle_event(event)
        +person_at(screen_x, screen_y)
        +run()
    }

    GameSimulation <|-- Game
    GameRenderer <|-- Game

    style Game fill:#fff1e8,stroke:#bf4520,color:#2d3142,stroke-width:2px
```

| คลาส | รับผิดชอบ | ไฟล์ |
| --- | --- | --- |
| **Game** | ตั้งค่าเกม รับคำสั่งผู้เล่น และควบคุม game loop | [cross_the_road.py](../cross_the_road.py) |
| GameSimulation | เดินเวลา เคลื่อนที่ ตรวจชน ตัดสินผลด่าน และคำสั่งของผู้เล่น (เดิน หยุด ใช้ความสามารถ) | [simulation.py](../simulation.py) |
| GameRenderer | อ่านสถานะแล้วกำหนดลำดับการวาด 1 เฟรม การวาดแต่ละอย่างเป็นฟังก์ชันใน `render_*.py` | [rendering.py](../rendering.py) |

`GameSimulation` และ `GameRenderer` ทำงานเป็น mixin: เมธอดใช้ `self` ของ `Game` โดยตรง ไม่มีออบเจ็กต์ simulation หรือ renderer แยกต่างหาก

## 2. คนและการจราจร — เกมเก็บอะไร และใครอ้างถึงใคร

`Game` จัดการคน รถ และโดรน ส่วน `Drone` อ้างถึงรถเป้าหมาย และ `Person` อ้างถึงคนที่อุ้มหรือคนที่อุ้มตนอยู่

```mermaid
classDiagram
    direction TB

    class Game {
        +list~Person~ people
        +list~Car~ cars
        +list~Drone~ drones
        +set~Person~ selected_people
    }

    class Person {
        +str kind
        +float health
        +list path
        +Person carrying
        +Person carried_by
        +speed() float
        +set_target(target_x, target_y)
    }

    class Car {
        +str kind
        +int lane
        +float speed
        +bool wreck
        +bool towed
        +blocks(lane_index) bool
        +dangerous() bool
        +hits(person_x, person_y, radius) bool
    }

    class Drone {
        +Car car
        +str state
        +float time_elapsed
        +bool done
        +update(delta_time)
    }

    Game "1" *-- "0..*" Person : people
    Game "1" *-- "0..*" Car : cars
    Game "1" *-- "0..*" Drone : drones
    Drone "0..1" --> "1" Car : car
    Person "0..1" --> "0..1" Person : carrying

    style Game fill:#fff1e8,stroke:#bf4520,color:#2d3142,stroke-width:2px
```

- **Person** เก็บสุขภาพ เส้นทาง และสถานะตัวละคร การชนและความเสียหายจัดการโดย `GameSimulation`
- **Car** รู้ขนาดและสถานะของตนเอง รวมถึงตรวจว่าทับเลนหรือชนตำแหน่งคนหรือไม่
- **Drone** มี `update()` ของตนเองเพื่อบินเข้า เกี่ยวรถ ยก และนำรถออกจากฉาก รถเป้าหมายยังเป็นออบเจ็กต์เดียวกับใน `Game.cars`
- `carrying` กับ `carried_by` เป็นลิงก์กลับกัน และเป็น `None` ได้ ส่วน `selected_people` อ้างถึงคนเดิมใน `people`

## 3. เอฟเฟกต์ในโลกเกม — ข้อมูลที่มีอายุจำกัด

เอฟเฟกต์ทุกชนิดเก็บข้อมูลเป็นหลัก: `GameSimulation` อัปเดตและลบเมื่อหมดอายุ ส่วน `GameRenderer` นำข้อมูลไปวาด

```mermaid
classDiagram
    direction TB

    class Game {
        +list~Puddle~ puddles
        +list~Fire~ fires
        +list~Particle~ particles
        +list~FloatingText~ floating_messages
        +list~Toast~ toast_messages
        +list~ImpactText~ impact_messages
    }

    class Puddle {
        +float x
        +float y
        +float radius
        +float life
        +set~Car~ hit_cars
    }

    class Fire {
        +float x
        +float y
        +float radius
        +float life
    }

    class Particle {
        +float z
        +float velocity_z
        +float gravity
        +float life
        +str shape
    }

    class FloatingText {
        +str text
        +float height
        +float life
    }

    class Toast {
        +str text
        +float life
    }

    class ImpactText {
        +str text
        +float size
        +float rotation
        +float life
    }

    Game "1" *-- "0..*" Puddle : puddles
    Game "1" *-- "0..*" Fire : fires
    Game "1" *-- "0..*" Particle : particles
    Game "1" *-- "0..*" FloatingText : floating_messages
    Game "1" *-- "0..*" Toast : toast_messages
    Game "1" *-- "0..*" ImpactText : impact_messages

    style Game fill:#fff1e8,stroke:#bf4520,color:#2d3142,stroke-width:2px
```

| คลาส | ความหมายในเกม |
| --- | --- |
| Puddle | คราบเลือดหรือไอศกรีมที่ทำให้ลื่น บันทึกรถที่ได้รับผลไปแล้ว |
| Fire | พื้นที่ไฟไหม้ กำหนดตำแหน่ง รัศมี และอายุ |
| Particle | เศษชิ้นส่วน ควัน หรือประกาย มีตำแหน่ง ความเร็ว แรงโน้มถ่วง และอายุ |
| FloatingText | ข้อความเล็กลอยขึ้นจากจุดในโลก เช่น "ลื่น!" "-12" (dataclass) |
| Toast | ข้อความแจ้งเตือนกลางจอด้านบน (dataclass) |
| ImpactText | คำใหญ่ตอนชน เช่น "โครม!" "ตูม!!" (dataclass) |

Person, Car, Drone, Puddle, Fire, Particle และคลาสข้อความทั้ง 3 อยู่ในไฟล์ entities.py ส่วน Game อยู่ในไฟล์ cross_the_road.py