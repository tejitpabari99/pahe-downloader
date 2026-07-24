# Cloudflare Terminal-Challenge Bypass Investigation (Part 5)

Status: **empirically tested**, live against `teknoasian.com`, 2026-07-24. This follows
directly from `playwright-feasibility.md`'s finding that plain Playwright Chromium drives the
entire "SoraLink" human-verify chain correctly but is blocked by a genuine Cloudflare Managed
Challenge on the terminal reveal POST. This document asks: is there *any* way past that
specific wall, from this environment, without a human solving it by hand each time?

All testing stayed within the same constraints as prior sessions: no mega.nz file content was
fetched, no MEGA login was attempted, no ad/popup content was followed beyond confirming it was
not part of the mega.nz chain, and the moment any technique had a chance of producing a real
result it was checked for a `mega.nz`/`mega.co.nz` URL and nothing further.

## Headline verdict

**No. No technique tested got past the terminal Cloudflare challenge to produce a real
mega.nz URL, from this sandbox's IP.** Two anti-detect browser drivers (nodriver, camoufox)
didn't even reliably *reach* a clean comparison at the terminal step — they broke the chain
earlier for unrelated reasons (see below) — and the one that did reach it under identical
conditions to plain Playwright (patchright) hit a byte-identical wall. Persistent-session
reuse made the next attempt *worse*, not better. No legitimate (source-inspectable, not
Chrome-Web-Store-sight-unseen) browser extension was found that solves this class of
challenge. The only remaining lever that would plausibly work is a paid CAPTCHA-solving
service — documented below, not activated.

## 1. IP reputation — check this first, it reframes everything

```
$ curl -s ipinfo.io
{
  "ip": "65.21.49.199",
  "hostname": "static.199.49.21.65.clients.your-server.de",
  "city": "Helsinki", "region": "Uusimaa", "country": "FI",
  "org": "AS24940 Hetzner Online GmbH"
}
```

This sandbox's outbound IP is a **Hetzner Online GmbH dedicated-server IP** (Hetzner's retail
brand for this IP range is literally `your-server.de` — visible in the reverse-DNS hostname).
Hetzner is one of the largest budget dedicated-server/hosting providers in Europe and its IP
ranges are extremely well-known to abuse-scoring systems (including Cloudflare's) as
datacenter/hosting-provider space, commonly used for scraping, bots, and VPN/proxy exit
nodes — categorically different from a residential ISP address.

**Why this matters for interpreting every other result in this document (and in
`playwright-feasibility.md`):** Cloudflare's bot-management scoring is not purely a browser-
fingerprint check. IP reputation is a first-class, independent signal, and datacenter IPs are
scored far more aggressively than residential ones *regardless of what automation technique
drives the browser*. This means:

- The terminal Managed Challenge observed in every test in this document and the prior session
  may be substantially or entirely an IP-reputation-driven decision, not a browser-fingerprint
  failure that a better driver could fix. This is consistent with what was actually observed:
  every browser tested (plain Playwright, patchright, nodriver, camoufox) passed the *front-
  door* check silently on a first visit (JS-execution/TLS fingerprinting), yet the *specific,
  sensitive* terminal endpoint was reliably gated — a pattern that fits "this IP is scored as
  suspicious for high-value actions" better than "this IP's browsers all look identical and
  bot-like."
- A real end user running this tool from their own home broadband/mobile connection is asking
  a **different, likely easier** question than "can any automation defeat Cloudflare from a
  Hetzner box." This document cannot distinguish those two cases from this environment — no
  residential-IP test was possible here — but it is the single most important caveat on every
  other finding below, and should be stated to the user plainly: **the tool's real-world
  reliability for its actual audience (people running it from home) may be meaningfully better
  than everything observed in this investigation.**
- It also means switching automation *libraries* while staying on this same IP is somewhat
  fighting the wrong variable. A cheap, easy way to partially test this hypothesis without
  a full IP reputation API subscription would be to re-run the exact same patchright chain
  from a residential/mobile connection or consumer VPN exit and compare — flagged as a
  follow-up recommendation, not done in this session (no such alternate network egress was
  available in this sandbox).

## 2. Anti-detection browser drivers

All three were installed and run in a throwaway `.venv` in `/tmp` (not committed), then driven
through the exact click chain confirmed live in `playwright-feasibility.md`
(`.humanVerify button.verify` → countdown → `.postnext` → `#xxc` form `hw=<LLPayload>` POST).
Reference scripts are kept at `docs/research/scratch/{patchright,nodriver,camoufox}-chain-spike.py`.

### patchright (chosen first — most actively maintained: PyPI 1.61.2, released 2026-07-05)

- Installs cleanly (`pip install patchright && patchright install chromium`), reuses the
  existing Playwright Chromium browser cache.
- **Headless, run 1/2:** passed the front door silently (identical to plain Playwright), drove
  the full click chain correctly, then hit the exact same terminal wall: HTTP-level Cloudflare
  Managed Challenge, `<title>Just a moment...</title>`, CSP scoped to
  `https://challenges.cloudflare.com` — **byte-identical page signature** to the one
  `playwright-feasibility.md` recorded for stock Playwright.
- **Headless, run 2/2** (different token, same page): identical outcome again. 2-for-2.
- **Headed via Xvfb:** hit an unrelated UI quirk (an intercepting overlay div, `.panhyu`,
  blocked the normal click; force-clicking worked but landed on a different ad popup than the
  headless runs) — not evaluated further since headless already gave a clean, reproducible,
  directly-comparable result and prior research established headed-mode gives no known
  advantage on this site.
- **Verdict: no improvement.** Patchright's CDP-detection patches don't move the needle on
  this specific Cloudflare Managed Challenge from this IP.

### nodriver (successor to undetected-chromedriver; PyPI 0.50.3, released 2026-05-13)

- Installs cleanly; needs an explicit `browser_executable_path` (it doesn't bundle its own
  Chromium) — pointed at the Playwright-cache Chromium binary, which worked fine.
- **Headless:** the *front-door* Cloudflare check itself challenged nodriver immediately
  (`<title>Just a moment...</title>` right after `page.goto()`, before any gate content ever
  rendered) — something that never happened even once across 11+ tokens of plain
  Playwright/patchright testing. This alone is a worse starting position than the other
  drivers, on this IP.
- **Headed via Xvfb:** passed the front door, correctly found and clicked the verified
  `.postnext` button (confirmed via a DOM dump: exactly one `<button class="myButton
  postnext">Continue</button>`, not a selector collision), but the click **never reached the
  terminal Cloudflare POST at all**. Instead the *same tab* (confirmed via CDP target-ID
  tracking — not a popup-tracking artifact) navigated to an unrelated, real-looking
  `teknoasian.com` blog article (different one each run: an AMD GPU review, an EV battery
  article, an Apple Vision Pro piece). Recovering the actual page source showed why: the
  gate's own script has an explicit **ad-blocker-detection branch** (`if (LLIsBlocked) { ...
  show "Ad blocker detected, please wait Ns" ... } else { window.open(adUrl); xxc.submit(); }`)
  — something in nodriver's default browser environment appears to trip a condition adjacent
  to this branch, diverting the flow before the real `#xxc` POST ever fires.
- **Verdict: not usable, independent of Cloudflare.** nodriver is *less* reliable than
  Playwright/patchright at simply reaching the terminal challenge on this specific site, for
  reasons unrelated to Cloudflare's own defenses.

### camoufox (Firefox-based anti-detect browser; PyPI 0.5.4, released 2026-07-16)

- Heavier install as expected: ~663 MB custom Firefox build + ~45 MB GeoLite2 data, but
  installed and ran without issue (`pip install camoufox[geoip]`, `camoufox fetch`).
- **Headless "virtual" display mode (camoufox's recommended stealth default):** passed the
  front door, drove the click chain, but hit the **exact same failure class as nodriver** — the
  main tab was diverted mid-chain to an unrelated real-looking blog article instead of reaching
  the terminal `#xxc` POST or any mega.nz content.
- Root-caused this one further: camoufox **bundles uBlock Origin by default**. Re-running with
  `exclude_addons=[DefaultAddons.UBO]` changed the intermediate mechanics — it revealed a
  previously undocumented sibling of the `hq`/`hw`/`xxc` chain (a form `id="xq"` with a hidden
  `hq` field, auto-submitted by the page's own `<script>xq.submit()</script>`, POSTing to what
  looks like — and may literally be reusing the URL shape of — a real blog post as its
  `action=` target) — but still terminated at the same kind of unrelated-article diversion, not
  at a Cloudflare wall and not at mega.nz.
- **Verdict: not usable, independent of Cloudflare**, for the same class of reason as
  nodriver — the gate's own anti-adblock/anti-automation branching logic derails the chain
  before the point being tested is even reached.

### Why patchright reached a clean comparison and the other two didn't

This is itself informative, not just a testing inconvenience: plain Playwright and patchright
share Playwright's browser-automation semantics closely enough that the site's `window.open()`
ad-popup call behaves the way `playwright-feasibility.md` already documented (opens a real new
tab/target that can be detected and closed, leaving the main tab's `#xxc` POST to fire and hit
the terminal Cloudflare wall on its own). nodriver's CDP session and camoufox's real-Firefox-
plus-bundled-adblocker environment both, for different underlying reasons, cause the site's own
JS to take a *different branch* than the one already reverse-engineered — meaning these tools
are actively **less compatible with this specific gate's mechanics**, not more capable of
beating Cloudflare. This is a genuinely useful negative result: don't reach for "more stealth"
tooling here expecting it to help — for this particular multi-branch gate script, it can make
things actively worse by triggering paths nobody has mapped.

## 3. Chrome/Firefox extension angle

Searched GitHub and Greasy Fork specifically for extensions/userscripts that claim to defeat
Cloudflare Turnstile/Managed Challenges (as opposed to ad-gate countdown-skippers, already
covered in `prior-art-and-alternatives.md`). Per the constraint, nothing was installed from the
Chrome Web Store sight-unseen; only source-inspectable projects were considered, and none
reached the bar of "load it as an unpacked extension and test it."

Findings, honestly:

- The large majority of "Turnstile solver/bypass" hits on GitHub
  (`x404xx/Turnstile-Solver`, `hasnainshahidx/turnstile_solver`, `art3m4ik3/cloudflare-solver`,
  `ismoiloffS/EzSolver`, `sarperavci/CloudflareBypassForScraping`, etc.) are **standalone
  Python/Selenium/CDP scripts, not browser extensions** — they run a whole separate automated
  browser, not something that attaches to a real user's Chrome session. They also generally
  target the weaker **"non-interactive"/invisible Turnstile widget** mode (a known,
  long-running arms race around simulating a legitimate-looking click inside the checkbox
  iframe), not the class of full Managed Challenge (`cf-mitigated: challenge`, real
  widget-render attempt) observed on `teknoasian.com`'s terminal step.
- The Greasy Fork userscripts found that specifically mention "Cloudflare Turnstile bypass"
  (e.g. "Cloudflare Turnstile Bypass with 2Captcha") are **thin wrappers around a paid
  CAPTCHA-solving API** (2Captcha) — functionally identical to section 4 below, just packaged
  as a userscript. They are not an independent bypass technique.
- **No genuine, source-inspectable Chrome or Firefox extension was found that independently
  defeats a full Cloudflare Managed Challenge for free.** This matches the pattern already
  documented in `prior-art-and-alternatives.md` for the ad-gate layer: every publicly
  reusable "bypass" either predates Cloudflare being added, runs inside an already-trusted
  real user session (inheriting a pass a human already earned), or pays a solving service.
  Nothing here changes that picture — it's the honest answer, not a forced positive.

## 4. CAPTCHA-solving-as-a-service (documentation only — not activated, no signup, no payment)

How it works technically: you send the service the target page's Turnstile **sitekey** (and
usually the page URL); their solver farm (a mix of headless-browser automation, real Turnstile-
API fingerprint replication, and in some cases genuine human solvers in the loop) returns a
valid Turnstile response token within roughly 10–30 seconds; your script injects that token
into the page's hidden `cf-turnstile-response` field (or submits it directly to the site's
verify endpoint) in place of letting the widget resolve itself, and the server-side check
passes. This is a service that specifically solves the Turnstile *token* — it does not know or
care about `teknoasian.com`'s own `hq`/`hw`/`xxc` chain riding on top of it; that scripting
would still need to be handled by the calling code exactly as already reverse-engineered.

Current pricing (checked live, 2026-07-24, Turnstile specifically):

| Service | Price per 1,000 solves |
|---|---|
| 2Captcha | ~$1.20–$1.45 |
| CapSolver | ~$1.20 |
| CapMonster | ~$1.30 |
| Anti-Captcha | ~$2.00 |
| NSLSolver (Cloudflare-specialist) | ~$0.40 |

This matches the ~$1–3/1000 range assumed in the task brief. Most of these offer a small free
trial credit (typically enough for a handful to a few dozen test solves) rather than a
sustained free tier.

**Caveats, stated once plainly (matching the standing guidance in
`playwright-feasibility.md`):** this is technically a different act than raw scraping-bypass
code, but it is still squarely against the target site's Terms of Service, and it introduces a
real, recurring per-resolution cost and a dependency on a third-party account. **This document
does not recommend activating this as a default** — it is included here purely so the user has
an accurate, priced option in hand if the manual-fallback UX (below) proves too disruptive in
practice. Signing up, paying, or wiring this in is explicitly the user's own call to make, not
something done proactively in this investigation.

## 5. Session / reputation persistence

Tested directly with patchright's `launch_persistent_context`, using one shared profile
directory across two back-to-back runs on two different, fresh `ht` tokens:

- **Run 1** (fresh persistent profile): behaved exactly like a normal one-off run — passed the
  front door, drove the chain, hit the terminal Cloudflare Managed Challenge (same signature as
  every other run in this document).
- **Run 2** (same profile, immediately after, brand-new/unrelated token): got **worse, not
  better** — this time even the *front-door* request was challenged
  (`__cf_chl_rt_tk=...` challenge-retry query param appended to the URL, `<title>Just a
  moment...</title>` on the very first `page.goto()`, before any gate content ever loaded).

**Finding: persistent-context/cookie reuse is not a viable mitigation here — it actively hurts.**
A browser profile that has already made one "sensitive-endpoint" hit in this session gets
scored worse on its very next attempt, even against a completely different token. This directly
confirms and sharpens the escalation behavior `playwright-feasibility.md` flagged from repeat
hits on the *same* token — it generalizes to the *profile*, not just the token. There is no
evidence here that a real human solving the challenge once, in a persistent profile, would grant
that profile a durable "trusted" status for subsequent automated runs; what was observed is the
opposite direction (a challenged/incomplete attempt makes the next one worse). This session had
no way to test the specific "human successfully completes the Turnstile checkbox, then
automation reuses that profile" scenario (no successful human solve occurred to persist), so
that exact sub-case remains formally untested — but the directional evidence available argues
against relying on it, and the existing playwright-feasibility.md recommendation to **never
auto-retry** is now reinforced with a second, independent data point (profile-level, not just
token-level).

## Per-technique results table

| Technique | Install effort | Reached terminal step cleanly? | Got a mega.nz URL? | Notes |
|---|---|---|---|---|
| Plain Playwright (prior session) | Trivial (`pip install playwright`) | Yes | No | Baseline; `cf-mitigated: challenge` on terminal POST, 2/2 tokens |
| patchright | Trivial, reuses Playwright's browser cache | Yes | No | Byte-identical wall to plain Playwright, 2/2 headless runs |
| nodriver | Trivial, needs manual Chromium path | No (broke earlier) | No | Front-door challenge in headless; mid-chain diversion to unrelated content in headed mode — never a clean comparison |
| camoufox | Heavier (~700 MB Firefox build) | No (broke earlier) | No | Same mid-chain diversion pattern as nodriver, root-caused to bundled uBlock Origin + the gate's own anti-adblock branch; persists even with UBO excluded |
| Chrome/Firefox extension (source-reviewed only) | N/A — none found worth testing | N/A | No | No genuine free/source-clean Turnstile-bypass extension found; real hits are either standalone scripts (not extensions) or thin paid-CAPTCHA-API wrappers |
| CAPTCHA-solving service (2Captcha/CapSolver/etc.) | Low (API integration), but costs money | Not tested (documentation-only per constraint) | N/A | ~$1.20–$2/1000 solves; technically plausible; ToS/ethical caveat stands; user's own decision |
| Persistent browser context / cookie reuse | Trivial | N/A | No | Made the *next* attempt worse (front-door challenge), not better; no evidence of a durable "trusted profile" effect from this session's data |

## Final recommendation

**Ship the already-planned automated-up-to-the-block + manual-fallback design from
`playwright-feasibility.md`, using plain Playwright or patchright (either is fine — they
perform identically here; patchright is a safe, zero-cost swap if its CDP-leak patches ever
help against a *different* site later, but it buys nothing on this one).** Do not add nodriver
or camoufox to the resolver — both were empirically *less* reliable than plain Playwright at
simply completing this specific gate's chain, for reasons unrelated to Cloudflare. Do not add a
browser extension — nothing legitimate and source-clean was found. Do not build in session/
profile persistence as a reliability feature — the one direct test available suggests it makes
things worse, not better, and adds complexity for no measured benefit. Do not wire up a paid
CAPTCHA-solving service by default — it's a real, working lever (documented above with current
pricing) but should remain an explicit, opt-in choice the user makes for their own account, not
something the tool activates silently.

**The one piece of new information that should change how this result is communicated to the
user:** this entire investigation ran from a Hetzner datacenter IP, which is a systematically
harsher starting position with Cloudflare than a home connection. The tool's actual end users
will very likely run it from residential IPs. **It is plausible — not proven, but plausible and
worth saying plainly — that a normal user on their home network may sail through this exact
gate without ever seeing the terminal challenge this investigation kept hitting.** Recommend
the CLI's manual-fallback message reflect this: something like *"Automated resolution hit a
Cloudflare checkpoint (this can depend on your network) — open this link in your browser to
finish: `<gate_url>`"* rather than language implying the tool itself is fundamentally broken.
If real-world reports come back showing residential users hit the same wall as this sandbox,
that would be the trigger to revisit the paid-CAPTCHA-service option as an opt-in flag.

## Addendum: live bug report confirms the mid-chain diversion also hits plain Playwright (2026-07-24)

A real user run against `resolver.py` (plain Playwright, headless, no anti-detect library)
reproduced exactly the "mid-chain diversion to unrelated ad content" failure mode that section 2
above only observed with nodriver and camoufox - it landed on
`https://teknoasian.com/unlocking-the-future-of-computing-the-power-of-qualcomm-core-oryon/`
after clicking `.postnext`, i.e. a random `teknoasian.com` blog article, not the `#xxc` form's
same-page response and not a Cloudflare challenge either. This means the diversion isn't
exclusive to nodriver/camoufox's environment quirks as section 2 implied - it's evidently a
race condition in the gate's own script (the `if (LLIsBlocked) {...} else { window.open(adUrl);
xxc.submit(); }` branch quoted there), most plausibly triggered when the `window.open(adUrl)`
popup call is blocked/fails and the site falls back to hijacking the main tab, that can also
happen under plain Playwright, just less often than under nodriver/camoufox.

Two bugs compounded to make this a dead end for the user, both fixed in `resolver.py`:

1. **No defense against the diversion itself.** The `.postnext` click handler only waited for
   *any* `document`-resource-type response in the context, so a same-tab navigation to the ad
   article satisfied it exactly as well as the real form response would have. Fix: an init
   script (`WINDOW_OPEN_SHIM_JS` / `_install_window_open_shim()`) installed on every context
   before any navigation, wrapping `window.open()` so a blocked/failed popup returns a truthy
   stub window instead of `null` - this defeats the `if (!w) location.href = adUrl`-shaped
   fallback pattern at its source, so the main tab is never hijacked in the first place.
2. **Misreporting the resulting dead end as a Cloudflare challenge.** Regardless of *why* the
   headless poll failed to find a `mega.nz` URL - a real Cloudflare challenge, or this ad
   diversion, or anything else - `resolve_gate_url()` unconditionally showed "hit a Cloudflare
   challenge" and opened a headed fallback browser window positioned at whatever dead-end page
   it had reached. For the ad-diversion case specifically, that headed window has nothing on it
   to click through - `_is_cloudflare_challenge()` itself was already reasonably precise (title
   check + `challenges.cloudflare.com` iframe check), but its result was never actually consulted
   before choosing the message/exception. Fix: `_looks_like_ad_dead_end()` checks whether the
   page is a genuine Cloudflare challenge or still shows any gate click-chain markers
   (`.humanVerify`, `.postnext`, `#xxc`); if neither, `resolve_gate_url()` raises a new
   `AdNetworkDeadEndError` immediately with an accurate message, skipping the pointless headed
   fallback entirely. When a headed fallback *is* warranted, its status messages and the final
   timeout exception now also say "didn't resolve automatically" rather than "Cloudflare
   challenge" when that's what's actually true.

This doesn't change the headline verdict above (the terminal Cloudflare Managed Challenge itself
is still unsolved by any tested technique) - it fixes a separate, earlier failure mode that could
strike before the terminal challenge is even reached, and that produced a misleading error message
for a real user.

## Session artifacts

Three throwaway virtual environments (`.venv-cf-test` with patchright, `.venv-nodriver`,
`.venv-camoufox`) were created under the scratchpad directory for this session and are not
committed (per convention — see `playwright-feasibility.md`'s equivalent note). The three
chain-driver scripts adapted from `teknoasian-chain-spike.py` for each library are kept as
references at:

- `docs/research/scratch/patchright-chain-spike.py`
- `docs/research/scratch/nodriver-chain-spike.py`
- `docs/research/scratch/camoufox-chain-spike.py`

Each file's header documents its specific confirmed outcome. None is a working resolver; all
three are kept purely so a future session doesn't have to re-derive the exact selectors/APIs
used to reach these conclusions.
