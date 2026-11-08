# Sequence diagram — เลือกกลุ่มแล้วข้ามพร้อมกัน (Shift-click)

ฉากนี้คือ feature ที่ใช้ในพรีเซนต์: ผู้เล่นกด Shift ค้างแล้วคลิกเลือกหลายคน
พอปล่อย Shift ทุกคนในกลุ่มเริ่มเดินในเฟรมเดียวกัน จากนั้น game loop
ขยับคน ตรวจการชน และเช็กแพ้ชนะทุกเฟรม

```mermaid
sequenceDiagram
    actor Player as ผู้เล่น
    participant game as game (Game)
    participant p as p (Person)
    participant car as car (Car)

    Note over Player,game: เลือกคนเข้ากลุ่ม (ยังไม่มีใครเดิน)
    loop ทุกครั้งที่ Shift + คลิกซ้าย
        Player->>game: handle_event(MOUSEBUTTONDOWN)
        game->>game: person_at(x, y)
        Note right of game: project() แปลงตำแหน่งคนเป็นพิกัดจอ<br/>แล้วหาคนที่ใกล้จุดคลิกที่สุด
        game->>game: toggle_person_selection(p)
        Note right of game: เพิ่มหรือเอาออกจาก selected_people (set)
    end

    Player->>game: handle_event(KEYUP: ปล่อย Shift)
    game->>game: start_selected_crossing()
    Note right of game: กรองคนที่ตาย / ข้ามสำเร็จ / ถูกแบกอยู่ออกก่อน
    loop ทุกคนใน selected_people
        game->>game: plan_crossing(p)
        game->>p: set_target(x, GOAL_Y - 30)
        p-->>game: p.path = waypoints ผ่านทางม้าลาย
    end
    game->>game: toast("กลุ่ม N คนเริ่มข้าม!")

    loop ทุกเฟรม: run() → update(delta_time)
        game->>game: update_person(p)
        game->>game: step_towards(p) → move_constrained(p)
        game->>game: check_hits()
        game->>car: hits(p.x, p.y)
        car-->>game: True / False
        alt ชน (True)
            game->>game: car_hit(p, car) → damage(p)
        else ถึงฝั่งปลอดภัย (p.y < GOAL_Y)
            game->>game: save(p)
        end
        game->>game: check_end()
    end
```

## ไฟล์และฟังก์ชันที่เกี่ยวข้อง

| ขั้นตอน | ฟังก์ชัน | ไฟล์ |
|---|---|---|
| รับคลิกและปุ่ม | `Game.handle_event()` | `cross_the_road.py` |
| หาคนที่ถูกคลิก | `Game.person_at()`, `project()` | `cross_the_road.py`, `geometry.py` |
| เลือก / เริ่มข้ามเป็นกลุ่ม | `toggle_person_selection()`, `start_selected_crossing()` | `cross_the_road.py` |
| วางเส้นทางผ่านทางม้าลาย | `Game.plan_crossing()`, `Person.set_target()` | `cross_the_road.py`, `entities.py` |
| ขยับคนทุกเฟรม | `update_person()`, `step_towards()`, `move_constrained()` | `simulation.py` |
| ตรวจการชน | `check_hits()`, `Car.hits()`, `car_hit()`, `damage()` | `simulation.py`, `entities.py` |
| ถึงฝั่ง / จบด่าน | `save()`, `check_end()` | `simulation.py` |

หมายเหตุ: `Game` สืบทอดจาก `GameSimulation` และ `GameRenderer` ฟังก์ชันใน
`simulation.py` จึงถูกเรียกผ่าน `self` ของ object `game` ตัวเดียวกัน
ใน diagram เลยแสดงเป็นลูกศรที่ชี้กลับเข้าหา `game`
