"""python3 -m pomo (from the repository root): same as bin/pomo."""
from pathlib import Path

from .main import main

main(str(Path(__file__).resolve().parent.parent / "bin"))
