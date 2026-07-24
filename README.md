# Auto Pahe Media Downloader

A CLI tool that takes a [pahe.ink](https://pahe.ink) release page URL, lets you pick a
resolution/episode entry that has a **MEGA** download option, and resolves it to the final
`mega.nz` URL. It never downloads the actual media file, never logs into MEGA, and never
navigates to mega.nz beyond capturing its URL.

Other providers (Google Drive, Putdrive, Veryfiles, 1Fichier) are not supported yet - MEGA
only, for now (see `docs/planning/PRD.md`).

## Why this is needed

pahe.ink never shows the real download host on its own page. Every provider button (including
MEGA) links to the same gate, `teknoasian.com/?ht=<token>`, which runs a multi-step "human
verify" click-chain before finally revealing the destination link. This tool automates that
entire chain with Playwright.

## Install

```bash
pip install -r requirements.txt
playwright install chromium
```

(Optional, Linux only, only needed if you ever run this on a machine with no real display -
see "The Cloudflare limitation" below: `sudo playwright install-deps chromium` and make sure
`xvfb`/`xvfb-run` are available.)

## Usage

```bash
python -m pahe_dl https://pahe.ink/some-release-page/
# or, if installed as a package:
pahe-dl https://pahe.ink/some-release-page/
```

If you omit the URL, the tool will prompt you for one. Example session:

```
$ pahe-dl https://pahe.ink/game-of-thrones-season-8-complete-bluray-480p-720p-1080p/
Fetching https://pahe.ink/game-of-thrones-season-8-complete-bluray-480p-720p-1080p/ ...
Found 4 MEGA entries.
? Select a MEGA download entry:
 » 1) 480p x264 - Per Episode
   2) 720p x264 - Per Episode
   3) 720p x265 - Per Episode
   4) 1080p x264 6CH - Per Episode
Resolving: 720p x264 - Per Episode ...
  ... launching browser...
  ... loading gate URL...
  ... verifying (click-through chain)...
  ... waiting for the resolved link...
  ... resolved automatically.
https://mega.nz/folder/AbCdEfGh#SomeRealKeyGoesHere
```

Use arrow keys + Enter, or type a number (1-9), to pick an entry.

## Options

### `--manual`

```bash
python -m pahe_dl --manual https://pahe.ink/some-release-page/
```

Skips the automated Playwright browser entirely for the resolve step. `pahe.ink` itself is
always parsed via plain HTTP (no browser needed for that part - see `pahe_dl/parser.py`), so
the tool can still discover entries and let you pick one; it just prints the
`teknoasian.com/?ht=...` gate URL for your chosen entry instead of trying to click through it,
e.g.:

```
Selected: 720p x264 - Per Episode
Open this link in your own browser to complete verification and get the MEGA link:
https://teknoasian.com/?ht=some-token-here
```

Use this when:

- You're running the tool on a machine with no display at all (e.g. a remote VM/server) - a
  headed browser window (see below) simply cannot open there.
- The automated browser keeps hitting ad-network dead ends or Cloudflare challenges and you'd
  rather just open the link yourself in your own everyday browser, on whatever machine you like.

## The Cloudflare limitation (read this)

The final step of the teknoasian.com gate chain is sometimes protected by a genuine
Cloudflare challenge that a script cannot solve on its own (confirmed in
`docs/research/playwright-feasibility.md` - this isn't a bug in this tool, it's the actual
state of the site as of this writing).

The tool handles this as gracefully as possible:

- **If the automated chain succeeds** (which it sometimes does), you get the `mega.nz` URL
  printed immediately - zero manual steps.
- **If it hits the Cloudflare challenge**, a real, visible browser window pops up,
  already sitting at the exact point the automation reached (same session, same page - you
  don't need to click through anything that already happened). All you need to do is solve
  the challenge visible in that one window. The moment a `mega.nz` link appears, the tool
  captures it automatically, closes the browser, and prints the link to your terminal. No
  copy-pasting, no second browser tab, no re-running the tool.
- If nothing resolves within a few minutes, the tool times out with a clear error message
  rather than hanging forever.
- **Either way, before it opens (or gives up on) a browser window, the tool also prints the
  plain gate link to your terminal** ("Open this link in your own browser to complete
  verification..."), so you're never stuck with just an error and no way forward - you can
  always paste that link into your own browser by hand, on any machine, exactly like
  `--manual` mode (above) does from the start.

The tool never retries the same link automatically if it fails - per the research, retrying
the same token tends to make Cloudflare's response worse, not better. If you want to try
again, re-run the tool (this may or may not get a fresh token, since pahe.ink pages are
cached) or pick a different resolution/entry.

**Not every dead end is a Cloudflare challenge.** teknoasian.com's ad-monetization step
occasionally diverts the browser tab to unrelated ad content (e.g. a random blog article on
the same domain) instead of either the download link or a real Cloudflare challenge - see
`docs/research/cloudflare-bypass-investigation.md`. There's nothing to click through on a
page like that, so the tool detects this case specifically and fails fast with a clear
"ad-network dead end" error instead of opening a pointless visible browser window and telling
you it's a Cloudflare challenge. If you see that error, just re-run the tool - it's normally
transient - or try `--manual` instead. Note it can also be triggered by a network/DNS-level ad
blocker (Pi-hole, AdGuard Home, a VPN's built-in blocker, etc. - not a browser extension; the
automated browser this tool launches is a fresh, extension-free session, so a browser-extension
adblocker on your everyday browser is not the cause) blocking requests the gate script's own
ad-blocker-detection logic checks for. If you suspect that, `--manual` sidesteps the whole
automated chain and lets you clear the gate in your own browser instead.

## Project layout

- `pahe_dl/parser.py` - fetches and parses a pahe.ink page into resolutions/episodes -> MEGA
  gate URLs.
- `pahe_dl/picker.py` - the interactive `questionary`-based entry picker.
- `pahe_dl/resolver.py` - the Playwright automation that resolves a gate URL to a `mega.nz`
  URL, including the hybrid headless/headed-fallback logic described above.
- `pahe_dl/cli.py` - wires the above together into the `pahe-dl` command.

See `docs/planning/PRD.md` and `docs/planning/TASKS.md` for the full design/build spec, and
`docs/research/` for the investigation this tool is based on.

## Constraints (by design, not limitations to work around)

- Never downloads the actual media file - only resolves/prints the final URL.
- Never logs into MEGA or uses a MEGA account.
- Never clicks ads/popups encountered during the gate chain (a monetization popup is known to
  fire during the flow - it's detected and discarded automatically).
- Single request per invocation - no concurrency, no batch mode.
