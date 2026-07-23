# MEGA Link Redirect Flow Research (Part 2)

Status: **partially verified — blocked at hop 1**. All tracing was done read-only (`curl`
with a browser User-Agent, and the `WebFetch` tool), one hop at a time, inspecting only
status codes / response headers / raw HTML of the specific link that pahe.ink itself
presents as the "MG" (Mega) button. No ads, popups, or unrelated on-page links were fetched
or clicked at any point.

## Hop 0 — pahe.ink page → gate URL

Confirmed (see `site-structure.md`). Every provider button on pahe.ink, regardless of host
(MEGA, Google Drive, Putdrive, ...), points to the same third-party domain:

```
https://teknoasian.com/?ht=<url-escaped base64-looking token, unique per button>
```

This is hop 0 → hop 1. There is nothing to decode locally; the token is opaque and must be
resolved by the gate server itself.

## Hop 1 — teknoasian.com gate: BLOCKED by Cloudflare bot-challenge

Requesting the gate URL directly (no browser, no JS execution):

```
$ curl -sD - -o /dev/null -A "<normal desktop Chrome UA>" \
    "https://teknoasian.com/?ht=<token>"

HTTP/2 403
cf-mitigated: challenge
content-security-policy: ... script-src 'nonce-...' 'unsafe-eval' https://challenges.cloudflare.com ...
server: cloudflare
x-robots-tag: noindex,nofollow
```

Response body title: `Just a moment...` — this is Cloudflare's standard **Managed
Challenge** interstitial (the "checking your browser" JS-challenge page, backed by
`challenges.cloudflare.com`, i.e. Cloudflare Turnstile). The same result was obtained with
the `WebFetch` tool (`HTTP 403`, no body retrievable).

**This means the very first hop past pahe.ink is already behind a real anti-bot check that
requires executing JavaScript in an environment Cloudflare is willing to trust** (valid
TLS/JA3 fingerprint, JS challenge execution, and possibly a short wait or an interactive
Turnstile widget). A plain HTTP client (`requests`/`httpx`/`curl`) cannot get past this
without either:
- driving a real (or well-disguised headless) browser that can execute the Cloudflare JS
  challenge, or
- an external CAPTCHA/Cloudflare-solving service, or
- a "Cloudflare bypass" library that reimplements the JS challenge/TLS fingerprinting
  (e.g. the class of tools like `cloudscraper`/`curl_cffi`) — these are explicitly a
  cat-and-mouse game with Cloudflare and can break at any time; none were available/tested
  in this sandboxed environment (no network install attempted, per "investigation only").

No headless browser (Playwright/Puppeteer/Selenium) was installed or available in this
environment, so **hops 2+ (whatever lies between the Cloudflare-gated teknoasian.com page
and the final mega.nz URL) could not be observed or verified in this session.** This is a
hard stop, not a guess — do not treat anything below "Hops 2+ (unverified)" as confirmed.

## Hops 2+ (unverified — pattern-matching from general knowledge, NOT observed this session)

pahe.in/pahe.ink-style link gates in general (as a *class* of site, not specifically
verified for teknoasian.com in this session) commonly implement one or more of:
- A countdown-timer page ("please wait N seconds") that reveals a "Get Link" /
  "Continue" button via `setTimeout` + DOM manipulation, sometimes gated further behind ad
  interaction requirements.
- A second intermediate domain (often a generic "link shortener/locker" service, sometimes
  ad-monetized) before finally issuing an HTTP redirect or a rendered link to
  `mega.nz/...`.
- A short-lived signed token passed forward hop-to-hop via query string.

**This paragraph is explicitly flagged as inference/background knowledge about this class
of site, not a verified finding** — it should not be relied upon for implementation without
first re-tracing the chain with a real (headless) browser, hop by hop, exactly as the
safety-conscious methodology below describes.

## Safety guardrails observed while tracing (for future automation)

- The teknoasian.com challenge page itself is Cloudflare's own official interstitial, not a
  third-party ad — nothing on this specific hop looked like an ad-injection or malicious
  redirect. It simply could not be passed non-interactively.
- General guidance for whoever continues this trace with a browser: any link/button whose
  destination domain is not part of the obvious pahe → (gate) → mega.nz path, or that opens
  a new tab/window unexpectedly, or that is an `<iframe>` (often ad content) should be
  treated as a decoy and never clicked. Only the element that is unambiguously the
  "continue/get link" affordance (by matching the page's own countdown/JS logic, not by
  visual position) should be followed.
- Never let a driver script execute a countdown page longer than a short, fixed timeout, and
  never download any file that isn't the expected final `https://mega.nz/...` URL string.

## Scriptability assessment

| Question | Answer |
|---|---|
| Can Part 2 be done with plain HTTP requests (requests/httpx) only? | **No, not as currently observed.** Hop 1 alone requires passing a Cloudflare Managed Challenge, which is a JS-executing, browser-fingerprint-checking gate. |
| Is a headless browser required? | **Very likely yes**, at minimum for the teknoasian.com hop. Recommend Playwright (Chromium), which has better anti-detection ergonomics than Selenium out of the box, run non-headless or with stealth patches if plain headless gets challenged further (Cloudflare frequently treats headless-flagged browsers more aggressively). |
| Is this reliably scriptable at all? | **Uncertain / at risk.** Cloudflare's managed challenge can escalate to an interactive Turnstile checkbox or a full CAPTCHA for automated-looking traffic (headless browsers, datacenter IPs, unusual TLS fingerprints), in which case no fully automated solution is safe/reliable without a paid solving service — which raises its own cost/ethics/ToS questions the user should weigh in on. |

## Recommendation

1. Re-attempt this trace with Playwright (or similar) in a real desktop-Chromium profile,
   one hop at a time, with:
   - A hard navigation timeout per hop (e.g. 15–20s) so a stuck challenge/ads page can't hang
     the tool.
   - A domain allowlist limited to the exact chain discovered (pahe.ink → teknoasian.com →
     ... → mega.nz) — any navigation attempt (e.g. via `page.on("popup")`, a new tab, or a
     redirect) to a domain outside that allowlist should be aborted, not followed.
   - No auto-clicking of anything except an element identified as the legitimate
     "continue/get link" control (verified against the page's own JS, e.g. by reading the
     `onclick`/timer logic rather than guessing from CSS class/visual styling — the pahe.ink
     page itself showed that visual styling (`class="shortc-button ... red"`) is not a
     reliable semantic signal, and there's no reason to assume the gate page's ad buttons
     will be any more honestly labeled).
2. If Cloudflare consistently escalates to an interactive Turnstile/CAPTCHA for this
   environment's IP/fingerprint, plain automation is not viable long-term without a
   commercial solving service; surface that tradeoff to the user rather than silently
   building something fragile.
3. Whatever mechanism is found at hops 2+, prefer the cheapest reliable option: if a hop
   turns out to be a plain HTTP redirect or meta-refresh once past Cloudflare, that
   particular hop can be replicated with `requests` afterward — a headless browser may only
   be strictly necessary for the Cloudflare-gated hop(s), with the rest of the chain
   followed cheaply via HTTP once a valid Cloudflare "clearance" cookie is obtained from the
   browser session (needs verification: whether that cookie/session can be handed off to a
   plain HTTP client for subsequent hops, or whether every hop is separately protected).

## Open items requiring a follow-up session with a real browser available

- What actually happens after passing the Cloudflare challenge — countdown page, direct
  redirect, form POST, etc.
- Whether the chain is stable across different `ht` tokens/providers/pages, or varies.
- Whether a Cloudflare clearance cookie can be reused across hops/requests to minimize
  headless-browser usage.
