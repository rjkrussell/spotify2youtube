#!/usr/bin/env python3
"""Entry point for spotify2youtube.py."""

import sys
import os

# Add project root to path so 'src' package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app import App

if __name__ == "__main__":
    app = App()
    app.mainloop()
