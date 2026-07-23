# Research Summary — Auto Pahe Media Downloader

This folder documents investigation only; no implementation code exists yet. See
`site-structure.md` (Part 1) and `mega-link-redirect-flow.md` (Part 2) for full detail.

## Part 1 — pahe.ink page structure: mostly solved

- pahe.ink is a plain server-rendered WordPress site. A simple `requests` + BeautifulSoup GET
  is enough to read the download-links section — no JS/headless browser needed for Part 1.
- Two different layout patterns were confirmed on real pages:
  - **Batch releases** (e.g. the user's Game of Thrones S8 example): tabs = resolution,
    inner groups = "Per Episode" vs "Batch".
  - **Ongoing/weekly releases** (e.g. Parish S1): tabs = episode number, inner groups =
    resolution/quality variant.
- **No final host URL (mega.nz or otherwise) ever appears on the pahe.ink page.** Every
  provider button (MEGA, Google Drive, Putdrive, etc.) links to the same third-party gate
  domain, `teknoasian.com/?ht=<opaque token>`. The only way to identify "this is the MEGA
  button" is the anchor's **visible text** (`MG`, `MG 1`, ...) — not the href, not the CSS
  class/color (color-to-provider mapping was shown to be unstable across pages).
- A parsing plan (BeautifulSoup selectors + small state machine over tab/pane children) is
  written up plan-level in `site-structure.md`.

## Part 2 — MEGA redirect chain: blocked after hop 1, needs a browser

- Hop 0 (pahe.ink → gate URL) is understood (see above).
- Hop 1 (the `teknoasian.com` gate itself) is **behind a Cloudflare Managed Challenge**
  ("Just a moment..." interstitial, HTTP 403 to any non-browser client). This was confirmed
  with both `curl` and the `WebFetch` tool — both got blocked.
- No headless browser (Playwright/Selenium) was available in this investigation
  environment, so **hops beyond the Cloudflare gate are unverified** — only general,
  explicitly-flagged-as-unconfirmed background knowledge about this class of link-gate site
  is offered as a starting hypothesis.
- Conclusion: Part 2 very likely requires a real/headless browser (Playwright recommended)
  at least to clear the Cloudflare hop, with a hard timeout and a strict domain allowlist so
  the automation never wanders into ads/unrelated redirects. Whether the rest of the chain
  can be cheaply replicated via plain HTTP after that (e.g. by reusing a Cloudflare
  clearance cookie) is unknown and needs a follow-up session with browser tooling available.

## Open questions for the user before implementation starts

1. **Environment**: is it acceptable to install/use a headless browser (Playwright +
   Chromium) for this project? Any preference on Playwright vs. an alternative?
2. **Cloudflare risk tolerance**: if the Cloudflare challenge sometimes escalates to an
   interactive Turnstile/CAPTCHA (common for datacenter IPs or flagged fingerprints), are
   you open to a paid CAPTCHA-solving service, or should the tool simply fail loudly and let
   you solve it manually in a real browser when that happens?
3. **MEGA account**: do you have a MEGA account/API credentials? Not needed to get the link,
   but relevant if a later phase should also download or verify the MEGA file
   programmatically (MEGA has its own API/`mega.py` etc. — out of scope for what's been
   researched so far).
4. **Stability of the redirect chain**: does it change per link/session, or is it stable
   long enough to hardcode hop logic? Unknown — needs to be checked once browser tooling is
   available, ideally across several different `ht` tokens/providers/pages.
5. **"Per Episode" MEGA link on batch pages**: is it in practice a single MEGA folder with
   all episodes, or something else? Confirming this affects how the CLI should present that
   choice to the user (see `docs/planning/cli-ux-notes.md`).
6. **Provider abbreviation coverage**: `SD` (seen on the Parish example) is unidentified.
   Worth confirming there isn't a similarly-labeled host that should be excluded/could be
   confused with MEGA in edge cases (current filter regex `^MG(?:\s*\d+)?$` seems safe, but
   worth double-checking against a wider sample of pages).
7. **Rate limiting / ToS**: no `Crawl-delay` or page-level disallow was found in
   `robots.txt`, but no attempt was made to hammer the site — recommend the eventual tool
   be conservative (single request per invocation, normal browser UA, no concurrency) both
   out of courtesy and to avoid tripping Cloudflare on the pahe.ink side too.
