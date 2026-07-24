"""
SPIKE / RESEARCH ARTIFACT - NOT PRODUCTION CODE.

nodriver variant of teknoasian-chain-spike.py, written for the Cloudflare-
bypass investigation (see docs/research/cloudflare-bypass-investigation.md
for full findings). Uses nodriver's CDP-based async API to drive the same
click chain.

Confirmed outcome (2026-07-24): inconsistent/broken chain execution, never a
clean comparison to the terminal wall. In one headless run the front-door
Cloudflare check itself (hop 1) challenged nodriver immediately - something
plain Playwright/patchright never triggered. In headed(+Xvfb) runs, clicking
the correct, verified ".postnext" button did NOT reach the terminal
Cloudflare POST at all - it was diverted, in the SAME tab (confirmed via
target-id tracking, not a popup-tracking bug), to an unrelated real-looking
teknoasian.com blog article. The gate's own JS (recovered from page source)
contains an explicit ad-blocker-detection branch (`LLIsBlocked`) with its own
retry-after-delay logic; nodriver's default browser environment appears to
trip some heuristic in that vicinity, sending the flow down a path this
script doesn't handle. Net effect: nodriver is less reliable than
Playwright/patchright for even *reaching* the terminal challenge here, let
alone passing it. No mega.nz URL was ever obtained. Kept as a reference only.

Safety: never navigate popups, never fetch mega.nz content, stop the instant
a mega.nz URL is observed.
"""
import asyncio, re, sys, time
import nodriver as uc

MEGA_RE = re.compile(r"https?://mega\.(nz|co\.nz)/[^\s\"'<>]+", re.IGNORECASE)
CHROME_PATH = "/root/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome"

async def main(url, headless=True):
    t0 = time.time()
    browser = await uc.start(headless=headless, browser_executable_path=CHROME_PATH,
                              sandbox=False)
    page = await browser.get(url)
    await asyncio.sleep(3)
    print(f"[t+{time.time()-t0:.1f}s] loaded, title={await page.evaluate('document.title')!r} url={page.url}")

    # find and click "Click To Verify"
    btn = None
    try:
        btn = await page.select(".humanVerify button.verify", timeout=8)
    except Exception as e:
        print(f"[select() raised] {e}")
    if not btn:
        print(f"[no humanVerify button appeared after t+{time.time()-t0:.1f}s]")
        html = await page.get_content()
        m = MEGA_RE.search(html)
        if m:
            print(f"[MEGA FOUND in body] {m.group(0)}")
        title = await page.evaluate("document.title")
        print(f"title={title!r} url={page.url}")
        print(html[:1200])
        browser.stop()
        return

    print(f"[t+{time.time()-t0:.1f}s] clicking 'Click To Verify'")
    await btn.click()

    async def try_select(sel):
        try:
            return await page.select(sel, timeout=0.1)
        except Exception:
            return None

    deadline = time.time() + 20
    clicked_skip = False
    postnext = None
    while time.time() < deadline:
        postnext = await try_select(".postnext")
        if postnext:
            break
        if not clicked_skip:
            skip = await try_select(".Skipper button.skipcontent")
            if skip:
                print(f"[t+{time.time()-t0:.1f}s] clicking intermediate 'Continue' (.skipcontent)")
                await skip.click()
                clicked_skip = True
        await asyncio.sleep(0.5)

    if not postnext:
        print(f"[t+{time.time()-t0:.1f}s] .postnext never appeared - dumping state")
        html = await page.get_content()
        print(html[:1500])
        browser.stop()
        return

    # Disambiguate: how many .postnext elements exist, and which one did select() grab?
    import json as _json
    dbg_raw = await page.evaluate(
        "JSON.stringify(Array.from(document.querySelectorAll('.postnext')).map(e => ({tag:e.tagName, html:e.outerHTML.slice(0,200), href:e.href||null})))"
    )
    dbg = _json.loads(dbg_raw)
    print(f"[.postnext candidates on page: {len(dbg)}]")
    for i, d in enumerate(dbg):
        print(f"  [{i}] tag={d.get('tag')} href={d.get('href')} html={d.get('html')}")

    print(f"[t+{time.time()-t0:.1f}s] .postnext button appeared, clicking it (final step)")
    orig_target_id = page.target.target_id if hasattr(page, "target") else None
    await postnext.click()
    await asyncio.sleep(2)

    print(f"[browser.tabs count: {len(browser.tabs)}] orig_target_id={orig_target_id}")
    for i, t in enumerate(browser.tabs):
        try:
            tid = t.target.target_id if hasattr(t, "target") else "?"
            ttitle = await t.evaluate("document.title")
            thref = await t.evaluate("location.href")
        except Exception as e:
            tid, ttitle, thref = "?", f"<err {e}>", "?"
        same = " <== SAME AS 'page' VAR" if t is page else ""
        orig = " <== ORIGINAL TAB" if tid == orig_target_id else ""
        print(f"  tab[{i}] target_id={tid} url={thref} title={ttitle!r}{same}{orig}")
        if t is not page and tid != orig_target_id:
            print(f"    [POPUP - closing, never navigating] {thref}")
            try:
                await t.close()
            except Exception:
                pass

    # re-bind `page` to the ORIGINAL tab (in case nodriver's `page` var silently
    # followed a popup/new target), so subsequent inspection is of the real gate flow
    for t in browser.tabs:
        tid = t.target.target_id if hasattr(t, "target") else None
        if tid == orig_target_id:
            page = t
            break

    for i in range(20):
        await asyncio.sleep(1)
        try:
            title = await page.evaluate("document.title")
        except Exception:
            title = ""
        if "just a moment" not in (title or "").lower():
            print(f"[t+{time.time()-t0:.1f}s] title cleared to {title!r}")
            break
    else:
        print(f"[t+{time.time()-t0:.1f}s] still 'Just a moment...' after extended wait")

    final_html = await page.get_content()
    real_url = await page.evaluate("location.href")
    title = await page.evaluate("document.title")
    print(f"[t+{time.time()-t0:.1f}s] after submit: page.url={page.url} location.href={real_url} title={title!r}")

    with open("/tmp/claude-0/-root-projects-pahe-downloader/17cb7e15-cc25-470c-9d30-1dc6a19b74c0/scratchpad/nodriver_final.html", "w") as f:
        f.write(final_html)

    m = MEGA_RE.search(final_html) or MEGA_RE.search(real_url or "")
    if m:
        print(f"[MEGA FOUND in final page] {m.group(0)}")
    else:
        print("[no mega.nz URL found] full html saved to nodriver_final.html")
        has_xxc = 'id="xxc"' in final_html or "id='xxc'" in final_html
        print(f"[xxc anchor present in html: {has_xxc}]")
        print("[title tag count / cf markers]", "just a moment" in final_html.lower(), "cf-mitigated" in final_html.lower())

    print(f"\n=== SUMMARY: elapsed={time.time()-t0:.1f}s")
    browser.stop()

if __name__ == "__main__":
    url = sys.argv[1]
    headless = "--headed" not in sys.argv
    uc.loop().run_until_complete(main(url, headless=headless))
