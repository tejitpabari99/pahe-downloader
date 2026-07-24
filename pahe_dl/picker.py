"""Interactive CLI picker over parsed MEGA download entries.

Per docs/planning/cli-ux-notes.md: use `questionary.select` for arrow-key
navigation with `use_shortcuts=True` for single-digit (1-9) numeric jump,
which comfortably covers the expected list sizes here (a handful of
resolutions/episodes x a handful of MEGA entries per page).
"""
from __future__ import annotations

import questionary

from pahe_dl.parser import Entry


class NoSelectionError(Exception):
    """Raised when the user cancels the picker (Ctrl-C/Esc) instead of
    picking an entry."""


def pick_entry(entries: list[Entry]) -> Entry:
    """Show an interactive picker over `entries` and return the chosen one.

    Raises ValueError if `entries` is empty (caller's responsibility to
    check first and show a friendlier message - see cli.py) and
    NoSelectionError if the user cancels out of the prompt.
    """
    if not entries:
        raise ValueError("pick_entry() called with an empty entry list")

    choices = [
        questionary.Choice(title=entry.label, value=entry) for entry in entries
    ]

    answer = questionary.select(
        "Select a MEGA download entry:",
        choices=choices,
        use_shortcuts=True,
        use_arrow_keys=True,
    ).ask()

    if answer is None:
        raise NoSelectionError("No entry selected (cancelled).")

    return answer
