# pahe.ink Page Structure Research (Part 1)

Status: verified against live pages, fetched read-only via `curl` (browser User-Agent) and
`WebFetch`. No JavaScript was executed; no forms submitted; no ads/tracking links opened.

## Pages fetched

| URL | Purpose | HTTP status |
|---|---|---|
| `https://pahe.ink/game-of-thrones-season-8-complete-bluray-480p-720p-1080p/` | User's example — a "complete season batch" release | 200 |
| `https://pahe.ink/category/ongoing/` | Find an example of a weekly/episodic release | 200 |
| `https://pahe.ink/parish-season-1/` | Example of an "ongoing" episode-by-episode release | 200 |
| `https://pahe.ink/robots.txt` | Crawl policy check | 200 |
| `https://pahe.ink/obsession-2025-bluray-480p-720p-1080p-2160p/` | Bug report follow-up — a **movie** release (resolves the "movie pages" open question below) | 200 |

`robots.txt` only disallows `/wp-admin/` (and explicitly allows `admin-ajax.php`). No
`Crawl-delay`. Content pages are not disallowed. The site is a plain WordPress install
(theme "Sahifa"/"tie", WordPress 6.7, LiteSpeed cache) — no SPA/client-side rendering. All
content discussed below is present in the initial server-rendered HTML; a plain HTTP GET
(requests/httpx) is sufficient for Part 1, **no headless browser is needed to read the
download-link listings**.

## Two distinct layout patterns (important)

pahe.ink does not use one fixed template for the download section — it's a hand-authored
WordPress shortcode block (`.post-tabs-ver`) and different uploaders group things
differently. Two patterns were observed and a real parser must handle both (and likely more,
see Open Questions):

### Pattern A — "batch release" (tabs = resolution)

Example: Game of Thrones S8 complete pack.

```
<div class="post-tabs-ver">
  <ul class="tabs-nav"><li>480p</li><li>720p</li><li>1080p</li></ul>
  <div class="pane">  <!-- 480p -->
    <div class="box download"><div class="box-inner-block">
      <span style="color:#00ccff;">480p x264</span><br/>
      <b>Per Episode</b> ~200-300 MB<br/>
      <a href="https://teknoasian.com/?ht=...." target="_blank" class="shortc-button small red ">MG</a>
      <b>Batch</b> 1.62 GB<br/>
      <a href="...teknoasian.com/?ht=...." class="shortc-button small white ">PD</a>
      <a href="..." class="shortc-button small green ">VF</a>
      <a href="..." class="shortc-button small purple ">GD</a>
      <a href="..." class="shortc-button small orange ">1F</a>
    </div></div>
  </div>
  <div class="pane"> <!-- 720p: TWO boxes, x264 and x265 -->
    <div class="box download">...720p x264... MG / PD / VF / GD / 1F ...</div>
    <div class="box download">...720p x265... MG / PD / VF / GD / 1F ...</div>
  </div>
  <div class="pane"> <!-- 1080p: one box, split batch (2 parts) -->
    <div class="box download">
      <b>Per Episode</b> ~1 GB<br/>
      <a class="... red ">MG</a>
      <b>Batch</b> 3.99 GB + 2.98 GB<br/>
      <a class="... white ">PD1</a><a class="... white ">PD2</a>
      <a class="... green ">VF 1</a><a class="... green ">VF 2</a>
      <a class="... orange ">1F 1</a><a class="... orange ">1F 2</a>
      <a class="... purple ">GD 1</a><a class="... purple ">GD 2</a>
    </div>
  </div>
</div>
```

Key finding: for this batch release, MEGA (`MG`) has only **one link per resolution**,
attached to the "Per Episode" label, while the other hosts have separate multi-part
"Batch" links. For the reader/user this MG link is most likely a single MEGA folder
containing all episodes, not literally one link per episode — see Open Questions.

### Pattern B — "ongoing/weekly release" (tabs = episode)

Example: `parish-season-1` (currently "Episode 1/2/3 Added").

```
<div class="post-tabs-ver">
  <ul class="tabs-nav"><li>Episode 1</li><li>Episode 2</li><li>Episode 3</li></ul>
  <div class="pane"> <!-- Episode 1 -->
    <div class="box download"><div class="box-inner-block">
      <span style="color:#00ccff;"><b>Episode 1</b></span><br/>
      <strong>480p x264</strong> | 150 MB<br/>
      <a href="...teknoasian.com/?ht=...." class="shortc-button small white ">PD</a>
      <a href="..." target="_blank" class="shortc-button small red ">MG</a>
      <a href="..." target="_blank" class="shortc-button small green ">SD</a>
      <a href="..." target="_blank" class="shortc-button small purple ">GD</a>
      <strong>720p x264</strong> | 450 MB<br/>
      ... PD / MG / SD / GD again ...
      <strong>1080p x264 6CH</strong> | 950 MB<br/>
      ... PD / MG / SD / GD ...
      <strong>1080p x265 6CH</strong> | 638 MB<br/>
      ... PD / MG / SD / GD ...
    </div></div>
  </div>
  <div class="pane"> <!-- Episode 2 --> ... same shape ... </div>
  ...
```

Here the tab axis is **episode**, and *within* each episode tab, resolution/quality
variants are the inner grouping — the inverse nesting of Pattern A. Also note the host set
differs: `SD` appears here instead of `VF`, and `1F` is absent — the provider set is not
fixed either.

### Pattern C — "movie release" (no tabs at all)

Example: `obsession-2025-bluray-480p-720p-1080p-2160p` (a bug report — the parser raised
`ParseError: No '.post-tabs-ver' / '.post-tabs' download section found` against this URL,
prompting this investigation). This resolves the "movie pages" open question flagged at the
end of Part 1: **confirmed movie pages are a third, structurally distinct layout**, not a
degenerate case of Pattern A/B.

```
<div class="entry">
  ...
  <p>
    <div class="box download"><div class="box-inner-block">
      <i class="fa tie-shortcode-boxicon"></i>
      480p x264 | 450 MB<br/>
      <a href="https://teknoasian.com/?ht=...." class="shortc-button small orange">1F</a>
      <a ... class="shortc-button small purple">GD</a>
      <a ... class="shortc-button small red">MG</a>
      <a ... class="shortc-button small green">VF</a>
      <a ... class="shortc-button small blue">TB</a>
      <br/><br/>
      720p x264 | 950 MB<br/>
      ... 1F / GD / MG / VF / TB again ...
      <br/><br/>
      720p x265 10Bit | 635 MB<br/>
      ... 1F / GD / MG / VF / TB ...
      <br/><br/>
      1080p x264 DD+5.1 | 3.09 GB<br/>
      ... 1F / GD / MG / VF / TB ...
      <br/><br/>
      1080p x265 10Bit DD+5.1 | 2.50 GB<br/>
      ... 1F / GD / MG / VF / TB ...
    </div></div>
  </p>
  <p>
    <div class="box download"><div class="box-inner-block">
      <i class="fa tie-shortcode-boxicon"></i>
      <em><strong>Source:</strong>2160p.UHD.BluRay.Remux.HDR.DV.HEVC.TrueHD.Atmos.7.1-CiNEPHiLES</em>
      <br/><br/>
      1080p x265 <a style="color:#d4af37;">HDR DV</a> DD+5.1 | 2.31 GB<br/>
      ... 1F / GD / MG / VF / TB ...
      <br/><br/>
      2160p x265 <a style="color:#d4af37;">HDR DV</a> DD+5.1 Atmos | 7.10 GB |
      <a href="https://pastebin.com/raw/..." style="color:#00e803;">MediaInfo</a><br/>
      ... 1F / GD / MG / VF / TB ...
    </div></div>
  </p>
  ...
</div>
```

Key findings, all confirmed against the live page:

- **There is no `.post-tabs-ver`/`.post-tabs` wrapper at all** — no `ul.tabs-nav`, no
  `.pane`. The `.box.download` elements sit directly in the post body (as siblings inside
  plain `<p>` tags under `.entry`), not nested inside any tab/pane structure. This is what
  caused the reported crash: the parser treated "no tabs container found" as "not a valid
  pahe.ink page" and raised unconditionally, when really it just meant "this page has no
  episode/resolution tab axis at all."
- **A single box bundles every resolution/quality tier back-to-back**, `<br>`-separated,
  rather than one box (or tab) per resolution. The first box above alone carries 480p,
  720p x264, 720p x265, 1080p x264, and 1080p x265 — five tiers in one box, zero tabs.
- **Resolution/quality labels are bare text nodes**, not wrapped in any `<b>`/`<strong>`/
  `<span>` tag the way Patterns A and B always wrap theirs (e.g. `480p x264 | 450 MB` sits
  directly in `box-inner-block` with no enclosing tag at all). A parser that only watches
  for specific label *tag names* (as the original implementation did) sees no label at all
  here and would misattribute every button to an "(unlabeled)" bucket even after the
  tabs/panes issue above is fixed.
- A label can also have a **non-button `<a>` spliced into the middle of it** — e.g. a
  `<a style="color:#d4af37;">HDR DV</a>` marker, or a `<a>MediaInfo</a>` link to an external
  pastebin — that carries meaningful label text (not spacing) but must not be confused with
  a provider button.
- The **2160p resolution tier itself needed no special handling** once the above two
  structural issues were fixed — there is no resolution allow-list anywhere in the parser;
  any resolution string flows through as opaque label text. The `2160p` in the bug report
  URL was a red herring as far as root cause goes — the real breakage was 100% structural
  (missing tabs, untagged labels), not a "we've never seen 2160p" issue.
- The second box is a genuine two-level structure: an overarching `Source: ...` line
  (release-group/media-info metadata) followed by two *actual* resolution groups (1080p
  HDR remux, 2160p HDR remux) that each get their own button row. This is structurally the
  *same shape* as Pattern A's "title, then N labeled sub-groups" nesting — just with a
  metadata string as the title instead of a resolution. The parser's box-title logic
  originally assumed the first label in a box is always this kind of pure, buttonless
  header; Pattern C's *first* box violates that assumption (its first label, `480p x264 |
  450 MB`, already owns its own button row) and needed a small refinement: a box's first
  label only keeps acting as a persistent title/prefix for later groups if it never directly
  owned a button row itself — otherwise it's treated as just the first of several
  self-contained, unrelated groups (see `_extract_box_entries` in `pahe_dl/parser.py`).

## How resolutions/tabs map to content (a real gotcha)

`<ul class="tabs-nav"><li>...</li></ul>` items have **no id/data attribute** linking them to
their pane. Binding is done purely by matching DOM order client-side, via:

```html
<script>jQuery(document).ready(function($){ jQuery("ul.tabs-nav").tabs("> .pane"); });</script>
```

i.e. `tabs-nav li[i]` corresponds to `.pane[i]` *within the same `.post-tabs-ver` container*,
by position only. A parser must scope its `.pane` query to `div.post-tabs-ver .pane` (or
`div.post-tabs .pane` — see below), not `.pane` globally: the page contains ~10
`.pane` elements in total (both test pages), most belonging to unrelated sidebar/tabbed
widgets, only 2-3 of which are the actual download tabs.

Both samples used `.post-tabs-ver` (vertical tab variant). The theme also ships a
`.post-tabs` (horizontal) class using the same jQuery plugin/markup shape; a robust parser
should match both `div.post-tabs, div.post-tabs-ver` as candidate containers, then apply the
same pane-scoped extraction. Not yet observed in the wild in this session; flagged for
verification against more sample pages.

## Where the actual download links live — the important part

**No `mega.nz` (or any final-host) URL ever appears in the pahe.ink page HTML.** All
provider buttons — MG, PD, VF, SD, GD, 1F, and their numbered variants (`MG 1`, `PD1`,
`GD 2`, ...) — point to the same third-party gate domain, `teknoasian.com`, e.g.:

```html
<a href="https://teknoasian.com/?ht=FcnED0MFEQfonB79ygrfVnHpY5Jla2xPq3lVVVZPzs8Uk..." target="_blank" class="shortc-button small red ">MG</a>
```

Only the single query parameter `ht` differs between buttons/providers/episodes. It is a
URL-safe-escaped Base64 blob (`%2F`, `%3D` present) that does **not** decode to a
plaintext/mega.nz URL — base64-decoding it yields high-entropy bytes intermixed with
base64-looking text, i.e. it looks like it's either encrypted, or itself another layer of
encoding/HMAC meant to be interpreted only server-side by teknoasian.com. **This token
cannot be decoded client-side/offline; it must be resolved by actually visiting the gate
URL** (see `mega-link-redirect-flow.md` for what happens next, and why that page could not be
fully traced in this session).

### Consequence for identifying "which button is MEGA"

Since the href/domain gives no signal about the destination host, **the only reliable
signal for "this is the MEGA entry" is the anchor's visible text**, matched case-sensitively
against a pattern like `^MG(?:\s*\d+)?$` (to also catch `MG 1`, `MG 2` for split releases).

The button's CSS class also encodes a color (`red`, `white`, `green`, `purple`, `orange`)
that visually groups same-provider buttons, but **the color-to-provider mapping is not
stable across pages** — `green` meant `VF` (Veryfiles) on the GoT page but `SD` on the
Parish page. **Do not use color as the provider signal; use the anchor text.**

Observed provider abbreviations so far: `MG` = Mega, `PD`/`PD1`/`PD2` = Putdrive, `VF` =
Veryfiles, `SD` = (host not yet confirmed — possibly "Streamsb"/another mirror, unverified),
`GD`/`GD 1`/`GD 2` = Google Drive, `1F`/`1F 1`/`1F 2` = 1Fichier. This list should be
treated as provisional and expanded as more pages are sampled — do not hardcode it as
exhaustive.

## Recommended parsing approach (plan-level, no code yet)

1. Fetch with `requests`/`httpx` + a normal browser `User-Agent` header (no JS engine
   required for Part 1 — confirmed the download section is present in the raw HTML).
2. Parse with BeautifulSoup (or `lxml`/`selectolax` if speed matters).
3. Select tab containers: `div.post-tabs-ver, div.post-tabs` (there is normally exactly one
   per content page, but don't assume — iterate all found).
4. Within each container, zip `ul.tabs-nav > li` (tab label text) with `div.pane` (in
   document order, 1:1 positional correspondence) — this reconstructs "which pane is which
   resolution/episode label" since there is no other linkage.
5. Within each pane, do **not** assume a fixed number of `<b>`/`<strong>` "group label" tags
   vs `<a>` "provider link" tags — instead walk the children of `.box-inner-block` as a flat
   stream and run a small state machine:
   - When encountering a bold/strong tag (or the initial `<span style="color:#00ccff">`
     title), update "current group label" (e.g. "480p x264", "Per Episode", "Batch",
     "Episode 1", "720p x264 | 450 MB").
   - When encountering an `<a class="shortc-button ...">`, emit an entry:
     `{tab_label, group_label, provider_text, gate_url=href}`.
   - Ignore `<br/>` / `&nbsp;` (pure spacing).
6. Filter emitted entries to `provider_text` matching the MEGA pattern (`^MG(?:\s*\d+)?$`)
   for this phase, per the user's request to ignore other hosts for now — but keep the
   parser's internal model provider-agnostic (store all providers) so Google Drive etc. can
   be turned on later without re-writing the parser.
7. Present the resulting MEGA entries (tab_label + group_label, e.g. "1080p x264 6CH — Per
   Episode") to the interactive picker (see `docs/planning/cli-ux-notes.md`); the picker's
   resolved value is the `gate_url`, which is the *input* to Part 2, not a final MEGA link.

## What could not be verified in this session

- Whether a horizontal `.post-tabs` (non `-ver`) layout ever actually appears on a real
  page (only the vertical variant was seen in the two samples fetched).
- The true identity of the `SD` provider abbreviation.
- Whether "Per Episode" MEGA links on batch-release pages are single-file, single-folder
  (whole season), or something else — could not confirm without following the MEGA link
  itself (out of scope / not requested this session, and doing so would require Part 2's
  redirect chain anyway).

## Update (movie-page bug follow-up)

The "whether movie pages use a third, simpler shape" open question above was **not**
correct as speculated — movie pages are a third layout, but not a simpler one. See
"Pattern C — movie release" above for the confirmed structure (no tabs at all, bare-text
labels, and a resolution/quality axis packed multiple-per-box instead of one-per-tab). The
parser (`pahe_dl/parser.py`) was fixed accordingly:

1. `parse_page` no longer raises when no `.post-tabs-ver`/`.post-tabs` container exists —
   it falls back to scanning for bare `.box.download` elements (scoped to `div.entry`, the
   main post-content wrapper, to avoid matching an unrelated same-shaped widget elsewhere
   on the page) and parses them as a single untitled "tab" (`tab_label=""`).
2. `_extract_box_entries`'s label-tracking no longer keys off a fixed set of tag names
   (`b`/`strong`/`span`) — it accumulates *any* non-button, non-`<br>` inline content
   (bare text, non-button `<a>`, any other inline tag) since the last flush point, so
   untagged bare-text labels (Pattern C) are captured the same as tagged ones (Patterns A
   and B).
3. A box's first label is only treated as a persistent "title" prefixed onto later groups
   if it never directly owned a button row of its own — otherwise (Pattern C's common case)
   each label is treated as a self-contained, independent group.

Regression-tested against both previously-working pages (`game-of-thrones-season-8-*` and
`parish-season-1`) with a diff against the pre-fix parser: identical entry counts and
`gate_url`s in both cases, with only cosmetic label-text enrichment (e.g. size info that
used to get silently dropped is now included) — no functional regression.
