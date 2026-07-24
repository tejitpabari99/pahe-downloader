"""
SPIKE / RESEARCH ARTIFACT - NOT PRODUCTION CODE.

camoufox variant of teknoasian-chain-spike.py, written for the Cloudflare-
bypass investigation (see docs/research/cloudflare-bypass-investigation.md
for full findings). camoufox is a custom anti-detect Firefox build with a
Playwright-compatible sync API.

Confirmed outcome (2026-07-24): same failure mode as nodriver, for a related
but distinct reason. camoufox bundles uBlock Origin by default; the gate's
own JS has an explicit ad-blocker-detection branch (`LLIsBlocked`, confirmed
in recovered page source) that alters the flow when it thinks an ad blocker
is present. With UBO active, clicking ".postnext" diverted the CURRENT tab
(not a popup - the ad-monetization `window.open()` call did not open a new
tab) to an unrelated real-looking teknoasian.com blog article. Excluding UBO
(`exclude_addons=[DefaultAddons.UBO]`) changed the intermediate mechanics
(revealed a previously-undocumented `id="xq"`/`hq`-field variant of the
chain, auto-submitted by the page's own script) but still ended at the same
kind of unrelated-article diversion, never the terminal Cloudflare wall and
never a mega.nz URL. Net effect: camoufox is less reliable than Playwright/
patchright for even *reaching* the terminal challenge here. Kept as a
reference only, not a working resolver.

Safety: never navigate popups, never fetch mega.nz content, stop the instant
a mega.nz URL is observed.
"""
import sys, re, time
from camoufox.sync_api import Camoufox
from camoufox import DefaultAddons

MEGA_RE = re.compile(r"https?://mega\.(nz|co\.nz)/[^\s\"'<>]+", re.IGNORECASE)

def run(url, referer, headless=True, label=""):
    print(f"\n===== {label} url={url[:70]}... headless={headless} =====")
    t0 = time.time()
    with Camoufox(headless=headless, geoip=True, exclude_addons=[DefaultAddons.UBO]) as browser:
        context = browser  # Camoufox() context manager yields a BrowserContext-like object
        page = context.new_page()

        ignored_popups = []
        def on_popup(popup):
            print(f"[POPUP - IGNORED, closing] {popup.url}")
            ignored_popups.append(popup.url)
            try:
                popup.close()
            except Exception:
                pass
        context.on("page", on_popup)

        mega_found = {"url": None}
        def on_response(resp):
            m = MEGA_RE.search(resp.url)
            if m and not mega_found["url"]:
                mega_found["url"] = m.group(0)
                print(f"[MEGA FOUND @ response.url] {m.group(0)}")
        context.on("response", on_response)

        page.goto(url, timeout=20000, wait_until="domcontentloaded", referer=referer)
        print(f"[t+{time.time()-t0:.1f}s] loaded, title={page.title()!r} url={page.url}")

        try:
            page.wait_for_selector(".humanVerify button.verify", timeout=8000)
        except Exception as e:
            print(f"[no humanVerify button appeared] {e}")
            html = page.content()
            m = MEGA_RE.search(html)
            if m:
                print(f"[MEGA FOUND in body] {m.group(0)}")
            print(re.sub(r'\s+', ' ', html)[:1200])
            return mega_found["url"]

        print(f"[t+{time.time()-t0:.1f}s] clicking 'Click To Verify'")
        page.click(".humanVerify button.verify")

        deadline = time.time() + 20
        clicked_skip = False
        while time.time() < deadline:
            if page.locator(".postnext").count() > 0:
                break
            if not clicked_skip and page.locator(".Skipper button.skipcontent").count() > 0:
                print(f"[t+{time.time()-t0:.1f}s] clicking intermediate 'Continue' (.skipcontent)")
                page.click(".Skipper button.skipcontent")
                clicked_skip = True
            time.sleep(0.5)

        if page.locator(".postnext").count() == 0:
            print(f"[t+{time.time()-t0:.1f}s] .postnext never appeared - dumping state")
            print(re.sub(r'\s+', ' ', page.content())[:1500])
            return mega_found["url"]

        print(f"[t+{time.time()-t0:.1f}s] .postnext button appeared, clicking it (final step)")
        page.click(".postnext")
        time.sleep(2)

        for i in range(20):
            time.sleep(1)
            try:
                t = page.title()
            except Exception:
                t = ""
            if not t.lower().startswith("loading") and "just a moment" not in t.lower():
                print(f"[t+{time.time()-t0:.1f}s] title stabilized to {t!r}")
                break
        else:
            print(f"[t+{time.time()-t0:.1f}s] title never stabilized, last={t!r}")

        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass

        # The site's own script may auto-submit ANOTHER hidden form (hq -> hw -> xxc
        # chain per prior-art doc) - if so, that's part of the documented mechanism,
        # not an action we're taking ourselves. Give it a further bounded window to
        # settle, polling for either a mega.nz URL or a stable non-loading title.
        for i in range(15):
            try:
                t = page.title()
                u = page.url
            except Exception:
                t, u = "", ""
            if MEGA_RE.search(page.content()) or MEGA_RE.search(u or ""):
                break
            if not t.lower().startswith("loading"):
                break
            time.sleep(1)

        final_html = page.content()
        final_url = page.url
        print(f"[t+{time.time()-t0:.1f}s] after submit: url={final_url} title={page.title()!r}")

        m = MEGA_RE.search(final_html) or MEGA_RE.search(final_url)
        if m:
            mega_found["url"] = m.group(0)
            print(f"[MEGA FOUND in final page] {m.group(0)}")
        else:
            print("[no mega.nz URL found] snippet:")
            print(re.sub(r'\s+', ' ', final_html)[:1500])

        print(f"\n=== SUMMARY: elapsed={time.time()-t0:.1f}s mega_url={mega_found['url']} ignored_popups={ignored_popups}")
        return mega_found["url"]

if __name__ == "__main__":
    url = sys.argv[1]
    referer = sys.argv[2] if len(sys.argv) > 2 else None
    if "--headed" in sys.argv:
        headless = False
    elif "--virtual" in sys.argv:
        headless = "virtual"
    else:
        headless = True
    run(url, referer, headless=headless)
