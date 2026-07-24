# TASKS — Auto Pahe Media Downloader (MEGA resolver CLI)

Numbered, junior-dev-followable checklist. Do these in order; commit after each numbered
section (one commit per logical task).

## 1. Project scaffolding
- [ ] Create `pahe_dl/` package: `__init__.py`, `parser.py`, `picker.py`, `resolver.py`,
      `cli.py`.
- [ ] Create `pahe_dl/__main__.py` so `python -m pahe_dl <url>` works.
- [ ] Create `requirements.txt` pinning `requests`, `beautifulsoup4`, `questionary`,
      `playwright`.
- [ ] Create `pyproject.toml` with a console-script entry point (`pahe-dl`).
- [ ] Verify `pip install -r requirements.txt` and `playwright install chromium` succeed.

## 2. Parser (`pahe_dl/parser.py`)
- [ ] Fetch a pahe.ink URL with `requests` + a normal desktop browser User-Agent.
- [ ] Find tab containers: `div.post-tabs-ver, div.post-tabs`.
- [ ] Zip `ul.tabs-nav > li` (tab label) with `div.pane` (in document order) inside each
      container.
- [ ] Within each pane, walk `.box-inner-block` children as a flat stream with a small state
      machine: bold/strong/title tags update "current group label"; `<a class="shortc-button
      ...">` tags emit `{tab_label, group_label, provider_text, gate_url}`.
- [ ] Match `provider_text` against `^MG(?:\s*\d+)?$` (case-sensitive) to flag MEGA entries;
      keep all providers in the internal model (provider-agnostic), just filter for MEGA when
      producing the CLI-facing list for now.
- [ ] Return a structured object: list of resolutions/tabs, each with its list of entries
      (label, provider, gate_url, is_mega).
- [ ] Test against the real example URL:
      `https://pahe.ink/game-of-thrones-season-8-complete-bluray-480p-720p-1080p/` — confirm
      real resolutions and real MEGA gate URLs are found.
- [ ] Handle the "no MEGA option for this entry" case gracefully (skip, don't crash).

## 3. Picker (`pahe_dl/picker.py`)
- [ ] Build `questionary.select(...)` choices from the parser's MEGA-filtered entries, label
      format `f"{tab_label} — {group_label}"`.
- [ ] Support numeric shortcut selection (single-digit) per `questionary`'s built-in
      shortcut-key behavior.
- [ ] Return the chosen entry's `gate_url`.
- [ ] Handle the empty-list case (no MEGA entries found on this page) with a clear message,
      no crash.

## 4. Resolver (`pahe_dl/resolver.py`)
- [ ] Implement `resolve_gate_url(gate_url: str, referer: str | None = None) -> str`.
- [ ] Base the automated chain directly on
      `docs/research/scratch/teknoasian-chain-spike.py`'s validated selectors/sequence:
      `.humanVerify button.verify` -> wait for `.postnext` (handling the optional
      `.Skipper button.skipcontent` intermediate stage) -> click `.postnext`.
- [ ] Intercept and immediately close any popup (`context.on("page", ...)`) without ever
      navigating it or reading its content beyond the URL (for logging).
- [ ] After the terminal click, poll (bounded, e.g. ~15-20s) for a `mega.nz`/`mega.co.nz` URL
      in response URLs or page content.
- [ ] Detect the known-blocked condition: HTTP 403, `cf-mitigated: challenge` header, or page
      title containing "Just a moment" / a Turnstile widget present.
- [ ] On success: close the browser, return the URL.
- [ ] On detected block: **do not close the browser**. Relaunch/keep it in headed mode
      (`headless=False`, e.g. via Xvfb in this sandbox) positioned at the same blocked page
      (no re-navigation, no retry of the same token from scratch — reuse the already-loaded
      page/context), then poll for up to ~3-5 minutes for a `mega.nz`/`mega.co.nz` URL to
      appear (href, page content, or navigation), auto-capture it, close the browser, return
      it. If the timeout elapses with nothing found, raise a clear, distinct exception/error
      message (not a silent hang, not a crash).
- [ ] Never retry the same `ht` token automatically (per research: retries make Cloudflare
      worse, not better).
- [ ] Verify headlessly: confirm the automated steps run correctly and the block condition is
      correctly detected (this sandbox is expected to hit the Cloudflare wall — that's fine).
- [ ] Verify the headed-fallback mechanism using `xvfb-run`: confirm the browser launches
      headed, polling loop runs, and it times out sensibly if nothing resolves — full manual
      challenge-solving is NOT expected to be verifiable by the agent building this.

## 5. CLI wiring (`pahe_dl/cli.py`)
- [ ] Accept a pahe.ink URL as a CLI arg; prompt for one if omitted.
- [ ] Run the parser; if no MEGA entries found, print a clear message and exit non-zero.
- [ ] Run the picker; get the chosen `gate_url`.
- [ ] Call `resolve_gate_url`; print progress/stage messages (per cli-ux-notes.md's
      recommendation to avoid a silent hang during the ~10-15s automated chain).
- [ ] On success, print the final `mega.nz` URL plainly (nothing else, so it's easy to
      copy/pipe).
- [ ] On unrecoverable error (timeout, parse failure, no MEGA entries), print a clear error
      message and exit non-zero — no stack-trace-only failures for expected error paths.
- [ ] Test end-to-end against the real example URL as far as sandbox automation allows.

## 6. Docs
- [ ] Write top-level `README.md`: what the tool does, install steps (`pip install -r
      requirements.txt`, `playwright install chromium`), usage example, and an honest note on
      the Cloudflare limitation (auto when possible, otherwise one visible browser window for
      the user to clear a challenge, then automatic capture — no other manual steps).
