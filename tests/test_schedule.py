import unittest

from app.scheduler import (
    make_hash,
    normalize_schedule,
)


class ScheduleTests(unittest.TestCase):

    def test_order_does_not_matter(self):
        a = [
            {
                "ClID": "1",
                "SClID": "1",
                "Day": "2026-09-10",
                "ParaN": "1",
            },
            {
                "ClID": "2",
                "SClID": "1",
                "Day": "2026-09-10",
                "ParaN": "2",
            },
        ]

        b = list(reversed(a))

        self.assertEqual(
            make_hash(a),
            make_hash(b),
        )

    def test_different_schedule_has_different_hash(self):
        a = [
            {
                "ClID": "1",
                "SClID": "1",
                "room": "101",
            }
        ]

        b = [
            {
                "ClID": "1",
                "SClID": "1",
                "room": "418",
            }
        ]

        self.assertNotEqual(
            make_hash(a),
            make_hash(b),
        )

    def test_normalization(self):
        schedule = [
            {
                "ClID": "2",
                "Day": "2026-09-10",
                "ParaN": "2",
            },
            {
                "ClID": "1",
                "Day": "2026-09-10",
                "ParaN": "1",
            },
        ]

        result = normalize_schedule(
            schedule
        )

        self.assertEqual(
            result[0]["ClID"],
            "1",
        )

        self.assertEqual(
            result[1]["ClID"],
            "2",
        )


if __name__ == "__main__":
    unittest.main()