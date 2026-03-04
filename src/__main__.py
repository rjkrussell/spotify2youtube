"""Allow running as `python -m src`."""

import logging
import os

# Enable matcher debug logging when running against the mock
if os.environ.get("YOUTUBE_MOCK") == "1":
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")

from src.app import App

app = App()
app.mainloop()
