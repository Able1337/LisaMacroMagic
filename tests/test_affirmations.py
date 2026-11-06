from datetime import datetime,timedelta
import random
import unittest
from affirmations import PHRASES,FOX_HINT,TIME_HINT,PhraseSchedule


class PhraseTests(unittest.TestCase):
    def test_sixty_one_distinct_phrases_include_hints(self):
        self.assertEqual(len(PHRASES),61); self.assertEqual(len(set(PHRASES)),61)
        self.assertIn('7 кликов',FOX_HINT)
        self.assertEqual(PHRASES[-1],TIME_HINT)
        self.assertIn(TIME_HINT,PhraseSchedule(random.Random(1)).remaining)

    def test_same_clock_slot_does_not_consume_phrases(self):
        schedule=PhraseSchedule(random.Random(1))
        first=schedule.update(datetime(2026,10,16,8,1))
        count=len(schedule.remaining)
        self.assertEqual(schedule.update(datetime(2026,10,16,8,9,59)),first)
        self.assertEqual(len(schedule.remaining),count)
        self.assertNotEqual(schedule.update(datetime(2026,10,16,8,10)),first)

    def test_four_hint_windows_per_day(self):
        schedule=PhraseSchedule(random.Random(1)); hints=[]
        for slot in range(144):
            now=datetime(2026,10,16)+timedelta(minutes=slot*10)
            if schedule.update(now)==FOX_HINT: hints.append(now.hour)
        self.assertEqual(hints,[0,6,12,18])

    def test_no_regular_repeats_and_exhaustion_keeps_last(self):
        schedule=PhraseSchedule(random.Random(4)); seen=[]; last=None
        for slot in range(144):
            now=datetime(2026,10,16)+timedelta(minutes=slot*10)
            text=schedule.update(now)
            if text==FOX_HINT: continue
            if len(seen)<60:
                self.assertNotIn(text,seen); seen.append(text); last=text
            else: self.assertEqual(text,last)
        self.assertEqual(len(seen),60)

    def test_random_order_is_not_catalog_order(self):
        schedule=PhraseSchedule(random.Random(10))
        generated=[schedule.update(datetime(2026,10,16,1)+timedelta(minutes=i*10)) for i in range(5)]
        self.assertNotEqual(generated,list(PHRASES[:5]))

    def test_start_inside_hint_slot_then_normal(self):
        schedule=PhraseSchedule(random.Random(1))
        self.assertEqual(schedule.update(datetime(2026,10,16,12,9)),FOX_HINT)
        self.assertNotEqual(schedule.update(datetime(2026,10,16,12,10)),FOX_HINT)
