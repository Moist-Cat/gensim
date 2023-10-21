import unittest
import unittest.mock

from gensim.cronie import Notice


class TestEventNotice(unittest.TestCase):
    def test_insert(self):
        dates = (1, 7, 3, 2, 6, 8, 4, 2)

        head = Notice(date=0, event_id=None)

        for date in dates:
            head.insert(Notice(date=date, event_id=None))

        self.assertEqual([0] + sorted(dates), list(head.all()))

    def test_pop(self):
        dates = (1, 7, 3, 2, 6, 8, 4, 2)

        head = Notice(date=0, event_id=None)

        for date in dates:
            head.insert(Notice(date=date, event_id=None))

        head = head.pop()
        self.assertEqual(head.next(), head)
        self.assertEqual(head.date, 1)

        head = head.pop()
        self.assertEqual(head.next(), head)
        self.assertEqual(head.date, 2)

    def test_yield_events(self):
        dates = (1, 2, 3, 4, 5)
        events = ("b", "c", "d", "e", "f")
        head = Notice(date=0, event_id="a")

        for date in dates:
            head.insert(Notice(date=date, event_id=events[date - 1]))

        self.assertEqual(
            {"event_ids": ["a", "b", "c", "d"], "notice": head.get(3)},
            head.event_ids(date_start=-1, date_end=3),
        )

    def test_yield_event_from_date(self):
        dates = (1, 2, 3, 4, 5)
        events = ("b", "c", "d", "e", "f")
        head = Notice(date=0, event_id="a")

        for date in dates:
            head.insert(Notice(date=date, event_id=events[date - 1]))

        self.assertEqual(
            {"event_ids": ["d", "e", "f"], "notice": head.get(5)},
            head.event_ids(date_start=2, date_end=5),
        )
