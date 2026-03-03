"""CheckboxTreeview with tri-state cascade logic."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class CheckboxTreeview(ttk.Treeview):
    """A Treeview with tri-state checkboxes using tag-based rendering."""

    # Unicode checkbox characters
    CHECKED = "\u2611"
    UNCHECKED = "\u2610"
    TRISTATE = "\u2612"

    def __init__(self, master=None, **kwargs):
        kwargs.setdefault("show", "tree")
        super().__init__(master, **kwargs)

        self.tag_configure("checked", foreground="black")
        self.tag_configure("unchecked", foreground="gray")
        self.tag_configure("tristate", foreground="black")

        self.bind("<Button-1>", self._on_click)

        self._check_states: dict[str, str] = {}  # item_id -> "checked"|"unchecked"|"tristate"

    def insert_item(self, parent="", index="end", text="", checked=True, **kwargs):
        """Insert an item with a checkbox prefix."""
        state = "checked" if checked else "unchecked"
        prefix = self.CHECKED if checked else self.UNCHECKED
        tags = kwargs.pop("tags", ())
        if isinstance(tags, str):
            tags = (tags,)
        tags = (state,) + tuple(tags)
        item_id = self.insert(parent, index, text=f"{prefix} {text}", tags=tags, **kwargs)
        self._check_states[item_id] = state
        return item_id

    def _on_click(self, event):
        """Toggle checkbox on click (only if clicking near the text start)."""
        region = self.identify("region", event.x, event.y)
        if region != "tree":
            return

        item = self.identify_row(event.y)
        if not item:
            return

        # Toggle the state
        current = self._check_states.get(item, "unchecked")
        new_state = "unchecked" if current in ("checked", "tristate") else "checked"

        self._set_state(item, new_state)
        self._cascade_down(item, new_state)
        self._cascade_up(item)

        self.event_generate("<<CheckChanged>>")

    def _set_state(self, item: str, state: str):
        self._check_states[item] = state
        prefix_map = {
            "checked": self.CHECKED,
            "unchecked": self.UNCHECKED,
            "tristate": self.TRISTATE,
        }
        text = self.item(item, "text")
        # Strip existing prefix (first 2 chars: symbol + space)
        if text and text[0] in (self.CHECKED, self.UNCHECKED, self.TRISTATE):
            text = text[2:]
        self.item(item, text=f"{prefix_map[state]} {text}")

        # Update tags
        old_tags = set(self.item(item, "tags"))
        old_tags -= {"checked", "unchecked", "tristate"}
        old_tags.add(state)
        self.item(item, tags=tuple(old_tags))

    def _cascade_down(self, item: str, state: str):
        """Set all descendants to the same state."""
        for child in self.get_children(item):
            self._set_state(child, state)
            self._cascade_down(child, state)

    def _cascade_up(self, item: str):
        """Update parent based on children states."""
        parent = self.parent(item)
        if not parent:
            return

        children = self.get_children(parent)
        states = {self._check_states.get(c, "unchecked") for c in children}

        if states == {"checked"}:
            self._set_state(parent, "checked")
        elif states == {"unchecked"}:
            self._set_state(parent, "unchecked")
        else:
            self._set_state(parent, "tristate")

        self._cascade_up(parent)

    def is_checked(self, item: str) -> bool:
        return self._check_states.get(item) == "checked"

    def get_state(self, item: str) -> str:
        return self._check_states.get(item, "unchecked")

    def set_checked(self, item: str, checked: bool):
        """Programmatically set an item's check state without cascade."""
        self._set_state(item, "checked" if checked else "unchecked")

    def get_text(self, item: str) -> str:
        """Get the item text without the checkbox prefix."""
        text = self.item(item, "text")
        if text and text[0] in (self.CHECKED, self.UNCHECKED, self.TRISTATE):
            return text[2:]
        return text
