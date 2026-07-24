"""Parses a pahe.ink content page into resolutions/episodes -> download entries.

Approach (see docs/research/site-structure.md for the full research this follows):

- pahe.ink is a plain server-rendered WordPress page; a normal HTTP GET is enough,
  no JS execution needed.
- The download section lives in one (or more) `.post-tabs-ver` / `.post-tabs`
  containers. The `<ul class="tabs-nav">` items and the `.pane` divs correspond
  1:1 *by position* (there is no id/data attribute linking them) - tab[i] is
  pane[i]. This is how the site's own jQuery binds them client-side, and it's
  the only way to recover "which pane is which resolution/episode label".
- Three layouts are handled (see docs/research/site-structure.md for the full
  research this follows):
    * "batch release": tabs = resolution (480p/720p/1080p/2160p), inner groups =
      "Per Episode" / "Batch".
    * "ongoing release": tabs = episode number, inner groups = resolution/
      quality variant.
    * "movie release": no tabs at all - there is no `.post-tabs-ver`/
      `.post-tabs` wrapper, just one or more bare `.box.download` elements
      directly in the post body, each containing several resolution/quality
      groups back-to-back (e.g. 480p, 720p x264, 720p x265, 1080p x264, ...
      all in the same box, `<br>`-separated). Handled by treating the whole
      page as a single unlabeled "tab" (`tab_label=""`) and reusing the same
      box-walking logic.
  All three are handled by the same code because it doesn't hardcode which
  axis means what - it just reports `tab_label` (from tabs-nav, or "" when
  there is no tab structure) and `group_label` (from the label text
  immediately preceding each run of provider buttons inside the box), and
  leaves interpretation to the caller/CLI.
- Group/resolution labels are not always wrapped in a `<b>`/`<strong>`/`<span>`
  tag - on movie pages they're bare text nodes (e.g. `1080p x265 DD+5.1 | 2.31
  GB` sitting directly in the box, no wrapping tag at all), sometimes with an
  inline `<a>` (non-button, e.g. a colored "HDR DV" tag or a "MediaInfo" link)
  in the middle of the label text. So label text is accumulated from *any*
  non-button, non-`<br>` inline content since the last flush (on `<br>` or
  right before a button run), not just from a fixed set of tag names.
- No provider's real destination host (mega.nz or otherwise) ever appears in
  the HTML - every provider button links to the same opaque
  `teknoasian.com/?ht=<token>` gate. The only reliable signal for "this is the
  MEGA button" is the anchor's *visible text* (`MG`, `MG 1`, ...), not the
  href or CSS class/color (color-to-provider mapping is not stable across
  pages - confirmed in research).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup, Tag

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 20  # seconds

# Matches MG, MG1, MG 1, MG 2, ... case-sensitively (per research: provider
# abbreviations are case-sensitive visible text, not a stable CSS signal).
MEGA_PATTERN = re.compile(r"^MG(?:\s*\d+)?$")


class ParseError(Exception):
    """Raised when a pahe.ink page can't be fetched or has no recognizable
    download-tabs structure at all (distinct from "parsed fine, just no MEGA
    entries")."""


@dataclass
class Entry:
    """One provider download button found on the page."""

    tab_label: str  # e.g. "480p" or "Episode 1" (from tabs-nav)
    group_label: str  # e.g. "480p x264 - Per Episode", "Batch", ...
    provider_text: str  # raw visible button text, e.g. "MG", "MG 1"
    gate_url: str  # the teknoasian.com/?ht=... URL (never a final host)

    @property
    def is_mega(self) -> bool:
        return bool(MEGA_PATTERN.match(self.provider_text.strip()))

    @property
    def label(self) -> str:
        """Human-friendly label for display, e.g. '720p — 720p x265 - Per Episode'
        or 'Episode 1 — 480p x264 | 150 MB'. Avoids repeating the tab label when
        the detail label already starts with it (common on batch/resolution-tab
        pages)."""
        if self.group_label.startswith(self.tab_label):
            return self.group_label
        return f"{self.tab_label} — {self.group_label}"


@dataclass
class ParsedPage:
    url: str
    entries: list[Entry] = field(default_factory=list)

    @property
    def mega_entries(self) -> list[Entry]:
        return [e for e in self.entries if e.is_mega]


def fetch_html(url: str) -> str:
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise ParseError(f"Failed to fetch {url}: {exc}") from exc
    if resp.status_code != 200:
        raise ParseError(f"Unexpected HTTP {resp.status_code} fetching {url}")
    return resp.text


def _direct_children_by_class(parent: Tag, tag_name: str, class_name: str) -> list[Tag]:
    return [
        child
        for child in parent.find_all(tag_name, recursive=False)
        if class_name in (child.get("class") or [])
    ]


def _extract_box_entries(box: Tag, tab_label: str) -> list[Entry]:
    """Walk a `.box.download` element's inner children as a flat stream,
    tracking labels and emitting one Entry per provider anchor found, per the
    state-machine plan in site-structure.md.

    A box carries up to two label "levels": a title, e.g. "480p x264" or
    "1080p x264 6CH" (batch pages), or an episode title like "Episode 1"
    (ongoing pages) - always the *first* label seen in the box - and zero or
    more subsequent group markers, e.g. "Per Episode"/"Batch" (batch pages),
    a fresh quality variant like "720p x264 | 450 MB" (ongoing pages), or a
    fresh resolution+quality line like "1080p x265 DD+5.1 | 2.31 GB" (movie
    pages, which pack every resolution into one box with no separate
    title/group nesting - each new label both replaces the "group" and, if
    it's the first one, acts as the box's title). Both are tracked so
    entries stay distinguishable (e.g. the two 720p boxes on a batch page -
    x264 vs x265 - would otherwise both just say "Per Episode").

    Label text is not confined to a fixed set of tag names: on movie pages a
    label is a bare text node, sometimes with an inline non-button `<a>`
    (e.g. a colored "HDR DV" marker or a "MediaInfo" link) spliced into the
    middle of it. So any non-button, non-`<br>` inline content is accumulated
    into a pending-label buffer and flushed (replacing "current group", and
    "title" if not yet set) at each `<br>` and again just before any button
    run, in case a label isn't `<br>`-terminated.

    Whether the box's first label is a genuine standalone "title" that should
    go on prefixing every later group (batch/ongoing pages: e.g. "480p x264"
    heading zero buttons of its own, followed by "Per Episode"/"Batch"
    sub-groups that each get their own buttons) or is itself just the first
    of several self-contained, unrelated groups (movie pages: e.g. "480p
    x264 | 450 MB" already has its own button row - there is no shared
    heading at all, so it must not bleed into "720p x264 | 950 MB" later in
    the same box) can't be told upfront. It's inferred after the fact: if the
    first label ever directly gets its own buttons (`current_group ==
    box_title` at emission time), it wasn't a pure header, so it stops being
    used as a prefix for whatever unrelated groups follow it.
    """
    inner = box.find("div", class_="box-inner-block") or box
    entries: list[Entry] = []
    box_title: str | None = None
    current_group: str | None = None
    title_is_pure_header = True
    pending_parts: list[str] = []

    def flush_pending() -> None:
        nonlocal box_title, current_group
        text = " ".join(part for part in pending_parts if part)
        text = re.sub(r"\s+", " ", text).strip()
        pending_parts.clear()
        if text:
            if box_title is None:
                box_title = text
            current_group = text

    for child in inner.children:
        name = getattr(child, "name", None)
        if name == "a":
            classes = child.get("class") or []
            if not any(c.startswith("shortc-button") for c in classes):
                # A non-button anchor (e.g. a colored "HDR DV" marker, a
                # "MediaInfo" link) is part of the surrounding label text,
                # not spacing - fold its text into the pending label.
                text = child.get_text(strip=True)
                if text:
                    pending_parts.append(text)
                continue
            flush_pending()
            provider_text = child.get_text(strip=True)
            href = child.get("href", "").strip()
            if not provider_text or not href:
                continue
            if current_group is None:
                detail_label = "(unlabeled)"
            elif box_title is None or current_group == box_title:
                detail_label = current_group
                if box_title is not None:
                    # The "title" just got its own buttons directly, so it
                    # was never a pure header - don't let it keep prefixing
                    # whatever unrelated groups come after it in this box.
                    title_is_pure_header = False
            elif title_is_pure_header:
                detail_label = f"{box_title} - {current_group}"
            else:
                detail_label = current_group
            entries.append(
                Entry(
                    tab_label=tab_label,
                    group_label=detail_label,
                    provider_text=provider_text,
                    gate_url=href,
                )
            )
        elif name == "br":
            flush_pending()
        elif name is None:
            # NavigableString: bare label text (movie pages put resolution/
            # quality lines directly here, with no wrapping tag at all).
            text = str(child).strip()
            if text:
                pending_parts.append(text)
        else:
            # <b>/<strong>/<span>/<em>/... label-bearing tags, and <i> icon
            # tags (empty text, contribute nothing).
            text = child.get_text(strip=True)
            if text:
                pending_parts.append(text)

    return entries


def parse_page(url: str, html: str | None = None) -> ParsedPage:
    """Fetch (unless `html` is supplied, e.g. for tests) and parse a pahe.ink
    page into a flat list of provider Entry objects across all resolution/
    episode tabs (or, on a movie page with no tab structure at all, across
    its flat `.box.download` sections - see module docstring). Raises
    ParseError if no recognizable download structure is found at all;
    returns a ParsedPage with an empty entry list (not an error) if a
    structure is found but simply carries no MEGA buttons.
    """
    if html is None:
        html = fetch_html(url)

    soup = BeautifulSoup(html, "html.parser")
    containers = soup.select("div.post-tabs-ver, div.post-tabs")

    if not containers:
        # Movie pages (e.g. a single-quality-tier release with no episodes)
        # carry no `.post-tabs-ver`/`.post-tabs` wrapper at all - just one or
        # more bare `.box.download` elements directly in the post body, each
        # bundling every resolution/quality tier back-to-back. Scope the
        # search to the main post-content wrapper (`.entry`) when present, to
        # avoid picking up an unrelated same-shaped widget elsewhere on the
        # page; fall back to the whole document if `.entry` isn't found.
        scope = soup.find("div", class_="entry") or soup
        boxes = [
            b
            for b in scope.find_all("div")
            if {"box", "download"} <= set(b.get("class") or [])
        ]
        if not boxes:
            raise ParseError(
                "No '.post-tabs-ver' / '.post-tabs' download section, and no "
                "flat '.box.download' section either - is this really a "
                "pahe.ink release page?"
            )
        entries = []
        for box in boxes:
            entries.extend(_extract_box_entries(box, tab_label=""))
        return ParsedPage(url=url, entries=entries)

    entries: list[Entry] = []
    for container in containers:
        tabs_nav = container.find("ul", class_="tabs-nav")
        tab_labels = (
            [li.get_text(strip=True) for li in tabs_nav.find_all("li", recursive=False)]
            if tabs_nav
            else []
        )
        panes = _direct_children_by_class(container, "div", "pane")

        if not tab_labels or not panes:
            continue

        # Positional 1:1 correspondence per site-structure.md - there is no
        # other linkage available. If counts mismatch, still zip as far as
        # possible rather than dropping the whole container.
        for tab_label, pane in zip(tab_labels, panes):
            boxes = [
                b
                for b in pane.find_all("div", recursive=False)
                if {"box", "download"} <= set(b.get("class") or [])
            ]
            for box in boxes:
                entries.extend(_extract_box_entries(box, tab_label))

    return ParsedPage(url=url, entries=entries)
