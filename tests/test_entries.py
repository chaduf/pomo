"""Work time entries: recorded at the end of a cycle, named in a form, written as .ics."""
import json

from support import PomoTestCase


class CycleEntriesTest(PomoTestCase):
    async def test_cycle_end_records_named_entries(self):
        async with self.run_app(cycles=2):
            await self.press("space")
            await self.advance(10 * 60)
            await self.press("space")          # a timer pause splits the work
            await self.advance(2 * 60)
            await self.press("space")
            await self.advance(13 * 60)
            await self.press("n")               # 1st work: 10 + 13 min, ended early by n
            await self.press("n")
            await self.advance(2 * 60)
            await self.press(*["minus"] * 5)    # 2nd work: 2 min, dropped; the 5th - ends it and the cycle
            self.assertEqual(self.screen_name(), "EntryForm")
            preview = str(self.app.screen.query_one("#preview").render())
            self.assertIn("…_work_1.1", preview)
            self.assertIn("(10 min)", preview)
            self.assertIn("(13 min)", preview)
            self.assertNotIn("work_2", preview)

            await self.press("ctrl+s")          # the title is required
            self.assertEqual(self.screen_name(), "EntryForm")
            await self.press(*"API", "enter", *"Refacto", "ctrl+s")
            self.assertEqual(self.screen_name(), "Screen")

            entries = self.recorded_entries()
            self.assertEqual([e["title"] for e in entries], ["API_work_1.1", "API_work_1.2"])
            self.assertEqual([round((e["end"] - e["start"]) / 60) for e in entries], [10, 13])
            self.assertEqual({e["description"] for e in entries}, {"Refacto"})
            ics_files = list(self.ics_dir.glob("*.ics"))
            self.assertEqual(len(ics_files), 1)
            self.assertIn("SUMMARY:API_work_1.2", ics_files[0].read_text())

    async def test_key_ending_the_cycle_is_not_typed_into_the_title(self):
        async with self.run_app(cycles=1):
            await self.press("space")
            await self.advance(10 * 60)
            await self.press("n")
            self.assertEqual(self.screen_name(), "EntryForm")
            self.assertEqual(self.app.screen.query_one("#title").value, "")

    async def test_single_entry_uses_the_title(self):
        async with self.run_app(cycles=1):
            await self.press("space")
            await self.advance(25 * 60)
            self.assertEqual(self.screen_name(), "EntryForm")
            await self.press(*"Solo", "ctrl+s")
            self.assertEqual([e["title"] for e in self.recorded_entries()], ["Solo"])

    async def test_short_work_is_not_recorded(self):
        async with self.run_app(cycles=1):
            await self.press("space")
            await self.advance(4 * 60)
            await self.press("n")
            self.assertEqual(self.screen_name(), "Screen")
            self.assertIn("No work to record", self.notifications()[-1])

    async def test_discard(self):
        async with self.run_app(cycles=1):
            await self.press("space")
            await self.advance(25 * 60)
            await self.pilot.click("#discard")
            await self.pilot.pause(0.3)
            self.assertEqual(self.recorded_entries(), [])
            self.assertEqual(self.notifications()[-1], "Work discarded")


class UnfinishedCycleTest(PomoTestCase):
    async def test_reset_asks_then_resets(self):
        async with self.run_app():
            await self.press("space")
            await self.advance(12 * 60)
            await self.press("r")
            self.assertEqual(self.screen_name(), "EntryForm")
            self.assertEqual(str(self.app.screen.query_one("#form-title").render()),
                             "Unfinished cycle: record your work")
            await self.press(*"Half", "ctrl+s")
            self.assertEqual([e["title"] for e in self.recorded_entries()], ["Half"])
            self.assertEqual(self.clock_text(), "25:00")
            self.assertEqual(self.info_text(), "Profile: classic  ·  Pomodoros: 0  ·  cycle 1/4")

    async def test_quit_asks_then_quits(self):
        async with self.run_app():
            await self.press("space")
            await self.advance(7 * 60)
            await self.press("q")
            self.assertEqual(self.screen_name(), "EntryForm")
            self.assertTrue(self.app.is_running)
            await self.pilot.click("#discard")
            await self.pilot.pause(0.3)
            self.assertFalse(self.app.is_running)


class RecoveryTest(PomoTestCase):
    async def test_work_of_a_dead_instance_is_offered(self):
        now = self.clock.time()
        self.pomo.DATA_DIR.mkdir(parents=True, exist_ok=True)
        (self.pomo.DATA_DIR / "current-999999.json").write_text(json.dumps({
            "profile": "deep", "ics_dir": str(self.ics_dir), "pending": [],
            "cycle": [{"work": 1, "start": now - 3600, "end": now - 3500}],   # 100 s: dropped
            "segment": {"work": 2, "start": now - 2000}, "last_seen": now - 800}))
        async with self.run_app():
            self.assertEqual(self.screen_name(), "EntryForm")
            self.assertEqual(str(self.app.screen.query_one("#form-title").render()),
                             "Unrecorded work from a previous session")
            await self.press(*"Late", "ctrl+s")
            entries = self.recorded_entries()
            self.assertEqual([(e["title"], e["profile"]) for e in entries], [("Late", "deep")])
            self.assertEqual(round((entries[0]["end"] - entries[0]["start"]) / 60), 20)
            self.assertFalse((self.pomo.DATA_DIR / "current-999999.json").exists())
