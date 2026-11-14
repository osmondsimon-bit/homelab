"""Run the private Telegram relay from the installed source tree."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from codex_messaging.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
