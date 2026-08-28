"""The Minutes list: a title first, and a tidy line under it.

_load_minutes is exercised unbound against a bare list widget: everything it
does is read the index and format rows, and building the whole settings
window here would only re-test the scaffolding test_ui already covers.
"""

import unittest
from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication, QListWidget

import meeting
import settings_ui
from tests.support import DikteTest


class MinutesList(DikteTest):
    def setUp(self):
        super().setUp()
        self.app = QApplication.instance() or QApplication([])

    def save_row(self, **overrides):
        row = meeting.new_entry("20260801-143000", 125.4)
        row.update(overrides)
        meeting.cfg.save_meeting(row)
        return row

    def load(self):
        # The widget must outlive the call: an unowned QListWidget dropped
        # mid-expression takes its items' C++ objects down with it.
        self._list = QListWidget()
        dummy = SimpleNamespace(minutes_list=self._list)
        settings_ui.SettingsWindow._load_minutes(dummy)
        return self._list

    def test_the_title_leads_and_the_details_follow(self):
        self.save_row(title="Weekly Planning")
        lines = self.load().item(0).text().splitlines()
        self.assertEqual(lines[0], "Weekly Planning")
        self.assertEqual(lines[1],
                         "1 Aug 2026 14:30  ·  2 min  ·  waiting to be "
                         "written up")

    def test_an_untitled_meeting_says_so(self):
        self.save_row()
        lines = self.load().item(0).text().splitlines()
        self.assertEqual(lines[0], "Meeting")
        self.assertIn("1 Aug 2026 14:30", lines[1])

    def test_a_finished_meeting_carries_no_status_noise(self):
        self.save_row(title="Weekly Planning", status="done")
        second = self.load().item(0).text().splitlines()[1]
        self.assertEqual(second, "1 Aug 2026 14:30  ·  2 min")

    def test_an_unparseable_stamp_still_says_something(self):
        self.save_row(title="Weekly Planning", ts="")
        lines = self.load().item(0).text().splitlines()
        self.assertEqual(lines[0], "Weekly Planning")
        self.assertIn("2 min", lines[1])

    def test_the_newest_meeting_is_first(self):
        self.save_row(title="Earlier", base="20260801-100000")
        self.save_row(title="Later", base="20260801-170000")
        items = self.load()
        self.assertEqual(items.item(0).text().splitlines()[0], "Later")
        self.assertEqual(items.item(1).text().splitlines()[0], "Earlier")


if __name__ == "__main__":
    unittest.main()
