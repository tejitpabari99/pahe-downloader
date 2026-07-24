# PRD — Auto Pahe Media Downloader (MEGA resolver CLI)

## What

A Python CLI tool that takes a `pahe.ink` content page URL, lets the user interactively pick
a resolution/episode entry that has a MEGA ("MG") download option, and outputs the final
resolved `mega.nz` URL for that entry. It never downloads the actual media file.

## Why

pahe.ink never exposes the real host URL on its own page — every provider button (MEGA,
Google Drive, Putdrive, ...) points at the same opaque `teknoasian.com/?ht=<token>` gate,
which is itself behind a multi-step "human verify" click-chain and, at its terminal step, a
Cloudflare challenge that does not always auto-clear. Manually working through this for every
episode/resolution is tedious. This tool automates everything that can be automated (page
parsing, entry selection, the entire gate click-chain up to the terminal step) and asks for
human help only for the one specific sub-step (a Cloudflare challenge) that cannot currently
be scripted around, without forcing the user to start over in a different browser/tab.

## Scope (v1)

- Provider: **MEGA only** (`MG`, `MG 1`, `MG 2`, ... button text). Other providers (GD, PD,
  VF, 1F) are out of scope for v1, but the parser's internal model stays provider-agnostic
  (see Non-Goals) so they can be turned on later without a rewrite.
- Input: one `pahe.ink` page URL (CLI arg, or prompted for if omitted).
- Parsing: fetch the page over plain HTTP (no JS needed for this part — confirmed in
  research), extract resolution/episode tabs and their MEGA gate URLs, handling both known
  layout patterns (batch-release "tabs=resolution" and ongoing-release "tabs=episode").
- Selection: an arrow-key + numeric-shortcut interactive picker (`questionary`) over the
  discovered MEGA entries.
- Resolution: drive the teknoasian.com gate chain (Click To Verify -> countdown ->
  Continue/Get Link -> `#xxc` form POST) via Playwright Chromium, reusing the validated
  selectors from `docs/research/scratch/teknoasian-chain-spike.py`.
- **Hybrid fallback**: if the chain completes automatically, print the `mega.nz` URL and
  exit. If the terminal step hits the known Cloudflare block, keep the *same* automated
  browser window open in headed mode, positioned exactly where automation left off, poll it
  for a `mega.nz`/`mega.co.nz` URL to appear once the user manually clears the visible
  challenge, auto-capture it, close the browser, print the URL. No copy/paste, no second
  browser, no re-running the tool.
- Output: the final `mega.nz`/`mega.co.nz` URL as plain text to stdout. Nothing else is
  fetched or downloaded past that point.

## Non-goals (v1)

- No support for GD/PD/VF/1F or any non-MEGA provider (deferred; same gate pattern expected
  to apply later, per research).
- No downloading of the actual media file bytes, ever.
- No MEGA login/account usage — final links are resolved/consumed anonymously.
- No CAPTCHA-solving service integration (explicitly rejected as a default per
  `playwright-feasibility.md` — cost/ToS/legal gray area, user's own call only, not built).
- No automatic retries against the same `ht` token (research shows retries make Cloudflare's
  response worse, not better).
- No headless-detection evasion/stealth patching beyond what ships with a normal Playwright
  Chromium session (research found the plain session already passes the Cloudflare front
  door silently; the only wall is the terminal POST, which stealth patches did not affect in
  testing).
- No concurrency / batch-resolving multiple entries in one run (single request per
  invocation, per the research doc's rate-limiting/courtesy recommendation).
- No handling of movie-only page layout beyond what falls out naturally from the two known
  patterns (not sampled in research; noted as a gap, not blocking).

## Success criteria

- Running the CLI against the real example URL
  (`https://pahe.ink/game-of-thrones-season-8-complete-bluray-480p-720p-1080p/`) correctly
  lists real resolutions and MEGA entries, lets the user pick one, and drives the automated
  chain up to the terminal step without crashing.
- When the terminal step succeeds automatically (not guaranteed, per research — Cloudflare
  behavior may vary by run/IP), the tool prints a valid `mega.nz` URL with zero manual steps.
- When the terminal step hits the known Cloudflare block, the tool opens a headed browser at
  the correct point, polls correctly, and captures/prints the link the moment a `mega.nz` URL
  appears, without hanging forever (bounded timeout, e.g. 3-5 minutes) or crashing.
- The tool never fetches ad/popup content, never navigates to mega.nz beyond capturing its
  URL, never logs into MEGA, never downloads file bytes.

## Architecture (one line per module)

- `pahe_dl/parser.py` — HTTP fetch + BeautifulSoup parse of a pahe.ink page into resolutions
  -> entries -> gate URLs (MEGA-filtered for now, provider-agnostic internally).
- `pahe_dl/picker.py` — `questionary`-based interactive selection over parsed MEGA entries.
- `pahe_dl/resolver.py` — Playwright automation implementing `resolve_gate_url(gate_url) ->
  str`, including the hybrid auto/headed-fallback behavior.
- `pahe_dl/cli.py` — wires the above together; the executable entry point.

This mirrors the function boundary already agreed in `docs/planning/cli-ux-notes.md`
(`resolve_gate_url(gate_url: str) -> str`), keeping parsing/picking independently testable
from gate-resolution.
