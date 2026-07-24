"""CLI entry point: wires the parser, picker, and resolver together.

Usage:
    pahe-dl <pahe.ink URL>
    python -m pahe_dl <pahe.ink URL>

If no URL is given as an argument, the user is prompted for one.
"""
from __future__ import annotations

import argparse
import sys

from pahe_dl.parser import ParseError, parse_page
from pahe_dl.picker import NoSelectionError, pick_entry
from pahe_dl.resolver import (
    CloudflareChallengeTimeout,
    GateResolutionError,
    resolve_gate_url,
)


def _prompt_for_url() -> str:
    try:
        url = input("Enter a pahe.ink page URL: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nNo URL provided, exiting.", file=sys.stderr)
        sys.exit(1)
    if not url:
        print("No URL provided, exiting.", file=sys.stderr)
        sys.exit(1)
    return url


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pahe-dl",
        description=(
            "Discover MEGA download entries on a pahe.ink page, let you pick one, "
            "and resolve it to a final mega.nz URL. Never downloads the actual file."
        ),
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="A pahe.ink release page URL (prompted for if omitted).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    url = args.url or _prompt_for_url()

    print(f"Fetching {url} ...")
    try:
        parsed = parse_page(url)
    except ParseError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    mega_entries = parsed.mega_entries
    if not mega_entries:
        print(
            "No MEGA ('MG') download entries were found on this page. "
            "Other providers are not supported yet.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Found {len(mega_entries)} MEGA entr{'y' if len(mega_entries) == 1 else 'ies'}.")

    try:
        entry = pick_entry(mega_entries)
    except NoSelectionError:
        print("No entry selected, exiting.", file=sys.stderr)
        sys.exit(1)

    print(f"Resolving: {entry.label} ...")

    def on_status(msg: str) -> None:
        print(f"  ... {msg}")

    try:
        mega_url = resolve_gate_url(entry.gate_url, referer=url, on_status=on_status)
    except CloudflareChallengeTimeout as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except GateResolutionError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    # Final output: just the URL, so it's easy to copy/pipe.
    print(mega_url)


if __name__ == "__main__":
    main()
