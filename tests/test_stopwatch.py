"""Behaviour of the stopwatch mode and of the switch between modes."""
import os
import signal

from support import PomoTestCase


class StopwatchTest(PomoTestCase):
    async def test_initial_screen(self):
        async with self.run_app(stopwatch=True):
            self.assertEqual(self.phase_text(), "⏱  Stopwatch (paused)")
            self.assertEqual(self.clock_text(), "00:00.0")
            self.assertEqual(self.info_text(), "Laps: 0")
            self.assertEqual(self.hints_text(), "space Start   l Lap   r Reset   ? Help   q Quit")

    async def test_counts_and_records_laps(self):
        async with self.run_app(stopwatch=True):
            await self.press("l")  # ignored while stopped
            self.assertEqual(self.info_text(), "Laps: 0")
            await self.press("space")
            await self.advance(2)
            await self.press("l")
            await self.advance(1)
            await self.press("l")
            await self.advance(3)
            await self.press("l")
            self.assertEqual(self.clock_text(), "00:06.0")
            self.assertEqual(self.info_text(), "Laps: 3")
            # newest first; fastest lap in green, slowest in red
            self.assertEqual(self.lap_rows(), [("3", "00:03.0", "red", "00:06.0"),
                                               ("2", "00:01.0", "green", "00:03.0"),
                                               ("1", "00:02.0", "", "00:02.0")])

    async def test_reset(self):
        async with self.run_app(stopwatch=True):
            await self.press("space")
            await self.advance(5)
            await self.press("l", "r")
            self.assertEqual(self.clock_text(), "00:00.0")
            self.assertEqual(self.info_text(), "Laps: 0")
            self.assertEqual(self.phase_text(), "⏱  Stopwatch (paused)")

    async def test_pomodoro_keys_do_nothing(self):
        async with self.run_app(stopwatch=True):
            await self.press("plus", "minus", "greater_than_sign", "less_than_sign", "n", "p", "c")
            self.assertEqual(self.screen_name(), "Screen")
            self.assertEqual(self.clock_text(), "00:00.0")
            self.assertEqual(self.notifications(), [])

    async def test_waybar(self):
        async with self.run_app(stopwatch=True):
            await self.press("space")
            await self.advance(4)
            os.kill(os.getpid(), signal.SIGUSR2)  # waybar right click: lap
            await self.pilot.pause(0.3)
            state = self.waybar_state()
            self.assertEqual((state["mode"], state["running"], state["elapsed"], state["laps"]),
                             ("stopwatch", True, 4, 1))

    async def test_help_lists_the_stopwatch_keys(self):
        async with self.run_app(stopwatch=True):
            await self.press("question_mark")
            keys = str(self.app.screen.query(".help-keys").first().render())
            self.assertIn("l        record a lap", keys)
            self.assertNotIn("+", keys)


class ModeSwitchTest(PomoTestCase):
    async def test_switch_to_stopwatch_and_back(self):
        async with self.run_app():
            await self.press("space", "n", "m")  # during a break: nothing to record
            self.assertEqual(self.phase_text(), "⏱  Stopwatch (paused)")
            self.assertEqual(self.notifications()[-1], "Stopwatch mode")
            await self.press("space")
            await self.advance(3)
            await self.press("m")
            self.assertEqual(self.phase_text(), "🍅  Work (paused)")
            self.assertEqual(self.clock_text(), "25:00")
            self.assertEqual(self.info_text(), "Profile: classic  ·  Pomodoros: 0  ·  cycle 1/4")
            self.assertEqual(self.notifications()[-1], "Pomodoro mode")

    async def test_switch_during_work_runs_the_end_hook(self):
        async with self.run_app():
            await self.press("space")
            await self.advance(60)
            await self.press("m")
            self.assertEqual(self.hook_events(), [("start", "start"), ("end", "switch")])
            self.assertEqual(self.phase_text(), "⏱  Stopwatch (paused)")
