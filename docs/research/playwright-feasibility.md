# Playwright Feasibility — teknoasian.com Cloudflare Gate (Part 4)

Status: **empirically verified with a live Playwright install against the real site**, in
this sandboxed environment, on 2026-07-23. All testing was read-only with respect to the
final destination: no mega.nz file content was ever fetched, no MEGA login was performed, no
ad/popup content was followed. 11 distinct, real `?ht=` tokens were used across 2 different
pahe.ink pages during this session (all now consumed by this testing).

## Go/no-go verdict

**Conditionally no, as of this session — with a concrete, well-understood blocker, not an
unknown one.**

Playwright Chromium installs cleanly, launches cleanly (headless and headed-via-Xvfb), passes
Cloudflare's front-door check silently on every attempt (no interstitial ever appeared on the
initial page load), and can correctly drive the *entire* legitimate on-page "SoraLink" human-
verification UI (the exact `Click To Verify` → wait → `Continue`/`Get Link` → form-submit
chain hypothesized from prior art). But the **final step of that chain — the POST that would
actually reveal the resolved link — is protected by a genuine Cloudflare Managed
Challenge/Turnstile that did not auto-clear within 20–30 seconds in either headless or headed
mode**, in 2-for-2 full attempts. This is not a guess or a single flaky result — it is a
clean, reproducible wall at the exact same point in the flow, on two different tokens from two
different pages.

This means: a pure, unattended Playwright resolver is **not currently viable** for this one
specific request without either (a) an interactive/paid CAPTCHA-solving integration, or (b) a
manual-fallback UX for the user to finish that one step themselves. Sections below lay out
both options plus a recommended architecture built around this reality.

## Install requirements (all confirmed working, this session)

| Item | Result |
|---|---|
| `pip install playwright` | Succeeded, no network/permission issues. Package version **1.61.0**. |
| `playwright install chromium` | Succeeded. Downloaded Chrome for Testing 149.0.7827.55 (~177 MiB) + Chrome Headless Shell 149.0.7827.55 (~114 MiB). |
| `playwright install-deps chromium` | Succeeded via `apt-get` as root, **no OS packages were actually missing** — every required lib (`libasound2t64`, `libnss3`, `libgbm1`, `xvfb`, font packages, etc.) was already present on this machine's Ubuntu 24.04 base image. Ran non-interactively (`DEBIAN_FRONTEND=noninteractive`), took well under 90s once `apt-get update` had run. |
| Root/sudo needed? | This session ran as `root` already; no sudo prompts encountered. On a non-root box, `install-deps` needs sudo. |
| Disk footprint | Browser cache `~/.cache/ms-playwright`: **1.3 GB**. Python venv (`playwright`, `beautifulsoup4`, deps): **156 MB**. Total ≈ **1.46 GB**. Machine had 8.3 GB free before install, 7.3 GB after — comfortably fits. |
| Headless sufficient? | **Yes for launching.** `headless=True` Chromium launches and renders JS fine (confirmed against example.com and against the full teknoasian.com page, including its jQuery/analytics/ad scripts). |
| Display/Xvfb needed? | `Xvfb`/`xvfb-run` were **already installed** on this box (part of the `install-deps` package set) despite `$DISPLAY` being unset. `xvfb-run -a python3 ...` successfully ran Chromium in `headless=False` mode. **Headed-via-Xvfb was tested as the "one stealth improvement" and made no difference to the Cloudflare outcome** (see below) — so there is no known reason to prefer it over plain headless for this specific site, though it remains available as a fallback knob. |
| Environment/venv | Used a throwaway local venv (`.venv-spike`, not committed) rather than global site-packages, per instructions — a real implementation should do the same (e.g. `.venv` + `requirements.txt`/`pyproject.toml`, not created this session since this was investigation-only). |

**No installation blockers of any kind were hit.** This environment has full outbound network
access to PyPI, the Playwright CDN, and pahe.ink/teknoasian.com; disk space and permissions
were sufficient throughout.

## What was actually observed, hop by hop

### Hop 0 — pahe.ink → gate URL
Confirmed again, unchanged from prior research: plain HTML, `MG` anchors point to
`teknoasian.com/?ht=<token>`. Tokens are **static per cached page** (re-fetching the same
pahe.ink URL minutes apart returned byte-identical `ht` values — the site uses LiteSpeed page
caching, as previously noted), not per-visitor/session.

### Hop 1 — teknoasian.com: Cloudflare's front door does *not* challenge Playwright
This is the single biggest surprise versus the earlier `curl`-based finding. A first, cold
`page.goto()` to a fresh `?ht=` URL — plain headless Chromium, **no stealth patches at all** —
got an immediate **HTTP 200** with `server: cloudflare` and no `cf-mitigated` header, i.e. no
"Just a moment..." interstitial whatsoever. This happened consistently across all first-visit
attempts (headless, headless+referer, headless+stealth, headed). Cloudflare's TLS/JA3 +
JS-execution front-door check is evidently satisfied by an ordinary Playwright Chromium
session; the earlier `curl`/`WebFetch` 403s from Part 2 research are fully explained by those
tools' inability to execute the CF JS challenge at all, not by any special hardening against
headless browsers per se.

### Hop 2 — the real gate content, and the actual UI chain
The `?ht=` request causes a same-site redirect to the bare `https://teknoasian.com/` URL,
which is visually indistinguishable from the site's ordinary WordPress blog homepage — but it
carries an **injected `<script>` block** (present only when a valid `ht` token drove the
request; confirmed absent on a plain, tokenless visit to the same URL) that implements exactly
the flow the prior-art research predicted, with real, current source recovered this session:

1. On `DOMContentLoaded`, JS inserts a `.humanVerify` widget: **"Please verify that you are
   human" + a "Click To Verify" button** (or, on some page states, "Click Generate Link to
   start" + "Generate Link" — a `IsPost` branch keyed on whether `.post-entry p` elements exist
   in the underlying page — both branches converge on the same next step).
2. Clicking it starts a 5-second client-side countdown ("Please wait for N seconds"), then
   reveals a **"Continue"/"Get Link" button** (`.postnext`) — on some page states there's an
   extra "Scroll down slowly then find and click Continue" intermediate stage with its own
   4-second countdown first.
3. Clicking `.postnext` does two things simultaneously:
   - `window.open('https://s0-greate.net/go/1445313', '_blank')` — **a monetization popup,
     unrelated to the mega.nz chain.** This must be detected and closed/ignored, never
     navigated. (Confirmed via `context.on('page', ...)`; successfully ignored every time.)
   - `document.getElementById('xxc').submit()` — a plain HTML `<form method="POST">` (no
     `action` attribute, so it submits back to the current URL) carrying one field,
     `hw=<LLPayload>`, where `LLPayload` is a long base64-looking blob embedded earlier in the
     page's inline script. This **is** the `hq`/`hw`/`xxc` mechanism from
     `sharoon7171/skip-wait-bypass-timers-countdowns-extension`'s `hq-chain.ts`, confirmed live
     and current, not stale — the field name (`hw`), the variable name (`LLPayload`), and the
     form id (`xxc`) all match verbatim.
4. **This is the point where the flow is blocked.** The POST response is a genuine Cloudflare
   Managed Challenge: HTTP 403, `cf-mitigated: challenge`, title `Just a moment...`, a CSP
   scoped to `challenges.cloudflare.com`, and browser console evidence of an actual Turnstile
   widget attempting to render (WebGL calls, "GPU stall due to ReadPixels", canvas/font
   fingerprinting probes). It **did not clear within 20–30 seconds** in either headless or
   headed(+Xvfb) mode, across 2 separate full attempts on 2 separate tokens. No `mega.nz` URL,
   nor any further chain artifact, ever appeared past this point.

This is a materially different (and more precise) picture than Part 2's original finding: the
Cloudflare wall isn't at the front door (hop 1) at all — it's placed specifically on the
**terminal "reveal" POST**, after a full, realistic, human-shaped interaction sequence has
already been completed. That is a much harder thing to script around, because there is no
earlier point in the flow where a plain HTTP client could shortcut past a request that
Cloudflare hasn't yet decided to gate.

## Captcha/anti-bot characterization (Step 3)

- **Not** a simple auto-clearing Managed Challenge for this specific request. It is
  functionally a **hard, interactive-grade Turnstile challenge** that a non-interactive script
  cannot pass: it presented as `cf-mitigated: challenge` + a real widget-rendering attempt, and
  showed no sign of resolving on its own within a generous wait window, in a real
  (non-headless, Xvfb-driven) browser with full click-based human-shaped interaction leading up
  to it.
- We could not determine from the client side alone whether this specific challenge is a fully
  invisible "Managed Challenge" that just happens to need longer than 30s, or an interactive
  Turnstile that fundamentally requires a checkbox click/human action — a screenshot of the
  live widget was not captured in this session (token budget was spent on breadth — 2 full
  end-to-end attempts — rather than depth on this one sub-question; see Chain Stability below
  for why 2 was judged sufficient). Either way, the practical conclusion for this tool is the
  same: it did not pass automatically inside a normal CLI-tool time budget.
- **Escalation behavior observed:** hitting the *same* `?ht=` URL a second time (in an
  unrelated, earlier test that didn't yet know about the click-through UI) got a **worse**
  outcome, not a better one — an immediate 403 challenge on the repeat hit, versus a silent 200
  on the first hit. This is consistent with Cloudflare/the origin scoring *repeated automated
  hits to sensitive endpoints* more harshly, not with reputation improving over time. **Do not
  design the tool to retry the same token automatically** — retries look more bot-like, not
  less.
- **Persistent context / cookie reuse does not look like a reliable mitigation** for the
  specific wall we hit: the challenge triggers on the *terminal POST of the human-verify chain*
  itself, on the very first attempt, before any question of session reuse arises. A persistent
  browser profile might still be worth carrying forward for hop-1 (it costs nothing and hop 1
  passes silently anyway), but it is not expected to change the outcome at the terminal step
  based on what was observed.
- **Recommendation on paid CAPTCHA-solving services:** this class of tool (2captcha,
  Anti-Captcha, CapSolver, etc.) does exist and could plausibly integrate with a Cloudflare
  Turnstile challenge. It is explicitly **not** recommended as a default here — it costs money
  per resolution, sits in a legal/ToS gray area on top of the base activity, and was not tested
  in this session. It should be treated purely as **the user's own optional decision** if the
  manual-fallback UX below proves too disruptive in practice, not as something to wire up
  proactively.
- **Recommended handling for the CLI:** build a **detect-and-fall-back** flow. When the
  resolver detects `cf-mitigated: challenge` / a "Just a moment..." title / no `mega.nz` URL
  after the full click-chain plus a bounded wait, it should stop, and print the original
  `teknoasian.com/?ht=...` gate URL for the user to **open in their own real, already-trusted
  browser** to finish manually and copy the resulting mega.nz link themselves. This keeps the
  tool honest about what it can and can't automate, and doesn't burn additional automated
  attempts against the same token (which, per the escalation note above, appears to make things
  worse).

## Chain-stability findings (Step 4)

**The mechanism is completely stable; only the token content differs**, exactly as the user
suspected and as prior art predicted:

- Tested across **2 different pahe.ink pages** (`game-of-thrones-season-8-...` batch release,
  `parish-season-1` episodic release) and **11 total distinct tokens**.
- Every single attempt exhibited the *identical* structural sequence: `?ht=` GET → redirect to
  bare `teknoasian.com/` → injected `.humanVerify` widget → `Click To Verify` → countdown →
  `.postnext` (`Continue`/`Get Link`) → simultaneous ad-popup + `#xxc` form POST with
  `hw=<LLPayload>` field. Field names, form id, JS variable names, and DOM class names
  (`.humanVerify`, `.Skipper`, `.postnext`, `#xxc`) were byte-identical across every token and
  both pages.
- The two full end-to-end attempts that went all the way to the terminal POST (one headless,
  one headed via Xvfb, on two different tokens from the same page) hit the **exact same
  Cloudflare Managed Challenge outcome**, at the exact same step, with no variation in
  behavior. This consistency is itself informative — it means the blocker is systemic (applied
  uniformly to this endpoint) rather than an occasional fluke, which is actually good news for
  *designing around it* (the detect-and-fall-back behavior above can be built with confidence
  it will trigger reliably rather than intermittently) even though it's bad news for full
  automation.
- No attempt reached a state with a visible `mega.nz`/`mega.co.nz` URL. **A real mega.nz URL
  was not obtained in this session.**

## Architecture recommendation for the resolver module

Given the above, `resolve_gate_url(gate_url: str) -> str` (per `docs/planning/cli-ux-notes.md`)
should be implemented as:

1. **One Playwright Chromium instance per CLI invocation** (not a long-lived daemon — this is a
   single-shot CLI tool). Headless by default; no evidence headed/Xvfb changes outcomes, so
   don't add that complexity/dependency by default. Keep a `--headed` debug flag for future
   troubleshooting only.
2. Navigate to the gate URL with a normal desktop UA/viewport, `referer` set to the originating
   pahe.ink page URL (harmless to include, matches real usage, no observed downside).
3. Drive the click chain **defensively via selectors matched against the page's own DOM/class
   names observed above** (`.humanVerify button.verify`, `.Skipper button.skipcontent`,
   `.postnext`), not by coordinates or visual position — this already matches the safety
   guardrail from `mega-link-redirect-flow.md`. Wrap each stage in a bounded wait
   (`wait_for_selector` with a ~10s timeout) so a changed page structure fails fast/loud rather
   than hanging.
4. **Explicitly intercept and discard any `page`/popup event** (`context.on("page", ...)`)
   before/around the final click — this is where the ad monetization popup fires — close it
   immediately, never let it navigate, never inspect its content beyond confirming it's not the
   mega.nz chain.
5. After the terminal click, poll for up to ~15–20s for either (a) a `mega.nz`/`mega.co.nz` URL
   appearing in any response URL or page content (success path), or (b) a `cf-mitigated:
   challenge` response / "Just a moment..." title (known-blocked path). On (b), **stop
   immediately** (per the escalation-risk finding — do not retry the same token) and surface
   the original gate URL to the user as a manual-completion fallback, clearly distinguishing
   this from an unexpected/unknown error.
6. Do **not** build in automatic retries against the same `ht` token — evidence suggests this
   makes Cloudflare's response worse, not better. If the user wants to try again, that should
   mean re-fetching a fresh render of the pahe.ink page (which may or may not yield a new
   token, since tokens appeared to be cache-static) or trying a different resolution/entry.
7. Isolate this whole module cleanly (as already planned) so that when — not if — teknoasian.com
   changes its chain again (it already has at least 3 times per the prior-art survey), the fix
   is contained to this file's selectors/regexes.

## Performance

- Page load + Cloudflare pass-through (hop 1): **~2–5 seconds**.
- Full click-through chain (Click To Verify → countdown(s) → Continue/Get Link click): adds
  another **~6–10 seconds** of deliberate, scripted wait time (mirroring the site's own
  countdown timers, which cannot safely be skipped without risking detection or breaking the
  chain).
- Total, when it works (hops 0–2, not counting the blocked terminal step): **roughly 10–15
  seconds end-to-end** — a "wait a bit," not instant, but well within CLI-tool tolerance. This
  is a meaningfully slower operation than a plain HTTP fetch, so the CLI should show a visible
  progress indicator/spinner with stage labels (e.g. "clearing gate...", "verifying...",
  "waiting Ns...") rather than a silent hang.
- The failed terminal step adds the wait budget spent polling for the Cloudflare title to clear
  (~20–30s was used in testing) before giving up — this should be tuned down to something more
  CLI-friendly (e.g. 10–12s) once this is implemented for real, since evidence suggests it
  doesn't clear at all rather than clearing slowly.

## Risk / ToS / ethical caveats

Automating past Cloudflare's bot-management protections is against the ToS of essentially
every site that deploys Cloudflare, including this one, regardless of technical feasibility.
This applies to the click-through automation described above just as much as it would to a
lower-level bypass. This is stated once, plainly, as the user's prior instructions require it
be surfaced — it is the user's call whether to proceed, not a judgment this document renders
further.

## Session artifacts

- Three throwaway Playwright scripts were written during this investigation
  (`spike.py` — raw gate-URL navigation/diagnostics, `spike_click.py` — real in-page click
  simulation, `spike_chain.py` — the full human-verify click chain). All ran inside a scratch
  local venv (`.venv-spike/`, ~156 MB) that has been **deleted** after this session; it was
  never committed.
- One of the three, the full-chain driver, is kept as a reference for whoever implements the
  real resolver, since it encodes the exact live DOM selectors and click sequence discovered
  above (`.humanVerify button.verify`, `.Skipper button.skipcontent`, `.postnext`, `#xxc`) —
  see `docs/research/scratch/teknoasian-chain-spike.py`. It is explicitly marked in its own
  header as a spike, not production code, and as a script that (per this doc's findings)
  reliably hits the Cloudflare wall rather than producing a working mega.nz URL. The other two
  were pure diagnostics and were not kept.
