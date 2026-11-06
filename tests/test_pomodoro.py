"""Behaviour of the pomodoro mode, as seen from the outside."""
import os
import signal

from support import PomoTestCase


class PomodoroDisplayTest(PomoTestCase):
    async def test_initial_screen(self):
        async with self.run_app():
            self.assertEqual(self.clock_text(), "25:00")
            self.assertEqual(self.phase_text(), "🍅  Work (paused)")
            self.assertEqual(self.info_text(), "Profile: classic  ·  Pomodoros: 0  ·  cycle 1/4")
            self.assertEqual(self.hints_text(), "space Start   n Next phase   r Reset   ? Help   q Quit")
            self.assertEqual(self.hook_events(), [])

    async def test_space_label_follows_the_state(self):
        async with self.run_app():
            await self.press("space")
            self.assertTrue(self.hints_text().startswith("space Pause"))
            await self.press("space")
            self.assertTrue(self.hints_text().startswith("space Resume"))

    async def test_hints_wrap_only_when_too_narrow(self):
        # the English line is 54 characters long, plus one of padding on each side
        async with self.run_app(size=(56, 30)):
            self.assertNotIn(" / ", self.hints_text())
            await self.pilot.resize_terminal(55, 30)
            await self.pilot.pause(0.3)
            self.assertEqual(self.hints_text(), "space Start   n Next phase   r Reset   ? Help / q Quit")
            await self.pilot.resize_terminal(80, 30)
            await self.pilot.pause(0.3)
            self.assertNotIn(" / ", self.hints_text())


class PomodoroTimerTest(PomoTestCase):
    async def test_countdown_and_hooks(self):
        async with self.run_app():
            await self.press("space")
            self.assertEqual(self.hook_events(), [("start", "start")])
            await self.advance(60)
            self.assertEqual(self.clock_text(), "24:00")
            self.assertEqual(self.phase_text(), "🍅  Work")
            await self.press("space")
            await self.press("space")
            self.assertEqual(self.hook_events(), [("start", "start"), ("end", "pause"), ("start", "resume")])

    async def test_paused_timer_does_not_count(self):
        async with self.run_app():
            await self.advance(600)
            self.assertEqual(self.clock_text(), "25:00")

    async def test_work_ends_into_short_break(self):
        async with self.run_app():
            await self.press("space")
            await self.advance(25 * 60)
            self.assertEqual(self.phase_text(), "☕  Short break")
            self.assertEqual(self.clock_text(), "05:00")
            self.assertEqual(self.info_text(), "Profile: classic  ·  Pomodoros: 1  ·  cycle 2/4")
            self.assertEqual(self.hook_events(), [("start", "start"), ("end", "end")])
            self.assertEqual(self.desktop_notifications, ["☕ Short break"])
            await self.advance(5 * 60)
            self.assertEqual(self.phase_text(), "🍅  Work")
            self.assertEqual(self.desktop_notifications[-1], "🍅 Back to work!")
            self.assertEqual(self.hook_events()[-1], ("start", "start"))

    async def test_next_phase_key(self):
        async with self.run_app():
            await self.press("space", "n")
            self.assertEqual(self.phase_text(), "☕  Short break")
            await self.press("n")
            self.assertEqual(self.phase_text(), "🍅  Work")
            self.assertEqual(self.info_text(), "Profile: classic  ·  Pomodoros: 1  ·  cycle 2/4")

    async def test_long_break_after_the_cycle(self):
        async with self.run_app(cycles=2):
            await self.press("space", "n", "n", "n")
            self.assertEqual(self.phase_text(), "🌴  Long break")
            self.assertEqual(self.clock_text(), "15:00")
            self.assertEqual(self.info_text(), "Profile: classic  ·  Pomodoros: 2  ·  cycle 1/2")

    async def test_extend_and_shorten(self):
        async with self.run_app():
            await self.press("plus")
            self.assertEqual(self.clock_text(), "30:00")
            self.assertEqual(self.notifications()[-1], "Work: +5 min")
            await self.press("minus", "subtract")
            self.assertEqual(self.clock_text(), "20:00")
            self.assertEqual(self.notifications()[-1], "Work: -5 min")

    async def test_shorten_ends_the_phase_when_little_time_is_left(self):
        async with self.run_app():
            await self.press("space")
            await self.advance(20 * 60 - 1)  # 5:01 left: shortened, the phase goes on
            await self.press("minus")
            self.assertEqual(self.clock_text(), "00:01")
            await self.press("plus")
            await self.advance(1)            # exactly 5:00 left: - ends the phase
            await self.press("minus")
            self.assertEqual(self.phase_text(), "☕  Short break")

    async def test_extend_is_reflected_in_waybar(self):
        async with self.run_app():
            await self.press("space", "plus")
            await self.advance(15 * 60)
            state = self.waybar_state()
            self.assertEqual((state["mode"], state["phase"], state["remaining"], state["total"]),
                             ("pomodoro", "work", 15 * 60, 30 * 60))

    async def test_add_and_remove_cycles(self):
        async with self.run_app():
            await self.press("greater_than_sign")
            self.assertIn("cycle 1/5", self.info_text())
            self.assertEqual(self.notifications()[-1], "Cycle: 5 work session(s) before the long break")
            await self.press("less_than_sign", "less_than_sign")
            self.assertIn("cycle 1/3", self.info_text())

    async def test_cannot_remove_below_the_current_session(self):
        async with self.run_app():
            await self.press("space", "n", "n", "n", "n")  # 2 sessions done, 3rd running
            await self.press("less_than_sign")
            self.assertIn("cycle 3/3", self.info_text())
            await self.press("less_than_sign")
            self.assertIn("cycle 3/3", self.info_text())
            self.assertEqual(self.notifications()[-1], "Cannot remove: this cycle needs at least 3 work session(s)")
            await self.press("n")
            self.assertEqual(self.phase_text(), "🌴  Long break")

    async def test_reset_is_a_full_reset(self):
        async with self.run_app():
            await self.press("space", "n", "n", "greater_than_sign")
            await self.press("r")
            self.assertEqual(self.clock_text(), "25:00")
            self.assertEqual(self.phase_text(), "🍅  Work (paused)")
            self.assertEqual(self.info_text(), "Profile: classic  ·  Pomodoros: 0  ·  cycle 1/4")
            self.assertEqual(self.hook_events()[-1], ("end", "reset"))
            self.assertTrue(self.hints_text().startswith("space Start"))

    async def test_waybar_signals(self):
        async with self.run_app():
            os.kill(os.getpid(), signal.SIGUSR1)  # waybar click: pause / resume
            await self.pilot.pause(0.3)
            self.assertEqual(self.phase_text(), "🍅  Work")
            os.kill(os.getpid(), signal.SIGUSR2)  # waybar right click: next phase
            await self.pilot.pause(0.3)
            self.assertEqual(self.phase_text(), "☕  Short break")


class HooksToggleTest(PomoTestCase):
    async def test_c_toggles_the_hooks(self):
        async with self.run_app():
            await self.press("c")
            self.assertTrue(self.info_text().endswith("·  hooks off"))
            self.assertEqual(self.notifications()[-1], "Hooks disabled")
            await self.press("space", "n", "n")
            self.assertEqual(self.hook_events(), [])
            await self.press("c", "n")
            self.assertEqual(self.hook_events(), [("end", "end")])

    async def test_no_hooks_option_starts_disabled(self):
        async with self.run_app(no_hooks=True):
            self.assertTrue(self.info_text().endswith("·  hooks off"))
            await self.press("space")
            self.assertEqual(self.hook_events(), [])


class HelpAndMenusTest(PomoTestCase):
    async def test_help_keys_and_content(self):
        async with self.run_app():
            for key in ("question_mark", "h", "f1"):
                await self.press(key)
                self.assertEqual(self.screen_name(), "HelpScreen")
                await self.press("escape")
                self.assertEqual(self.screen_name(), "Screen")
            await self.press("question_mark")
            keys = str(self.app.screen.query(".help-keys").first().render())
            for row in ("+        add 5 min", "<        remove a work session", ">        add a work session"):
                self.assertIn(row, keys)
            await self.press("q")  # closes the help, does not quit
            self.assertEqual(self.screen_name(), "Screen")
            self.assertTrue(self.app.is_running)

    async def test_keys_are_inert_while_the_help_is_open(self):
        async with self.run_app():
            await self.press("question_mark", "space")
            await self.press("escape")
            self.assertEqual(self.phase_text(), "🍅  Work (paused)")

    async def test_profile_menu_loads_a_profile(self):
        config = self.pomo.CONFIG_FILE
        config.parent.mkdir(parents=True)
        config.write_text('default_profile = "classic"\n'
                          "[profiles.classic]\nwork = 25\nshort_break = 5\ncycles = 4\n"
                          "[profiles.deep]\nwork = 50\nshort_break = 10\ncycles = 3\n")
        async with self.run_app():
            await self.press("p")
            self.assertEqual(self.screen_name(), "ProfileMenu")
            await self.press("j", "enter")
            self.assertEqual(self.clock_text(), "50:00")
            self.assertEqual(self.info_text(), "Profile: deep  ·  Pomodoros: 0  ·  cycle 1/3")
            self.assertEqual(self.notifications()[-1], "Profile 'deep' loaded")


class QuitTest(PomoTestCase):
    async def test_quit_during_work_runs_the_end_hook(self):
        async with self.run_app():
            await self.press("space")
            await self.advance(60)
            await self.press("q")
            self.assertFalse(self.app.is_running)
            self.assertEqual(self.hook_events()[-1], ("end", "quit"))
