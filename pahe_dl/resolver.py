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
  5. The terminal response is either:
       (a) the resolved page/content containing a mega.nz URL - success, or
       (b) a genuine Cloudflare Managed Challenge (403 / `cf-mitigated:
           challenge` / "Just a moment..." title) - the known, reproducible
           block documented in playwright-feasibility.md.

Hybrid fallback (the key UX requirement): on (b), do NOT ask the user to
start over in a separate browser. Instead, carry the already-established
session (cookies) and the exact blocked URL over into a new *headed*
browser window - positioned at exactly the same point the automated chain
reached - and poll that window for a mega.nz/mega.co.nz URL to appear once
the user clears the visible challenge there. Auto-capture it the moment it
appears, close the browser, return it. No copy/paste, no second tab, no
re-running the tool.

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


class _BlockedDuringChain(Exception):
    """Internal signal: a Cloudflare challenge was detected while trying to
    drive the click-chain (front door or mid-chain), distinct from the
    structural "site changed" error. Never raised out of this module."""


@dataclass
class _ChainOutcome:
    mega_url: str | None
    blocked: bool


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
    appears (site changed), or CloudflareChallengeTimeout if the headed
    fallback window timed out without the user clearing the challenge.
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

        # Blocked (or ambiguous - no link found and no explicit block signature
        # either, e.g. a slow render): fall back to a headed window rather than
        # giving up, since the whole point of this design is to avoid asking the
        # user to start over from scratch. Carry the current session (cookies)
        # and exact URL over so the fallback window opens already positioned at
        # the same point the automated chain reached.
        status(
            "hit a Cloudflare challenge - opening a visible browser window for "
            "you to clear it (this is expected sometimes; see README)..."
        )
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
            f"waiting up to {HEADED_FALLBACK_TIMEOUT_SECONDS}s for the challenge "
            "to be cleared..."
        )
        headed_deadline = time.monotonic() + HEADED_FALLBACK_TIMEOUT_SECONDS
        final_outcome = _poll_for_outcome(headed_page, headed_deadline, poll_interval=1.5)

        headed_browser.close()

        if final_outcome.mega_url:
            status("resolved.")
            return final_outcome.mega_url

        raise CloudflareChallengeTimeout(
            f"Timed out after {HEADED_FALLBACK_TIMEOUT_SECONDS}s waiting for a "
            "mega.nz URL to appear in the headed browser window. Either the "
            "challenge wasn't cleared in time, or the chain led somewhere "
            "other than mega.nz for this entry."
        )
