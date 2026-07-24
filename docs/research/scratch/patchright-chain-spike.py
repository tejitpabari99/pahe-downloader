"""
SPIKE / RESEARCH ARTIFACT - NOT PRODUCTION CODE.

Patchright variant of teknoasian-chain-spike.py, written for the Cloudflare-
bypass investigation (see docs/research/cloudflare-bypass-investigation.md
for full findings). Swaps stock Playwright for patchright (a stealth-patched
Playwright fork that removes several CDP-detection leaks). Otherwise drives
the identical click chain documented in playwright-feasibility.md.

Confirmed outcome (2026-07-24, 2-for-2 headless runs on distinct tokens):
BYTE-IDENTICAL terminal Cloudflare Managed Challenge to plain Playwright -
same "Just a moment..." title, same CSP referencing challenges.cloudflare.com.
Patchright's stealth patches made no observable difference at this specific
wall. Kept as a reference for whoever revisits this; not a working resolver.

Same safety rules as the original: never navigate popups, never fetch
mega.nz content, stop the instant a mega.nz URL is observed.
"""
import sys, re, time
from patchright.sync_api import sync_playwright

MEGA_RE = re.compile(r"https?://mega\.(nz|co\.nz)/[^\s\"'<>]+", re.IGNORECASE)

def run(url, referer, headless=True, label="", persistent_dir=None):
    print(f"\n===== {label} url={url[:70]}... headless={headless} persistent={persistent_dir} =====")
    t0 = time.time()
    with sync_playwright() as p:
        if persistent_dir:
            context = p.chromium.launch_persistent_context(
                persistent_dir,
                headless=headless,
                viewport={"width": 1366, "height": 768},
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
                no_viewport=False,
            )
            browser = None
        else:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
                viewport={"width": 1366, "height": 768},
            )
        page = context.pages[0] if context.pages else context.new_page()

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
            print("title:", page.title())
            print(re.sub(r'\s+', ' ', html)[:1000])
            if browser:
                browser.close()
            else:
                context.close()
            return mega_found["url"]

        print(f"[t+{time.time()-t0:.1f}s] clicking 'Click To Verify'")
        try:
            page.click(".humanVerify button.verify", timeout=8000)
        except Exception as e:
            print(f"[normal click failed ({e.__class__.__name__}), retrying with force=True]")
            page.click(".humanVerify button.verify", force=True)

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
            if browser:
                browser.close()
            else:
                context.close()
            return mega_found["url"]

        print(f"[t+{time.time()-t0:.1f}s] .postnext button appeared, clicking it (final step)")
        with context.expect_event("response", predicate=lambda r: r.request.resource_type == "document", timeout=15000):
            page.click(".postnext")

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
                page.screenshot(path="/tmp/claude-0/-root-projects-pahe-downloader/17cb7e15-cc25-470c-9d30-1dc6a19b74c0/scratchpad/cf_challenge_patchright.png", full_page=True)
                print("[screenshot saved] cf_challenge_patchright.png")
            except Exception as e:
                print(f"[screenshot failed] {e}")

        m = MEGA_RE.search(final_html) or MEGA_RE.search(final_url)
        if m:
            mega_found["url"] = m.group(0)
            print(f"[MEGA FOUND in final page] {m.group(0)}")
        else:
            print("[no mega.nz URL found yet in final page] snippet:")
            print(re.sub(r'\s+', ' ', final_html)[:2000])

        print(f"\n=== SUMMARY: elapsed={time.time()-t0:.1f}s mega_url={mega_found['url']} ignored_popups={ignored_popups}")
        if browser:
            browser.close()
        else:
            context.close()
        return mega_found["url"]

if __name__ == "__main__":
    url = sys.argv[1]
    referer = sys.argv[2] if len(sys.argv) > 2 else None
    headless = "--headed" not in sys.argv
    persistent = None
    for a in sys.argv:
        if a.startswith("--persistent="):
            persistent = a.split("=", 1)[1]
    run(url, referer, headless=headless, persistent_dir=persistent)
