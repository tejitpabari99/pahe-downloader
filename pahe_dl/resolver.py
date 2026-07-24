"""Resolves a teknoasian.com `?ht=` gate URL down to a final mega.nz URL.

Implements the boundary agreed in docs/planning/cli-ux-notes.md:

    resolve_gate_url(gate_url: str) -> str

Chain (see docs/research/scratch/teknoasian-chain-spike.py for the validated
reference this is based on, and docs/research/playwright-feasibility.md for
the full findings this design follows):

  1. Load the `?ht=...` gate URL. Cloudflare's front door passes an ordinary
     Playwright Chromium session silently (confirmed in research) - no
     interstitial appears here.
  2. Click ".humanVerify button.verify" ("Click To Verify").
  3. Wait out the JS countdown; a "Continue"/"Get Link" button (".postnext")
     appears, possibly via an intermediate ".Skipper button.skipcontent"
     stage on some page states.
  4. Click ".postnext". This simultaneously fires an unrelated ad-monetization
     popup (intercepted and closed immediately, never navigated) and submits
     a same-page form (`#xxc`) whose response is the terminal step.
  5. The terminal response is one of:
       (a) the resolved page/content containing a mega.nz URL - success, or
       (b) a genuine Cloudflare Managed Challenge (403 / `cf-mitigated:
           challenge` / "Just a moment..." title) - the known, reproducible
           block documented in playwright-feasibility.md, or
       (c) an ad-network dead end: instead of (a) or (b), the tab is
           diverted to unrelated content (e.g. a random teknoasian.com blog
           article) with no mega.nz URL and no Cloudflare markers either.
           This happens when the ad popup at step 4 is blocked and the
           site's own script falls back to hijacking the *same* tab instead
           - see docs/research/cloudflare-bypass-investigation.md and
           AdNetworkDeadEndError. `_install_window_open_shim()` prevents
           most instances of this; `_looks_like_ad_dead_end()` catches
           whatever slips through so it's reported accurately (there is
           nothing to click through on a page like this, unlike (b)).

Hybrid fallback (the key UX requirement): on (b), do NOT ask the user to
start over in a separate browser. Instead, carry the already-established
session (cookies) and the exact blocked URL over into a new *headed*
browser window - positioned at exactly the same point the automated chain
reached - and poll that window for a mega.nz/mega.co.nz URL to appear once
the user clears the visible challenge there. Auto-capture it the moment it
appears, close the browser, return it. No copy/paste, no second tab, no
re-running the tool. On (c), the headed fallback is skipped entirely (it
would just be a silent dead end) and AdNetworkDeadEndError is raised
immediately with an accurate explanation instead.

Safety invariants enforced throughout:
  - Never logs into MEGA.
  - Never navigates to mega.nz/mega.co.nz - only ever regex-searches for the
    URL string in page content/response URLs/anchors.
  - Never follows a popup/new-tab (closed immediately on detection).
  - Never retries the same `ht` token automatically (research found this
    makes Cloudflare's response worse, not better) - one headless attempt,
    then (if blocked) one headed fallback window, full stop.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

MEGA_RE = re.compile(r"https?://mega\.(nz|co\.nz)/[^\s\"'<>]+", re.IGNORECASE)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1366, "height": 768}

# Timeouts (milliseconds unless noted). Tuned per docs/research/playwright-feasibility.md:
# the terminal Cloudflare challenge, when it happens, reliably does NOT clear on its
# own within a short window - so the headless-phase wait is kept short (no point
# burning CLI time on a wait that evidence says won't pay off), while the headed
# fallback gets a genuinely generous window since a human now has to act.
PAGE_LOAD_TIMEOUT_MS = 20_000
VERIFY_BUTTON_TIMEOUT_MS = 10_000
POSTNEXT_WAIT_TIMEOUT_S = 20
POSTNEXT_CLICK_RESPONSE_TIMEOUT_MS = 15_000
HEADLESS_BLOCK_POLL_SECONDS = 12
HEADED_FALLBACK_TIMEOUT_SECONDS = 240  # 4 minutes


class GateResolutionError(Exception):
    """Base class for resolver failures."""


class GateChainStructureError(GateResolutionError):
    """The expected DOM structure (humanVerify/.postnext/etc.) did not appear -
    likely means teknoasian.com changed its gate template again."""


class CloudflareChallengeTimeout(GateResolutionError):
    """The headed fallback window was left open for the full timeout budget and
    no mega.nz URL was ever captured (the user did not clear the challenge in
    time, or the chain terminated in something other than a mega.nz link)."""


class AdNetworkDeadEndError(GateResolutionError):
    """The `.postnext` click diverted the tab to unrelated ad-network content
    (e.g. a random teknoasian.com blog article) instead of reaching either the
    mega.nz chain or a genuine Cloudflare challenge, and there was nothing on
    the resulting page to interact with.

    This is a known teknoasian.com race condition - see "Why patchright
    reached a clean comparison and the other two didn't" in
    docs/research/cloudflare-bypass-investigation.md, which documents the
    site's own `if (LLIsBlocked) {...} else { window.open(adUrl);
    xxc.submit(); }` branch and observed cases where a blocked/failed
    `window.open()` causes the *same tab* to navigate to the ad content
    instead. `_install_window_open_shim()` prevents most instances of this at
    the source; this exception covers whatever slips through so the CLI can
    report it accurately instead of misreporting it as a Cloudflare
    challenge (there is nothing to "clear" on a page like this, so opening a
    headed browser window for it would just be a silent dead end - as
    observed in a live bug report).

    UPDATE 2026-07-24 (live re-check, see the "LLIsBlocked was a red herring"
    addendum in docs/research/cloudflare-bypass-investigation.md for full
    evidence): the `LLIsBlocked`/ad-blocker-detection theory below is
    superseded. The actual live gate script, recovered by loading real
    `?ht=...` URLs, hardcodes `var LLIsBlocked = false;` and wraps the only
    code that could ever change it in dead code - `if (false) {
    checkAdsBlocked(...) }` - so `LLIsBlocked` never becomes true today, from
    any network, and `xxc.submit()` fires unconditionally on `.postnext`
    (there is also no `if (!w) location.href = adUrl`-shaped fallback in the
    current script at all - `window.open(submitRedirect, "_blank")` is called
    and its return value is never inspected). The real, still-unsolved
    obstacle reproduced live on that date - on every one of 4 independent
    attempts, across 3 different tokens, via full click-chain, via a
    same-session `fetch()` POST, and via a plain same-session `fetch()` GET -
    was a genuine Cloudflare Managed Challenge (`Just a moment...` title, 403,
    `challenges.cloudflare.com` CSP) on the *second* request to
    teknoasian.com in a session, regardless of request method or human-like
    click timing/mouse movement. This is IP-reputation-based bot management,
    not a JS check this module can neutralize - it's the same wall already
    catalogued as unsolved-from-this-VM in the "Cloudflare Terminal-Challenge
    Bypass Investigation (Part 5)" section of
    docs/research/cloudflare-bypass-investigation.md. This exception's
    original text is preserved below for history, but its network-level
    ad-blocker hypothesis should be treated as ruled out, not just unproven.

    Note the shim only covers *one* branch of the gate script: the `else`
    half, where `window.open(adUrl)` fails/returns null. `LLIsBlocked` itself
    - the flag that picks the `if` branch in the first place - is evaluated
    by a separate ad-blocker-detection check the shim does not touch, and the
    real `xxc.submit()` (the call that reaches the actual mega.nz chain) only
    happens inside that same `else` branch. So a *network-level* ad/DNS
    blocker (as opposed to a browser-extension blocker, which this tool's
    vanilla, extension-free Playwright context never has installed - see
    docs/research/cloudflare-bypass-investigation.md's addendum on this) that
    causes `LLIsBlocked` to evaluate true is a plausible, distinct trigger for
    this same dead end that the shim cannot address at all. See --manual in
    the CLI for a way to route around this entirely."""


class _BlockedDuringChain(Exception):
    """Internal signal: a Cloudflare challenge was detected while trying to
    drive the click-chain (front door or mid-chain), distinct from the
    structural "site changed" error. Never raised out of this module."""


@dataclass
class _ChainOutcome:
    mega_url: str | None
    blocked: bool


WINDOW_OPEN_SHIM_JS = """
(() => {
  const nativeOpen = window.open;
  window.open = function (...args) {
    const win = nativeOpen.apply(window, args);
    if (win) return win;
    // Popup blocked (common for programmatic window.open() from an
    // automated click, per docs/research/cloudflare-bypass-investigation.md).
    // teknoasian.com's own gate script does
    // `var w = window.open(adUrl); if (!w) location.href = adUrl;`-shaped
    // fallbacks (see the humanVerify/.postnext chain), which hijacks the
    // *main tab* to the ad content when window.open() fails, derailing the
    // chain before it ever reaches the real #xxc form response or a genuine
    // Cloudflare challenge. Returning a truthy stub window instead makes
    // that fallback branch believe the popup succeeded, so the main tab is
    // left alone.
    return { closed: false, close() {}, focus() {}, blur() {}, postMessage() {} };
  };
})();
"""


def _install_window_open_shim(context: BrowserContext) -> None:
    """Neutralizes the same-tab-hijack fallback some ad scripts use when
    `window.open()` is blocked. Must be installed before any page navigates
    (via `context.add_init_script`, not after `new_page()`) so it's present
    before the gate's own scripts run. See WINDOW_OPEN_SHIM_JS and
    AdNetworkDeadEndError for the full rationale.

    NOTE (2026-07-24 live re-check, see AdNetworkDeadEndError's docstring):
    the current live gate script does not actually gate `xxc.submit()` on
    `window.open()`'s return value at all - it calls `window.open(...)` and
    then `xxc.submit()` unconditionally. Kept as defense-in-depth in case an
    older/other gate template variant (teknoasian.com's script has changed at
    least twice historically per docs/research/prior-art-and-alternatives.md)
    does use that pattern - it's harmless either way."""
    context.add_init_script(WINDOW_OPEN_SHIM_JS)


def _install_popup_guard(context: BrowserContext, ignored: list[str]) -> None:
    """Ad-monetization popups fire alongside the legitimate `.postnext` click
    (confirmed in research: `window.open(...)` to an unrelated domain). Close
    any such popup immediately without ever navigating it or reading its
    content beyond the URL, which is kept only for diagnostics/logging."""

    def on_popup(popup: Page) -> None:
        ignored.append(popup.url)
        try:
            popup.close()
        except Exception:
            pass

    context.on("page", on_popup)


def manual_fallback_message(gate_url: str) -> str:
    """Shared "do it yourself" message for the automated flow's fallback
    prints (see resolve_gate_url()'s dead-end/Cloudflare branches below) and
    for the CLI's --manual mode (pahe_dl/cli.py), so both surfaces say the
    same thing. `gate_url` should be the original `?ht=...` URL, not a
    mid-chain/session-carrying URL - it's meant to be opened fresh in a
    plain, unrelated browser (possibly on a different machine entirely, e.g.
    this tool running headless on a VM and the user finishing verification on
    their own desktop)."""
    return (
        "Open this link in your own browser to complete verification and "
        f"get the MEGA link:\n{gate_url}"
    )


def _find_mega_url(*texts: str) -> str | None:
    for text in texts:
        if not text:
            continue
        m = MEGA_RE.search(text)
        if m:
            return m.group(0)
    return None


def _is_cloudflare_challenge(page: Page) -> bool:
    try:
        title = page.title()
    except Exception:
        title = ""
    if "just a moment" in title.lower():
        return True
    try:
        # Cloudflare's Turnstile widget is embedded via a challenges.cloudflare.com
        # iframe when the managed challenge is actually rendered (not just present
        # in a <script src> reference, which appears on plenty of harmless pages).
        return page.locator("iframe[src*='challenges.cloudflare.com']").count() > 0
    except Exception:
        return False


def _looks_like_ad_dead_end(page: Page) -> bool:
    """True if `page` is neither a genuine Cloudflare challenge nor still
    showing any of the gate's own click-chain markers - i.e. it looks like
    the ad-network diversion AdNetworkDeadEndError documents, not a
    Cloudflare challenge and not mid-chain. There would be nothing for a
    human to click through on a page like this, so a headed-browser fallback
    would be pointless."""
    if _is_cloudflare_challenge(page):
        return False
    try:
        has_gate_markers = (
            page.locator(".humanVerify").count() > 0
            or page.locator(".postnext").count() > 0
            or page.locator("#xxc").count() > 0
        )
    except Exception:
        has_gate_markers = False
    return not has_gate_markers


def _drive_verify_chain(page: Page) -> None:
    """Clicks through the humanVerify -> (optional skip) -> postnext sequence.
    Raises GateChainStructureError if the expected elements never appear and
    it's not explained by a Cloudflare challenge (a fast, loud failure rather
    than a silent hang, per the design brief) - the caller checks for the
    Cloudflare case itself, both before and after this call, since the
    challenge can appear at the front door, mid-chain, or only at the
    terminal step depending on run/IP/token-freshness."""
    try:
        page.wait_for_selector(".humanVerify button.verify", timeout=VERIFY_BUTTON_TIMEOUT_MS)
    except Exception as exc:
        if _is_cloudflare_challenge(page):
            raise _BlockedDuringChain() from exc
        raise GateChainStructureError(
            "The '.humanVerify button.verify' (Click To Verify) control never "
            "appeared - teknoasian.com's gate template may have changed."
        ) from exc

    page.click(".humanVerify button.verify")

    deadline = time.monotonic() + POSTNEXT_WAIT_TIMEOUT_S
    clicked_skip = False
    while time.monotonic() < deadline:
        if page.locator(".postnext").count() > 0:
            break
        if not clicked_skip and page.locator(".Skipper button.skipcontent").count() > 0:
            page.click(".Skipper button.skipcontent")
            clicked_skip = True
        time.sleep(0.5)

    if page.locator(".postnext").count() == 0:
        raise GateChainStructureError(
            "The '.postnext' (Continue/Get Link) control never appeared after "
            "the countdown - teknoasian.com's gate template may have changed."
        )

    with page.context.expect_event(
        "response",
        predicate=lambda r: r.request.resource_type == "document",
        timeout=POSTNEXT_CLICK_RESPONSE_TIMEOUT_MS,
    ):
        page.click(".postnext")


def _poll_for_outcome(page: Page, deadline: float, poll_interval: float = 1.0) -> _ChainOutcome:
    """Poll the page for a mega.nz URL or a confirmed Cloudflare-block state
    until `deadline` (a time.monotonic() timestamp)."""
    while time.monotonic() < deadline:
        try:
            html = page.content()
        except Exception:
            html = ""
        found = _find_mega_url(html, page.url)
        if found:
            return _ChainOutcome(mega_url=found, blocked=False)
        try:
            anchors = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
        except Exception:
            anchors = []
        found = _find_mega_url(*anchors)
        if found:
            return _ChainOutcome(mega_url=found, blocked=False)
        time.sleep(poll_interval)
    return _ChainOutcome(mega_url=None, blocked=_is_cloudflare_challenge(page))


def _new_browser_and_context(
    playwright: Playwright,
    headless: bool,
    storage_state: dict | None = None,
) -> tuple[Browser, BrowserContext]:
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context(
        user_agent=USER_AGENT,
        viewport=VIEWPORT,
        storage_state=storage_state,
    )
    # Must happen before context.new_page()/any navigation - see
    # _install_window_open_shim's docstring.
    _install_window_open_shim(context)
    return browser, context


def resolve_gate_url(
    gate_url: str,
    referer: str | None = None,
    on_status: callable = None,
) -> str:
    """Resolve a teknoasian.com `?ht=...` gate URL to a final mega.nz URL.

    `on_status(str)`, if given, is called with short human-readable progress
    messages (e.g. "loading gate...", "waiting for challenge to clear...") so
    a CLI caller can show a spinner/stage label instead of a silent hang, per
    docs/planning/cli-ux-notes.md.

    Raises GateChainStructureError if the expected page structure never
    appears (site changed), CloudflareChallengeTimeout if the headed
    fallback window timed out without the link resolving, or
    AdNetworkDeadEndError if the chain was diverted to unrelated ad-network
    content with nothing to click through (not a Cloudflare challenge - see
    that exception's docstring).
    """

    def status(msg: str) -> None:
        if on_status:
            on_status(msg)

    ignored_popups: list[str] = []

    with sync_playwright() as playwright:
        status("launching browser...")
        browser, context = _new_browser_and_context(playwright, headless=True)
        # NOTE: the popup guard must be installed *after* creating the main
        # page, not before - BrowserContext's "page" event fires for every
        # new page in the context, including the initial context.new_page()
        # call itself, not just real popups/new tabs. Installing it first
        # would race-close our own main page.
        page = context.new_page()
        _install_popup_guard(context, ignored_popups)

        status("loading gate URL...")
        try:
            page.goto(
                gate_url,
                timeout=PAGE_LOAD_TIMEOUT_MS,
                wait_until="domcontentloaded",
                referer=referer,
            )
        except Exception as exc:
            browser.close()
            raise GateResolutionError(f"Failed to load gate URL {gate_url}: {exc}") from exc

        # Cloudflare's front door usually passes silently (per research), but
        # a previously-used/"hot" token can get an immediate challenge - check
        # before assuming the click-chain structure is even present.
        blocked_early = _is_cloudflare_challenge(page)

        if not blocked_early:
            status("verifying (click-through chain)...")
            try:
                _drive_verify_chain(page)
            except _BlockedDuringChain:
                blocked_early = True
            except GateChainStructureError:
                browser.close()
                raise

        if not blocked_early:
            status("waiting for the resolved link...")
            deadline = time.monotonic() + HEADLESS_BLOCK_POLL_SECONDS
            outcome = _poll_for_outcome(page, deadline)
            if outcome.mega_url:
                status("resolved automatically.")
                browser.close()
                return outcome.mega_url

        # Not resolved. This is one of two very different situations, and
        # conflating them was the root cause of a real bug (see
        # AdNetworkDeadEndError and docs/research/cloudflare-bypass-
        # investigation.md): a genuine Cloudflare challenge (blocked_early,
        # or the page currently shows CF's own markers) DOES have something
        # a human can clear in a headed browser window. An ad-network
        # diversion - the tab landed on unrelated content with no gate
        # markers and no Cloudflare markers either - does NOT; opening a
        # headed window for it is a silent dead end, so fail fast and
        # honestly instead.
        if not blocked_early and _looks_like_ad_dead_end(page):
            dead_end_url = page.url
            browser.close()
            # Never leave the user with just an error and no way forward -
            # see manual_fallback_message()'s docstring and --manual in
            # cli.py. Printed via on_status (reaches the console immediately,
            # regardless of exactly how the caller chooses to report the
            # exception below).
            status(manual_fallback_message(gate_url))
            raise AdNetworkDeadEndError(
                f"The click-through chain was diverted to an unrelated page "
                f"({dead_end_url}) instead of reaching the download link or a "
                "Cloudflare challenge. This is a known teknoasian.com "
                "ad-network race condition, not a Cloudflare challenge - "
                "there is nothing to solve on that page. Please re-run the "
                "tool (this is usually transient), try --manual, or see "
                "docs/research/cloudflare-bypass-investigation.md."
            )

        is_cf = blocked_early or _is_cloudflare_challenge(page)
        if is_cf:
            status(
                "hit a Cloudflare challenge - opening a visible browser window "
                "for you to clear it (this is expected sometimes; see "
                "README)..."
            )
        else:
            status(
                "didn't resolve automatically (still on an unfinished gate "
                "page) - opening a visible browser window for you to finish "
                "it..."
            )
        # Print the plain fallback link *before* attempting the headed
        # window, not just on eventual timeout - this is the only fallback
        # a headless machine (no display at all) has, since the headed
        # launch below will itself fail there. See manual_fallback_message().
        status(manual_fallback_message(gate_url))
        # Carry the current session (cookies) and exact URL over so the
        # fallback window opens already positioned at the same point the
        # automated chain reached.
        current_url = page.url
        storage_state = context.storage_state()
        browser.close()

        headed_browser, headed_context = _new_browser_and_context(
            playwright, headless=False, storage_state=storage_state
        )
        headed_page = headed_context.new_page()
        _install_popup_guard(headed_context, ignored_popups)
        try:
            headed_page.goto(current_url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
        except Exception as exc:
            headed_browser.close()
            raise GateResolutionError(
                f"Failed to open the headed fallback window at {current_url}: {exc}"
            ) from exc

        status(
            f"waiting up to {HEADED_FALLBACK_TIMEOUT_SECONDS}s for "
            + ("the challenge to be cleared..." if is_cf else "the link to resolve...")
        )
        headed_deadline = time.monotonic() + HEADED_FALLBACK_TIMEOUT_SECONDS
        final_outcome = _poll_for_outcome(headed_page, headed_deadline, poll_interval=1.5)

        headed_browser.close()

        if final_outcome.mega_url:
            status("resolved.")
            return final_outcome.mega_url

        if is_cf:
            raise CloudflareChallengeTimeout(
                f"Timed out after {HEADED_FALLBACK_TIMEOUT_SECONDS}s waiting for "
                "a mega.nz URL to appear in the headed browser window. Either "
                "the challenge wasn't cleared in time, or the chain led "
                "somewhere other than mega.nz for this entry."
            )
        raise CloudflareChallengeTimeout(
            f"Timed out after {HEADED_FALLBACK_TIMEOUT_SECONDS}s waiting for a "
            "mega.nz URL to appear in the headed browser window. This wasn't a "
            "Cloudflare challenge - the gate page just never resolved to a "
            "download link in that window."
        )
