# Prior Art & Alternatives Research (Part 3)

Status: search-engine + third-party-repo research only. No live requests were made to
pahe.ink or teknoasian.com in this session (per constraint) — everything below comes from
GitHub/Codeberg/Greasy Fork/Reddit content read via `WebSearch`, `WebFetch`, and `gh api`/
`gh search code`.

## Direct answer: **Partial**

There is no ready-to-import open-source library that resolves a pahe.ink "MG" button all
the way to a working `mega.nz` URL *today*. But the prior art is unusually good for a niche
target: multiple independent, actively-maintained projects have already reverse-engineered
**the exact `teknoasian.com` gate** (not just "a similar gate") down to concrete request/
response shapes. What's still unsolved/unverified by anyone publicly:

- **Getting past teknoasian.com's Cloudflare Managed Challenge from a script.** Every
  project found either (a) predates Cloudflare being added to teknoasian.com and is now
  broken/disabled for that domain, or (b) runs as a **browser extension inside a real,
  already-logged-in Chrome tab**, i.e. it never has to solve Cloudflare itself — it inherits
  a session that a real browser already passed silently. No project demonstrates clearing
  the challenge from a cold, non-interactive context (which is exactly our situation with
  Playwright).
- Whether the same `hq`/`hw`/`xxc` token chain (see below) still terminates at `mega.nz`
  specifically for MEGA buttons, vs. some other provider — none of the found projects
  filter by destination host; they just follow the chain to whatever `id="xxc"` anchor
  resolves to.

What **is** already solved and directly reusable as a blueprint (not as drop-in code, see
licensing column) is what happens **after** Cloudflare: the ad-gate itself is a known,
named template ("SoraLink" / what one very recent project calls the "LL Safelink" chain)
running on `teknoasian.com`, `linegee.net`, `intercelestial.com`, and others, and its
hop-by-hop mechanics have been reverse-engineered down to specific POST bodies and regexes
by at least three independent authors.

## Evidence

### The `teknoasian.com` gate is a known, named ad-gate template — not bespoke

| Finding | Detail |
|---|---|
| Domain is a recognized "shortlink"/ad-gate target across many independent bypass tools | `teknoasian.com` (and sibling domains `linegee.net`, `intercelestial.com`) appear by name in `supported_sites.txt` lists, `@match` rules, and uBlock filters across 15+ unrelated GitHub repos found via `gh search code teknoasian` (e.g. `Amm0ni4/bypass-all-shortlinks-debloated`, `rushiranpise/userscripts`, `suryadeeprampur/Bypass-bot-1`, `Ishatgrepo/bypass`, `Tenith01/safe-jump`, `nOneCode4u/bypass-shortlinks`, AdGuard's own filter lists). |
| Gate widget IDs are consistent across sites/authors | `#soralink-human-verif-main` → `#generater` → `#showlink` (older, click-based flow) and, more recently, form fields named `hq`/`hw` and a final `<a id="xxc" href="...">` (newer, fetch-based flow) — the *same* element/param names recur verbatim across unrelated repos, confirming this is one commodity gate template ("SoraLink"), not something teknoasian.com built themselves. |
| Cloudflare was added to teknoasian.com relatively recently, breaking older bypasses | `hamngku/PaheinBypass` (JS/Puppeteer) has a `teknoasian.com` branch **explicitly commented out** with the note *"Maybe PAHE no longer uses the teknoasian.com domain for download links"* — the old flow (click two images: `ok-lets-continue.png`, `download.png`) no longer works. Codeberg issues on `Amm0ni4/bypass-all-shortlinks-debloated` show the same arc: issue #14 (Cloudflare-era jQuery click-override workaround), issue #246 (Feb 2025, feature marked "not supported"), issue #351 (Jul 2025, "Bypassed" notice fires but the countdown still runs — i.e. still broken). Reddit (`r/Piracy`, Feb 2025 and Sep 2025 threads) shows *ordinary human users*, not just bots, hitting new friction specifically on Teknoasian links — consistent with a hardened/Cloudflare-fronted gate rather than a bot-only block. |
| The post-Cloudflare hop chain has been reverse-engineered as plain HTTP, at least twice | `Ishatgrepo/bypass/extra_bypasses/pahe_soractrl.user.js` (Jan 2025) neutralizes the `event.isTrusted` check SoraLink uses to detect real clicks, letting a userscript fire the `#soralink-human-verif-main` → `#generater` → `#showlink` handlers itself. Far more usefully, `sharoon7171/skip-wait-bypass-timers-countdowns-extension` — **pushed 2 days before this research (2026-07-21)**, live on the Chrome Web Store — has a dedicated `src/sites/ll-safelink/hq-chain.ts` module (commit message: *"move teknoasian hq chain to ... fetch-only ht bypass"*) that resolves a `?ht=` URL (the exact same query param pahe.ink uses!) **purely with `fetch()`/POST, no clicking, no DOM waiting**: extract `hq` token → `POST /` with `{hq}` → regex out an `LLPayload`/`hw` value → `POST /` with `{hw}` → regex out an `action=` URL + new `hq` → `POST` that URL → regex out `hw` again → final `POST` → regex an `<a id="xxc" href="...">` out of the response, which is the resolved destination. |

### Pahe-specific projects (site-structure parsing + bypass attempts)

| Project | What it does | Fits pahe.ink + teknoasian.com? | Avoids a real browser? | Freshness | License |
|---|---|---|---|---|---|
| [`hamngku/PaheinBypass`](https://github.com/hamngku/PaheinBypass) | Node/Puppeteer tool that parses pahe.in/ph/li/ink pages and drives a real Chrome via Puppeteer to click through each host's gate | Yes for domain coverage, but its `teknoasian.com` branch is dead/disabled (see above) — only `intercelestial.com` and `linegee.net` branches are live | **No** — uses `puppeteer.launch()` against a real installed Chrome | Last commit 2024-03-24 (stale) | GPL-3.0-or-later (copyleft — architecture is fine to learn from, code reuse would require our project to also be GPL) |
| [`Ishatgrepo/bypass`](https://github.com/Ishatgrepo/bypass) (`pahe_soractrl.user.js`) | Tampermonkey userscript targeting `teknoasian.com`/`linegee.net` specifically; defeats the `isTrusted` click check | Yes, exact domain match | No — runs inside a real browser tab as a userscript | Jan 2025 | None declared |
| [`sharoon7171/skip-wait-bypass-timers-countdowns-extension`](https://github.com/sharoon7171/skip-wait-bypass-timers-countdowns-extension) | Chrome extension, live on the Web Store; `hq-chain.ts` does a fetch-only POST chain for `teknoasian.com`'s `?ht=` links | Yes, exact domain + exact query param (`ht`) match | **Partially** — the token-chain itself is plain `fetch()`, but it executes inside an extension content-script context in a real Chrome tab that already holds Cloudflare's session cookie; it does not independently solve the Cloudflare challenge | **Very fresh** — pushed 2026-07-21, actively developed (commits as recent as this week) | None declared |
| [`Amm0ni4/bypass-all-shortlinks-debloated`](https://codeberg.org/Amm0ni4/bypass-all-shortlinks-debloated) | General-purpose Violentmonkey shortlink-bypass script; `teknoasian.com` is one of 100+ supported domains | Domain match, but currently non-functional for this domain per its own issue tracker | No — browser userscript | Last commit 2025-06-23; teknoasian-specific support marked broken Feb–Jul 2025 | "Missing license" (Codeberg-flagged — no OSI/FSF license found) |
| [`roofman2008/Pahe.ph-Scraper`](https://github.com/roofman2008/Pahe.ph-Scraper) | .NET/C# scraper for pahe.ph, bypasses Sucuri WAF and an intermediate service it calls "SoraLink" | Same *family* (SoraLink template, same site network) but targets pahe.ph, not confirmed against `teknoasian.com`'s current Cloudflare layer (its own TODO lists Cloudflare bypass as "Not Needed Now", i.e. wasn't an issue for its target at the time) | Unclear — no evidence of headless browser use, but also predates Cloudflare on this gate | Last commit 2023-02-20 (stale, C#/.NET) | MIT (permissive) |
| [`HassanBuTt78/Pahe-scrapper`](https://github.com/HassanBuTt78/Pahe-scrapper) | JS scraper described as "skipping all ad walls" for pahe.in | Unconfirmed — no README detail on which gate/mechanism; low signal | Unknown | Last commit 2023-10-21, 0 stars | None declared |
| [`lazuardyk/pahe`](https://github.com/lazuardyk/pahe) | Early (2018) Python link grabber | No — predates `teknoasian.com` gate entirely | N/A | 2018, dead | None declared |
| [`ayushjaipuriyar/animepahe-dl`](https://github.com/ayushjaipuriyar/animepahe-dl) | Actively maintained (pushed 2026-05-16), full-featured `animepahe.ru` downloader, PyPI package, MIT | **No** — animepahe uses its own `kwik.si`/m3u8-stream-based distribution, not the `teknoasian.com`/MEGA-gate flow used by pahe.ink's movie/TV downloads. The "sibling site shares infra" hypothesis from the task brief was **not confirmed** — animepahe's download path appears to be architecturally distinct | N/A (different problem) | Very fresh | MIT |
| [`IsNoobgrammer/AnimePahe-dl_extractor`](https://github.com/IsNoobgrammer/AnimePahe-dl_extractor) | Older animepahe.ru scraper; explicitly "no longer maintained", superseded by `AnimeDownloader` | Same caveat as above — animepahe-specific flow, not pahe.ink's gate | N/A | 2023, archived-in-spirit | Apache-2.0 |

### Hosted "just paste your link" bypass services (unverified, use with caution)

- `pahebypasser.heartontarget.com` — advertised as a live web front-end for `PaheinBypass`
  (same author/repo). Not tested in this session (would mean sending a real, presumably
  live `ht` token to an unknown third-party server — out of scope for this pure
  desk-research pass, and a genuine trust/privacy question if ever used for real).
- `pahebypass.koyeb.app` — mentioned in passing in Codeberg issue #246 as an alternative
  bypass endpoint; also unverified, and the issue thread itself notes it may be offline.

Neither is source-inspectable from where they're linked (no repo attached), so neither
counts as "open source" prior art — flagging only because they exist and a user might
otherwise stumble on them as a shortcut. Recommend treating both as unverified/opaque
third-party services, not as something to build on.

## What this changes about our own findings

This does **not** overturn `mega-link-redirect-flow.md`'s core conclusion — a real/headless
browser is still needed at least for the Cloudflare hop, no project anywhere avoids that for
a cold/non-interactive client. But it substantially de-risks "hops 2+ (unverified)":

- The vague "countdown timer, then maybe another shortener, then maybe a signed token"
  guess in our own doc can now be replaced with a concrete, testable hypothesis: teknoasian's
  post-Cloudflare flow is a **`hq` → `hw` (`LLPayload`) → `xxc`** POST-chain (per
  `sharoon7171`'s July 2026 code), not an arbitrary number of unknown hops.
- It's plausible (not yet proven — needs a live trace) that once Playwright's browser
  context has cleared the Cloudflare Managed Challenge and holds a valid clearance cookie,
  the rest of the chain can be done via cheap `fetch()`/`page.evaluate()` calls inside that
  same page context — or even handed off to a plain `requests`/`httpx` session carrying the
  cookie jar — rather than needing full DOM navigation/clicking for every hop. This matches
  (and is now evidenced, not just guessed) the "reuse the clearance cookie for subsequent
  hops" idea already flagged as an open item in `mega-link-redirect-flow.md`.
- No license anywhere in this space is clean enough to freely fork/vendor: the two most
  relevant hits are GPL-3.0 (`PaheinBypass` — copyleft) and unlicensed ("missing license" —
  `bypass-all-shortlinks-debloated`, `Ishatgrepo/bypass`, `sharoon7171`'s extension). None of
  these forbid *reading* the code to reimplement the same idea independently (which is what
  this document does), but none should be copy-pasted into our codebase without separately
  resolving licensing, and the two "no license" projects technically reserve all rights by
  default.

## Recommendation

**(b) Proceed to build a custom Playwright-based solution** — no ready-made project can be
adopted wholesale — but narrow the scope of what Playwright needs to do, informed by the
above:

1. Use Playwright (Chromium, with stealth/anti-detection patches) only to load the
   `teknoasian.com/?ht=...` gate URL and get past the Cloudflare Managed Challenge. Budget
   for this being the single riskiest/most fragile step (per our own prior finding and the
   Feb/Sep 2025 Reddit reports of the challenge tightening over time).
2. Once loaded, look for exactly the shape `sharoon7171`'s `hq-chain.ts` describes: an `hq`
   token (in a hidden form field or embedded in page HTML), a `var LLPayload = '...'`
   assignment, a follow-up form `action=` URL, and eventually an anchor `<a id="xxc"
   href="...">` — verify this structure empirically against 2–3 real `ht` tokens (this also
   directly answers the user's open Q4 about chain stability from the earlier README update).
   Prefer driving this chain via `page.evaluate()`-issued `fetch()` calls inside the already-
   authenticated Playwright page (simplest, automatically carries cookies/headers correctly)
   over a separate plain-HTTP client, at least for a first working version.
3. If the `xxc` anchor's resolved target is not itself `mega.nz` but another redirector, keep
   following with the same domain-allowlist/timeout discipline already documented in
   `mega-link-redirect-flow.md`, stopping the moment a `mega.nz` URL is reached and never
   issuing a `GET` for anything beyond that (per the no-file-download constraint recorded in
   `docs/research/README.md`).
4. Treat this whole chain as a moving target the way every project surveyed here has had to:
   `teknoasian.com`'s gate logic already changed at least twice in the last ~18 months
   (image-click era → SoraLink DOM-click era → current `hq`/`hw`/`xxc` fetch era). Design the
   resolver as an isolated, easily-replaceable module (already the plan per
   `docs/planning/cli-ux-notes.md`'s `resolve_gate_url()` boundary) so a future break is a
   contained fix, not a rewrite.

Sources consulted (representative, not exhaustive): GitHub repos and code search results for
`hamngku/PaheinBypass`, `Ishatgrepo/bypass`, `sharoon7171/skip-wait-bypass-timers-countdowns-extension`,
`roofman2008/Pahe.ph-Scraper`, `HassanBuTt78/Pahe-scrapper`, `lazuardyk/pahe`,
`ayushjaipuriyar/animepahe-dl`, `IsNoobgrammer/AnimePahe-dl_extractor`; Codeberg issues #14,
#246, #351 on `Amm0ni4/bypass-all-shortlinks-debloated`; Greasy Fork listings for "Bypass Pahe
Links" and "Bypass All Shortlinks"; `r/Piracy` Reddit threads (Feb 2025, Sep 2025) referencing
Pahe/Teknoasian breakage.
