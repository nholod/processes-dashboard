import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "generate_dashboard.py"
SPEC = importlib.util.spec_from_file_location("dashboard_generator", MODULE_PATH)
dashboard = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(dashboard)


class CronFieldParserTests(unittest.TestCase):
    def test_single_value(self):
        self.assertEqual(dashboard.expand_cron_field("10", 0, 59), [10])

    def test_list(self):
        self.assertEqual(dashboard.expand_cron_field("8,17,22", 0, 23), [8, 17, 22])

    def test_range(self):
        self.assertEqual(dashboard.expand_cron_field("10-12", 0, 23), [10, 11, 12])

    def test_wildcard_step(self):
        self.assertEqual(dashboard.expand_cron_field("*/20", 0, 59), [0, 20, 40])

    def test_range_step(self):
        self.assertEqual(dashboard.expand_cron_field("10-22/4", 0, 23), [10, 14, 18, 22])

    def test_list_range_and_step(self):
        self.assertEqual(
            dashboard.expand_cron_field("1,5-9/2,12", 0, 23),
            [1, 5, 7, 9, 12],
        )

    def test_invalid_range_rejected(self):
        with self.assertRaises(ValueError):
            dashboard.expand_cron_field("22-10", 0, 23)

    def test_zero_step_rejected(self):
        with self.assertRaises(ValueError):
            dashboard.expand_cron_field("*/0", 0, 59)


class ScheduleLabelTests(unittest.TestCase):
    def label(self, expr):
        return dashboard.schedule_label(
            {"kind": "cron", "expr": expr, "tz": "Europe/Moscow"}
        )

    def test_hour_range(self):
        self.assertEqual(
            self.label("20 10-22 * * *"),
            "Ежедневно 10:20, 11:20, 12:20, 13:20, 14:20, 15:20, "
            "16:20, 17:20, 18:20, 19:20, 20:20, 21:20, 22:20 МСК",
        )

    def test_multiple_hours(self):
        self.assertEqual(
            self.label("15 8,17 * * *"),
            "Ежедневно 08:15, 17:15 МСК",
        )

    def test_wildcard_step(self):
        self.assertEqual(self.label("*/15 * * * *"), "Каждые 15 минут")

    def test_range_with_minute_step(self):
        self.assertEqual(
            self.label("*/30 7-22 * * *"),
            "Ежедневно каждые 30 минут, часы 7-22 МСК",
        )

    def test_unsupported_expression_falls_back(self):
        self.assertEqual(
            self.label("x 10-22 * * *"),
            "Cron: x 10-22 * * * МСК",
        )


if __name__ == "__main__":
    unittest.main()
