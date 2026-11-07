"""The command line entry point: what happens around the app (start, exit, crash)."""
import json

from support import ModeTestCase


class RunTest(ModeTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.pomo.system.refresh_waybar = lambda: None
        self.pomo.system.run_hook = lambda cmd, env: None
        self.pomo.system.notify = lambda *a, **k: None

    def run_app(self, fake_run, *argv: str) -> None:
        """main.run() with the Textual app replaced by `fake_run(app)`."""
        self.pomo.app.Pomo.run = fake_run
        args = self.pomo.main.build_parser().parse_args(list(argv))
        self.pomo.main.run(args, {})

    def snapshots(self) -> list:
        return sorted(self.pomo.DATA_DIR.glob("current-*.json")) if self.pomo.DATA_DIR.exists() else []

    def test_normal_exit_cleans_up(self):
        self.pomo.STATE_FILE.write_text("{}")
        self.run_app(lambda app: None)
        self.assertFalse(self.pomo.STATE_FILE.exists())
        self.assertEqual(self.snapshots(), [])

    def test_crash_during_work_keeps_the_work_for_the_next_launch(self):
        def crash(app):
            app.timer.toggle()  # work starts...
            raise RuntimeError("boom")  # ...and the app dies

        with self.assertRaises(RuntimeError):
            self.run_app(crash)
        [snapshot] = self.snapshots()
        self.assertIsNotNone(json.loads(snapshot.read_text())["segment"])
        self.assertFalse(self.pomo.STATE_FILE.exists())

    def test_cli_options_override_the_profile(self):
        seen = {}
        self.run_app(lambda app: seen.update(name=app.timer.name, view=app.timer.view()),
                     "-w", "40", "-c", "2")
        self.assertEqual(seen["name"], "pomodoro")
        self.assertEqual(seen["view"].clock, "40:00")
        self.assertIn("cycle 1/2", seen["view"].info)

    def test_stopwatch_option(self):
        seen = {}
        self.run_app(lambda app: seen.update(name=app.timer.name), "--stopwatch")
        self.assertEqual(seen["name"], "stopwatch")
