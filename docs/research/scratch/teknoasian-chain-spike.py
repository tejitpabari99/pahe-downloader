"""
SPIKE / RESEARCH ARTIFACT - NOT PRODUCTION CODE.

Written during the Playwright feasibility investigation (see
docs/research/playwright-feasibility.md for full findings, verdict, and
architecture recommendation). Kept as a reference for the real
`resolve_gate_url()` implementation because it captures the exact,
verified-live DOM selectors and click sequence for teknoasian.com's
"SoraLink" human-verify gate - not because this file itself should be
imported or run as-is. It has no error handling suitable for a CLI tool,
hardcodes a throwaway UA/viewport, and prints copious debug output.

Known outcome as of 2026-07-23 (see the findings doc): this script
successfully drives every step of the chain below, but the final POST is
reliably blocked by a non-auto-clearing Cloudflare Managed Challenge -
i.e. running this script as-is will NOT get you a mega.nz link. Treat it
as "here is how to click the buttons," not "here is a working resolver."

Drives the actual SoraLink human-verify chain observed on teknoasian.com:
  1. Load ?ht=... gate URL (redirects to a page skinned as the site homepage
     but with an injected ".humanVerify" widget).
  2. Click ".humanVerify button.verify" ("Click To Verify").
  3. Wait out the JS countdown; a "Continue"/"Get Link" button (".postnext")
     appears (possibly via an intermediate ".skipcontent" stage on "post" pages).
  4. Click ".postnext". This triggers a `window.open(adUrl)` popup (ad monetization,
     IGNORED/closed immediately, never followed) AND a same-page form POST
     (#xxc, field hw=<LLPayload>).
  5. Observe the POST's resulting page for a mega.nz URL.

Safety: any popup that isn't part of the pahe->teknoasian->mega chain is closed
immediately without navigation. Never navigates to mega.nz itself.
"""
import sys, re, time
from playwright.sync_api import sync_playwright

MEGA_RE = re.compile(r"https?://mega\.(nz|co\.nz)/[^\s\"'<>]+", re.IGNORECASE)

def run(url, referer, headless=True, label=""):
    print(f"\n===== {label} url={url[:70]}... =====")
    t0 = time.time()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 768},
        )
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
            browser.close()
            return

        print(f"[t+{time.time()-t0:.1f}s] clicking 'Click To Verify'")
        page.click(".humanVerify button.verify")

        # After clicking, either:
        #  (a) short path: after ~5s, a #xxc form + .postnext button appears directly, or
        #  (b) long path ("IsPost"): after ~5s, a .Skipper button.skipcontent appears,
        #      click it, wait ~4s more, then .postnext appears.
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
            browser.close()
            return

        print(f"[t+{time.time()-t0:.1f}s] .postnext button appeared, clicking it (final step)")
        with context.expect_event("response", predicate=lambda r: r.request.resource_type == "document", timeout=15000):
            page.click(".postnext")

        # give the resulting page time to render/redirect further, and to let
        # a Cloudflare Managed Challenge auto-clear if it's going to.
        for i in range(20):
            time.sleep(1)
            try:
                t = page.title()
            except Exception:
                t = ""
            if "just a moment" not in t.lower():
                print(f"[t+{time.time()-t0:.1f}s] title cleared to {t!r}")
                break
        else:
            print(f"[t+{time.time()-t0:.1f}s] still 'Just a moment...' after extended wait")
        final_html = page.content()
        final_url = page.url
        print(f"[t+{time.time()-t0:.1f}s] after submit: url={final_url} title={page.title()!r}")
        if "just a moment" in page.title().lower():
            try:
                page.screenshot(path="cf_challenge.png", full_page=True)
                print("[screenshot saved] cf_challenge.png (cwd)")
            except Exception as e:
                print(f"[screenshot failed] {e}")

        m = MEGA_RE.search(final_html) or MEGA_RE.search(final_url)
        if m:
            mega_found["url"] = m.group(0)
            print(f"[MEGA FOUND in final page] {m.group(0)}")
        else:
            print("[no mega.nz URL found yet in final page] snippet:")
            print(re.sub(r'\s+', ' ', final_html)[:2000])
            # look for any outbound anchors that might be the real link
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            candidates = [h for h in hrefs if "teknoasian.com" not in h and "javascript:" not in h and not h.startswith("https://pahe.ink")]
            print(f"[non-teknoasian anchors found: {len(candidates)}]")
            for h in candidates[:20]:
                print("   ", h)

        print(f"\n=== SUMMARY: elapsed={time.time()-t0:.1f}s mega_url={mega_found['url']} ignored_popups={ignored_popups}")
        browser.close()

if __name__ == "__main__":
    url = sys.argv[1]
    referer = sys.argv[2] if len(sys.argv) > 2 else None
    headless = "--headed" not in sys.argv
    run(url, referer, headless=headless)
