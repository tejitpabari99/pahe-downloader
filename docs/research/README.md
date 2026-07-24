# Research Summary — Auto Pahe Media Downloader

This folder documents investigation only; no implementation code exists yet. See
`site-structure.md` (Part 1) and `mega-link-redirect-flow.md` (Part 2) for full detail. Also see
`prior-art-and-alternatives.md` (Part 3), `playwright-feasibility.md` (Part 4), and
`cloudflare-bypass-investigation.md` (Part 5, "is there any way past the terminal Cloudflare
challenge without a human" — verdict: no, from this sandbox's datacenter IP; ship the
automated-up-to-the-block + manual-fallback design).

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

## Open questions — resolved by user (2026-07-23)

1. **Environment**: **resolved.** A headless browser (Playwright + Chromium) is acceptable
   for clearing the Cloudflare hop. No alternative was requested.
2. **Cloudflare risk tolerance**: still open — not addressed by the user yet. If the
   challenge escalates to an interactive Turnstile/CAPTCHA, whether to use a paid
   solving service vs. failing loudly for manual resolution remains an open call to make
   once real browser tracing surfaces whether this actually happens.
3. **MEGA account**: **resolved.** The user has an existing MEGA.nz account. It is **not**
   needed to resolve/view the final mega.nz link — that works anonymously — but it's
   available in case a later phase needs authenticated MEGA access (e.g. the MEGA API/
   `mega.py`), which remains out of scope for now.
4. **Stability of the redirect chain**: **resolved (belief, not yet proven).** The user
   believes the teknoasian.com redirect chain is *likely stable* across different tokens/
   links, but isn't fully certain. This still requires empirical verification — the
   recommended check is tracing 2-3 different pahe.ink download links (different pages/
   providers/tokens) once browser tooling is available and confirming the hop structure/
   mechanism is identical and only the `ht` token differs.
5. **"Per Episode" MEGA link on batch pages**: **resolved.** On batch/season pages,
   "Per Episode" MEGA entries are individual per-episode file links, while the season-wide
   "Batch" MEGA entry is a MEGA **folder** link containing all episodes. Both are valid
   resolution targets — the tool should resolve whichever entry the user picks and return
   whatever final `mega.nz` URL results (file or folder), without trying to distinguish or
   validate which kind it got.
6. **Provider abbreviation coverage**: **resolved.** The unidentified `SD` provider is
   out of scope and can be ignored/skipped entirely — no further identification needed.
7. **Rate limiting / ToS**: still open/unaddressed by the user — recommendation stands as
   written: the eventual tool should be conservative (single request per invocation,
   normal browser UA, no concurrency) both out of courtesy and to avoid tripping Cloudflare
   on the pahe.ink side too.
8. **Provider scope confirmation**: **resolved.** Build and validate the MEGA path
   end-to-end first. Other providers (GD, PD, VF, 1F) are deferred, presumed to follow the
   same teknoasian.com gate pattern, and will be tackled only after MEGA works.
9. **Product constraint — no media downloads (new, from user)**: **resolved.** The tool's
   job ends at producing the final `mega.nz` URL as text output. It must **never** download
   the actual media file content and should avoid triggering/consuming a MEGA download
   quota. Resolving the link and/or a `HEAD`-style validity check is fine; a `GET` of the
   actual file bytes is not. This applies to every phase of the project, not just MEGA.
