import datetime
import json
import unittest

import config as cfg
from tests.support import DikteTest

from ui import stats


class StatsTests(DikteTest):
    def test_empty_history(self):
        self.assertEqual(stats.history_stats(limit=200)["total"], 0)
        self.assertEqual(stats.provider_usage(), {})
        self.assertEqual(len(stats.daily_counts(days=7)), 7)
        for _, c in stats.daily_counts(days=7):
            self.assertEqual(c, 0)

    def test_history_counts_and_provider(self):
        today = datetime.date.today().isoformat()
        cfg.append_history({"ts": f"{today} 10:00:00", "text": "hello", "duration": 2, "provider": "local"})
        cfg.append_history({"ts": f"{today} 11:00:00", "text": "hi", "duration": 3, "provider": "openai"})
        cfg.append_history({"ts": f"{today} 12:00:00", "text": "", "duration": 1, "provider": "local"})
        hs = stats.history_stats(limit=200)
        self.assertEqual(hs["total"], 3)
        self.assertEqual(hs["by_provider"].get("local"), 2)
        self.assertEqual(hs["by_provider"].get("openai"), 1)
        # success rate: 2 with text out of 3
        self.assertAlmostEqual(hs["success_rate"], 66.6, delta=1)
        self.assertAlmostEqual(hs["avg_duration"], 2.0, delta=0.1)

    def test_daily_counts(self):
        today = datetime.date.today()
        yesterday = (today - datetime.timedelta(days=1)).isoformat()
        today_s = today.isoformat()
        cfg.append_history({"ts": f"{yesterday} 09:00:00", "text": "a", "duration": 1, "provider": "local"})
        cfg.append_history({"ts": f"{today_s} 09:00:00", "text": "b", "duration": 1, "provider": "local"})
        cfg.append_history({"ts": f"{today_s} 10:00:00", "text": "c", "duration": 1, "provider": "local"})
        dc = stats.daily_counts(days=3)
        self.assertEqual(len(dc), 3)
        # last entry is today
        self.assertEqual(dc[-1][0], today_s)
        self.assertEqual(dc[-1][1], 2)
        self.assertEqual(dc[-2][0], yesterday)
        self.assertEqual(dc[-2][1], 1)

    def test_meetings_stats_empty(self):
        ms = stats.meetings_stats()
        self.assertEqual(ms["total"], 0)
        self.assertEqual(ms["by_status"], {})

    def test_meetings_stats_with_data(self):
        today = datetime.date.today().isoformat()
        cfg.save_meeting({"base": "2026-01-01_120000", "ts": f"{today} 10:00:00", "title": "M1", "status": "done", "duration": 600})
        cfg.save_meeting({"base": "2026-01-02_120000", "ts": f"{today} 11:00:00", "title": "M2", "status": "failed", "duration": 1200})
        ms = stats.meetings_stats()
        self.assertEqual(ms["total"], 2)
        self.assertEqual(ms["by_status"].get("done"), 1)
        self.assertEqual(ms["by_status"].get("failed"), 1)

    def test_provider_usage(self):
        today = datetime.date.today().isoformat()
        cfg.append_history({"ts": f"{today} 10:00:00", "text": "a", "duration": 1, "provider": "local"})
        cfg.append_history({"ts": f"{today} 11:00:00", "text": "b", "duration": 1, "provider": "local"})
        pu = stats.provider_usage()
        self.assertEqual(pu.get("local"), 2)
