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
- Whether movie pages (single quality, no episodes/batches) use a third, simpler shape.
  Recommend sampling one before implementation.
