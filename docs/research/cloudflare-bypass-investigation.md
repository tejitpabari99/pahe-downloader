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

## Addendum: revisiting whether a network-level ad blocker could still defeat the shim fix (2026-07-24)

Follow-up to the addendum above, triggered by a second live report: the user re-ran the tool after
the `WINDOW_OPEN_SHIM_JS` fix landed and it still didn't resolve automatically, and asked whether
their own ad blocker could be the cause.

**Short answer: plausible, and it's a real gap the shim doesn't cover - not overlap with the bug
already fixed.** Re-reading the reverse-engineered branch quoted in both the section-2 writeup and
the addendum above, closely:

```
if (LLIsBlocked) { ... show "Ad blocker detected, please wait Ns" ... }
else { window.open(adUrl); xxc.submit(); }
```

Two things follow from this shape that weren't spelled out before:

1. **`xxc.submit()` - the call that actually reaches the real mega.nz chain - lives inside the
   `else` branch, gated on `LLIsBlocked` being false.** `WINDOW_OPEN_SHIM_JS` only changes what
   `window.open(adUrl)` *returns* inside that same `else` branch (truthy stub instead of null,
   defeating a `if (!w) location.href = adUrl`-shaped fallback pattern *elsewhere* in the gate's
   click chain per the first addendum). It does nothing to influence `LLIsBlocked` itself, which is
   decided by a separate, not-yet-recovered ad-blocker-detection check *before* either branch runs.
   If that check evaluates true, the `if` branch runs instead - a branch the shim was never designed
   to touch - and whatever it does next (the recovered fragment only shows a "please wait" message,
   not its eventual resolution) is exactly the kind of thing that could plausibly still divert the
   tab, independent of the window.open() fix entirely.
2. **A DNS/router/VPN-level ad blocker (as opposed to a browser-extension one) is a plausible way to
   flip `LLIsBlocked` to true** - most ad-blocker-detection techniques work by trying to load a
   known ad-related resource (a bait script/image/element) and checking whether it failed, which is
   exactly what a network-level blocker (Pi-hole, AdGuard Home, a VPN's built-in filter, some
   corporate/router-level policies) would cause regardless of which browser or profile makes the
   request - unlike a browser popup blocker, which the shim already handles by design.
   `resolver.py`'s browser context is confirmed vanilla and extension-free (`grep -n "launch\b"
   pahe_dl/resolver.py` shows only `playwright.chromium.launch(headless=...)` - no
   `launch_persistent_context`, no `user_data_dir`, no `channel=`, i.e. a fresh bundled Chromium
   with the user's real profile/extensions never in the picture), so a **browser-extension**
   adblocker on the user's everyday browser specifically is *not* a plausible cause here - but a
   **network-level** one still is, since it would affect this tool's launched browser too, on
   whatever network it runs from.

What this addendum does *not* do is claim certainty: the exact `LLIsBlocked` detection logic and
what the `if` branch does after its "please wait" message were never fully recovered (nodriver's
and camoufox's environments tripped *a* condition adjacent to this branch per section 2, but which
one, and via which detection mechanism, was never pinned down precisely enough to write a targeted
JS counter-patch the way `WINDOW_OPEN_SHIM_JS` could for the `!w` case). Writing speculative code
against an unrecovered detection function isn't a sound fix. Instead, the practical mitigation
shipped alongside this addendum is a way to route around the whole problem: `--manual` (see
`pahe_dl/cli.py`) skips the automated browser for the resolve step entirely and just prints the
gate URL, and the automated flow itself now also prints that same link as a fallback before it
opens (or fails to open) a headed browser window, for both the Cloudflare-challenge and
ad-network-dead-end cases - see `manual_fallback_message()` in `resolver.py`. A user who suspects
their network is the cause (or who's running the tool somewhere with no display for a headed
browser at all, like a headless VM) can just clear the gate by hand from there, without depending on
this tool correctly out-guessing every branch of a script that was only ever partially recovered.

It's also worth noting, separately, that "the user hasn't picked up the shim fix yet" remains a live
possibility for the specific second report that triggered this addendum - the report described the
resulting browser window as "just opens the same tekno... link," which is consistent with either a
genuine post-fix Cloudflare-challenge headed-fallback window (same domain, so it can look
unremarkable to someone not looking for Cloudflare-specific markers) or a pre-fix
`AdNetworkDeadEndError`-shaped dead end (also same domain). Both explanations remain on the table;
this addendum's `LLIsBlocked`-branch finding stands regardless of which one actually happened, since
it's a genuine gap either way.

## Addendum: `LLIsBlocked` was a red herring - the real script, and the real wall, recovered live (2026-07-24)

Follow-up to the two addenda above, triggered by a third live report ("I clicked the link you
gave, I have to do the clicking thing again... no point of developing this at all") and a
direct instruction to stop treating `--manual` as an acceptable answer and instead find out
exactly how `LLIsBlocked` gets set to true and neutralize it.

This session did what neither prior addendum did: loaded real, current `?ht=...` gate URLs
with headless Playwright from this VM and read the actual `<script>` contents, rather than
reasoning from the partial fragment quoted in the earlier addenda. Both a fresh `pahe.ink`
page fetch (via `parser.py`, plain HTTP - unaffected by anything below) and the `teknoasian.com`
gate loads worked cleanly from this VM this session: Cloudflare's front door passed silently
(`GET /?ht=...` → `200`, full page + script returned), exactly as `playwright-feasibility.md`
originally found.

### What `LLIsBlocked` actually is, verbatim, as of 2026-07-24

Recovered identically across two independent, freshly-parsed `ht` tokens (different releases/
resolutions, same underlying template):

```js
var LLPayload = '...(base64-looking blob)...'
var LLIsBlocked = false;
var LLBlockTime = 4
...
var ADS_URL = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js';

function checkAdsBlocked(callback) {
    var xhr = new XMLHttpRequest();
    xhr.onreadystatechange = function () {
        if (xhr.readyState == XMLHttpRequest.DONE) {
            callback(xhr.status === 0 || xhr.responseURL !== ADS_URL);
        }
    };
    xhr.open('HEAD', ADS_URL, true);
    xhr.send(null);
}
if(false) {
    checkAdsBlocked(function(adsBlocked) {
        LLIsBlocked = adsBlocked;
    });
}
```

So the detection mechanism, as hypothesized in the previous addendum, genuinely is a classic
bait-request technique - `HEAD` a well-known ad-serving URL (`adsbygoogle.js`) and treat a
failed/redirected response as "blocked". **But the call site that would ever invoke it is
wrapped in `if(false) { ... }`** - dead, unreachable code. `LLIsBlocked` is declared `false`
and nothing on the page ever reassigns it before the `.postnext` click handler reads it. The
only two other assignments in the whole script are `LLIsBlocked = false;` inside the
`.postnext` click handler's own `if (LLIsBlocked)` branch (a self-resetting guard for a branch
that can now never be entered). **Conclusion: `LLIsBlocked` cannot evaluate `true` today, from
any network, any ad blocker, any VPN - the site has shipped this check disabled.** This holds
for both tokens tested and is presumably a global template setting (`if(false)` is static
source, not conditioned on anything request-specific), not a per-token or per-IP variation.

This also resolves an inconsistency the previous addendum couldn't: the `.postnext` click
handler in the live script is:

```js
document.querySelector('.postnext').addEventListener('click', () => {
    if (LLIsBlocked) {
        LLIsBlocked = false;
        /* show "Ad blocker detected" message, wait LLBlockTime seconds, re-show button */
    } else {
        if (submitRedirect) {
            window.open(submitRedirect, "_blank")
        }
        xxc.submit();
    }
});
```

`xxc.submit()` is **not** gated on `window.open()`'s return value at all - unlike the
`if (!w) location.href = adUrl`-shaped pattern the first addendum (and `WINDOW_OPEN_SHIM_JS`)
assumed. `window.open(submitRedirect, "_blank")` is called and its result is simply discarded;
`xxc.submit()` runs unconditionally right after. `WINDOW_OPEN_SHIM_JS` is harmless to keep (it
costs nothing and may matter for a template variant that does use that pattern - teknoasian's
gate script has changed at least twice before per `prior-art-and-alternatives.md`), but it is
not doing anything load-bearing against the *current* script, and no init-script countermeasure
against `LLIsBlocked` was written, because there is nothing live to counter - writing one would
be pure dead-code theater against a check the site itself already disabled.

### So what actually stops the automated chain? Reproduced live, 4/4, regardless of technique

With `LLIsBlocked` ruled out, the click-chain was driven for real against three different fresh
tokens, two different ways:

1. **Full click-chain** (`.humanVerify` → wait/skip → `.postnext`), including a variant with
   deliberate human-like mouse movement to each button (`page.mouse.move(..., steps=10-12)`,
   randomized 0.3-1.0s pauses before each click, matching or exceeding the site's own ~9s
   countdown dwell time) - **2/2 tokens**: the `.postnext` click's resulting page (same-origin
   POST, no `action` attribute so it targets the current URL) came back as Cloudflare's
   `Just a moment...` interstitial - HTML title `Just a moment...`, a
   `challenges.cloudflare.com` CSP `frame-src`/`connect-src` entry, no `#xxc`, no
   `.humanVerify`, no `mega.nz` anywhere in the response. Identical outcome with and without
   the human-like mouse movement/timing.
2. **Same-session `fetch()` calls** issued via `page.evaluate()` from the already-loaded,
   already-Cloudflare-cleared gate page (same cookies, same origin, no DOM interaction at all)
   - **1/1 POST** (replicating the `#xxc` form's own `hw=<LLPayload>` body) and **1/1 plain
   GET** (no body, just re-requesting the exact same URL that had just loaded fine) - both
   came back `403`, HTML title `Just a moment...`, same `challenges.cloudflare.com` CSP.

**4 for 4.** Every single follow-up request to `teknoasian.com` in a session - POST or GET,
via a real click-driven navigation or via `fetch()`, with or without human-like interaction
timing - got the same Cloudflare Managed Challenge the *first* request in the session never
did. This rules out click-trustedness, request method, DOM-vs-fetch, and interaction timing as
the variable; the only thing that changed between "request 1: passes" and "request 2+: hard
403 challenge" is that it's a second request in the same session, from the same IP. That is a
textbook signature of IP-reputation-driven Cloudflare Bot Management stepping up enforcement
mid-session, not a per-request JS-level check.

This is, concretely, the exact same wall this document's own headline section already
catalogued as **empirically tested and unsolved from this VM's IP** (patchright, nodriver, and
camoufox all included) - "Cloudflare Terminal-Challenge Bypass Investigation (Part 5)" at the
top of this file. The `LLIsBlocked` theory in the two addenda above was a plausible-sounding
but, per this session's live evidence, incorrect explanation for the same underlying symptom;
the real cause was the already-documented terminal Managed Challenge the whole time.

### What this means for the tool, concretely

- **No JS countermeasure was added for `LLIsBlocked`**, because there is nothing live to
  counter. `resolver.py`'s `AdNetworkDeadEndError` docstring and this repo's `README.md` have
  been updated to state this as a confirmed finding, not a hedge, so a future session doesn't
  re-chase this same lead.
- `resolver.py`'s existing classification logic (`_is_cloudflare_challenge()`,
  `blocked_early`/`is_cf` in `resolve_gate_url()`) already correctly identifies this exact
  failure mode as a genuine Cloudflare challenge, not an ad-network dead end - confirmed
  directly this session (the "Just a moment..." title and `challenges.cloudflare.com` iframe
  checks matched every reproduction above). No bug was found in that classification.
- The headed-browser fallback could not be exercised end-to-end in this VM (`no X server or
  $DISPLAY` - this VM has no display at all, a separate and expected limitation of the sandbox,
  not of the code), so the *"human clears the visible challenge, tool auto-captures the mega.nz
  link"* half of the flow was verified only by code inspection this session, not by an actual
  human clearing a real challenge window.
- **This is genuinely not fixable from this VM by changing `resolver.py`.** Per the "IP
  reputation" section at the top of this document, this VM's outbound IP is a Hetzner
  dedicated-server address, a class of IP Cloudflare treats with materially more suspicion than
  a residential connection. The recommendation stands and is now further corroborated with
  fresh, tightly-controlled evidence gathered specifically for this session: **re-test from the
  user's actual machine/network (e.g. their Windows desktop) before concluding the automation
  itself is broken.** If a residential run still hits the same wall, that would be the trigger
  to revisit the paid CAPTCHA-solving option this document already priced out, or to explore
  session/IP-persistence strategies not yet tried - not to add more JS shims, since the
  evidence here shows the obstacle is not JS-level at all.

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
