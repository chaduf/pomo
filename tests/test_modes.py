"""Unit tests of the mode objects, without Textual: the timer logic and the events it reports."""
from support import ModeTestCase


class StopwatchModeTest(ModeTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.sw = self.pomo.StopwatchMode(self.clock.monotonic)

    def run_for(self, seconds: float) -> None:
        self.clock.advance(seconds)
        self.sw.tick()

    def test_starts_idle(self):
        self.assertTrue(self.sw.idle)
        self.assertFalse(self.sw.running)
        self.assertEqual(self.sw.view().clock, "00:00.0")
        self.assertEqual(set(self.sw.actions), {"lap"})

    def test_counts_only_while_running(self):
        self.run_for(5)
        self.assertEqual(self.sw.elapsed, 0)
        self.sw.toggle()
        self.run_for(2.5)
        self.sw.toggle()
        self.run_for(10)
        self.assertEqual(self.sw.view().clock, "00:02.5")
        self.assertFalse(self.sw.idle)

    def test_toggle_counts_the_time_since_the_last_tick(self):
        self.sw.toggle()
        self.clock.advance(1.2)
        self.sw.toggle()  # no tick in between
        self.assertAlmostEqual(self.sw.elapsed, 1.2)

    def test_laps(self):
        self.sw.lap()  # ignored while stopped
        self.sw.toggle()
        for seconds in (2, 1, 3):
            self.run_for(seconds)
            self.sw.lap()
        self.assertEqual(self.sw.lap_rows(), [("3", "00:03.0", "red", "00:06.0"),
                                              ("2", "00:01.0", "green", "00:03.0"),
                                              ("1", "00:02.0", "", "00:02.0")])
        self.assertEqual(self.sw.view().info, "Laps: 3")

    def test_skip_records_a_lap(self):
        self.sw.toggle()
        self.run_for(4)
        self.sw.skip()
        self.assertEqual(len(self.sw.laps), 1)

    def test_reset(self):
        self.sw.toggle()
        self.run_for(3)
        self.sw.lap()
        self.sw.reset()
        self.assertTrue(self.sw.idle)
        self.assertEqual(self.sw.laps, [])
        self.assertIsNone(self.sw.view().laps)

    def test_interrupt_has_nothing_to_record(self):
        self.sw.toggle()
        self.assertEqual(self.sw.interrupt("quit"), [])
        self.assertEqual(self.sw.unrecorded(), (None, []))

    def test_waybar_state(self):
        self.sw.toggle()
        self.run_for(7.9)
        data, key, tick = self.sw.waybar_state(self.clock.time())
        self.assertEqual((data["mode"], data["elapsed"], data["running"]), ("stopwatch", 7, True))
        self.assertEqual(tick, 7)


class PomodoroModeTest(ModeTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.reported: list[tuple] = []
        p = self.pomo
        events = p.PomodoroEvents(
            hook=lambda which, env: self.reported.append(("hook", which, env["POMO_EVENT"])),
            announce=lambda title, body, icon: self.reported.append(("announce", title)),
            notice=lambda message, severity: self.reported.append(("notice", message, severity)),
            work_changed=lambda: None,
            cycle_complete=lambda: self.reported.append(("cycle_complete",)))
        settings = {**p.DEFAULTS, "cycles": 2}
        self.pm = p.PomodoroMode(self.clock.monotonic, self.clock.time, settings, "classic", events)

    def run_for(self, seconds: float) -> None:
        self.clock.advance(seconds)
        self.pm.tick()

    def hooks(self) -> list[tuple]:
        return [r[1:] for r in self.reported if r[0] == "hook"]

    def test_starts_idle(self):
        view = self.pm.view()
        self.assertTrue(self.pm.idle)
        self.assertEqual((view.title, view.clock), ("🍅  Work (paused)", "25:00"))
        self.assertEqual(view.info, "Profile: classic  ·  Pomodoros: 0  ·  cycle 1/2")
        self.assertEqual(view.progress, (0, 1500))
        self.assertEqual(self.reported, [])

    def test_work_then_short_break(self):
        self.pm.toggle()
        self.run_for(25 * 60)
        self.assertEqual(self.pm.phase, "short")
        self.assertEqual(self.hooks(), [("start", "start"), ("end", "end")])
        self.assertIn(("announce", "☕ Short break"), self.reported)
        self.assertEqual(len(self.pm.cycle), 1)  # the work became a segment
        self.assertEqual(self.pm.view().info, "Profile: classic  ·  Pomodoros: 1  ·  cycle 2/2")

    def test_long_break_completes_the_cycle(self):
        self.pm.toggle()
        self.run_for(25 * 60)
        self.pm.skip()          # end of the short break
        self.run_for(25 * 60)
        self.assertEqual(self.pm.phase, "long")
        self.assertEqual(self.reported[-1], ("cycle_complete",))
        segments = self.pm.take_cycle()
        self.assertEqual([s["work"] for s in segments], [1, 2])
        self.assertEqual(self.pm.cycle, [])

    def test_pause_splits_the_work_segment(self):
        self.pm.toggle()
        self.run_for(600)
        self.pm.toggle()
        self.assertEqual(self.hooks()[-1], ("end", "pause"))
        self.pm.toggle()
        self.assertEqual(self.hooks()[-1], ("start", "resume"))
        self.run_for(300)
        self.pm.skip()
        self.assertEqual([round((s["end"] - s["start"]) / 60) for s in self.pm.cycle], [10, 5])

    def test_extend_and_shorten(self):
        self.pm.extend()
        self.assertEqual(self.pm.view().clock, "30:00")
        self.assertEqual(self.reported[-1], ("notice", "Work: +5 min", "information"))
        self.pm.shorten()
        self.pm.shorten()
        self.assertEqual(self.pm.view().clock, "20:00")
        self.assertEqual(self.pm.view().progress, (0, 1200))

    def test_shorten_ends_the_phase_with_five_minutes_left(self):
        self.pm.toggle()
        self.run_for(20 * 60)
        self.pm.shorten()
        self.assertEqual(self.pm.phase, "short")

    def test_add_and_remove_cycles(self):
        self.pm.add_cycle()
        self.assertEqual(self.pm.cycles, 3)
        self.pm.remove_cycle()
        self.pm.remove_cycle()
        self.assertEqual(self.pm.cycles, 1)
        self.pm.remove_cycle()  # never below the current session
        self.assertEqual(self.pm.cycles, 1)
        self.assertEqual(self.reported[-1][2], "warning")

    def test_interrupt_stops_and_hands_over_the_work(self):
        self.pm.toggle()
        self.run_for(600)
        segments = self.pm.interrupt("quit")
        self.assertEqual(self.hooks()[-1], ("end", "quit"))
        self.assertFalse(self.pm.running)
        self.assertEqual(len(segments), 1)
        self.assertEqual(self.pm.unrecorded(), (None, []))

    def test_interrupt_during_a_break_runs_no_hook(self):
        self.pm.toggle()
        self.pm.skip()
        count = len(self.hooks())
        self.pm.interrupt("reset")
        self.assertEqual(len(self.hooks()), count)

    def test_reset(self):
        self.pm.toggle()
        self.pm.skip()
        self.pm.add_cycle()
        self.pm.reset()
        self.assertTrue(self.pm.idle)
        self.assertEqual((self.pm.phase, self.pm.cycles, self.pm.done_pomodoros), ("work", 2, 0))

    def test_waybar_state(self):
        self.pm.toggle()
        self.run_for(60)
        data, key, tick = self.pm.waybar_state(self.clock.time())
        self.assertEqual((data["mode"], data["phase"], data["remaining"], data["total"]),
                         ("pomodoro", "work", 1440, 1500))
        self.assertEqual(data["ends_at"], self.clock.time() + 1440)
        self.assertEqual(key, ("work", True, 0, 1500))

    def test_keys(self):
        self.assertEqual(set(self.pm.actions), {"skip", "extend", "shorten", "add_cycle", "remove_cycle"})
        self.assertEqual(self.pm.hints(), [("n", "skip", "Next phase")])
        timer_keys, app_keys = self.pm.help_rows()
        self.assertEqual([k for k, _ in timer_keys], ["space", "n", "+", "-", ">", "<", "r"])
        self.assertEqual([k for k, _ in app_keys], ["p", "m"])
