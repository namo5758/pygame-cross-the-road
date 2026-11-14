"""Regression coverage for the status text actually rendered in the HUD."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from render_hud import draw_person_info


class PersonStatusTests(unittest.TestCase):
    def test_rendered_status(self):
        cases = [
            ({}, "รออยู่"),
            ({"is_walking": True}, "กำลังเดิน"),
            ({"injured": True, "is_walking": True}, "บาดเจ็บหนัก (เดินช้า)"),
            ({"down_time": 1, "injured": True}, "ล้มอยู่"),
            ({"burn_time": 3}, "กำลังไฟไหม้!"),
            ({"burn_time": 3, "down_time": 1, "injured": True}, "กำลังไฟไหม้!"),
            ({"saved": True, "is_walking": True}, "ปลอดภัยแล้ว"),
            ({"saved": True, "burn_time": 3}, "ปลอดภัยแล้ว"),
        ]
        for fuel in (False, True):
            for changes, expected in cases:
                with self.subTest(fuel=fuel, **changes):
                    attributes = dict(
                        index=0, alive=True, saved=False, fuel=fuel,
                        health=100, maximum_health=100, burn_time=0,
                        down_time=0, injured=False, is_walking=False,
                        information={"name": "Test", "skill_description": "", "cooldown": 0},
                    )
                    attributes.update(changes)
                    person = SimpleNamespace(**attributes)
                    game = SimpleNamespace(
                        hovered_person=lambda: person,
                        font_bold=Mock(), font_small=Mock(), font_regular=Mock(),
                    )
                    draw_person_info(game, Mock())
                    status = game.font_small.render.call_args.args[0]
                    self.assertEqual(status, f"HP 100/100  ·  {expected}")
                    title = game.font_bold.render.call_args.args[0]
                    self.assertEqual("ถังน้ำมัน!" in title, fuel)


if __name__ == "__main__":
    unittest.main()
