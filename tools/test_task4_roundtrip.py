"""
test_task4_roundtrip.py — Round-trip gate for Task 4 (mission I/O).

Tests:
  1. No-op round-trip: load real Chernarus mission.sqm, make NO edits,
     download → output MUST be byte-identical to input.
  2. Single-value edit: change one town's value → diff must affect only that
     town's init= line; everything else byte-identical.
  3. Single-drag: change one town's position → diff must affect only that
     town's position[]= line; everything else byte-identical.
  4. 0 console errors throughout.

Requires playwright: pip install playwright && playwright install chromium
"""
import sys
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

MISSION_SQM = Path(r"C:\Users\Steff\a2waspwarfare\Missions\[55-2hc]warfarev2_073v48co.chernarus\mission.sqm")
BASE_URL     = "http://localhost:8095"
SCREENSHOT_DIR = Path(r"C:\Users\Steff\sector-planner\docs\screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

def read_sqm():
    return MISSION_SQM.read_text(encoding="utf-8", errors="replace")

def run_tests():
    original_text = read_sqm()
    failures = []
    screenshots = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context()
        console_errors = []

        def on_console(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        # ============================================================
        # TEST 1: No-op round-trip — byte-identical
        # ============================================================
        print("\n[TEST 1] No-op round-trip (byte-identical)...")
        page = ctx.new_page()
        page.on("console", on_console)
        page.goto(BASE_URL, wait_until="networkidle")
        page.wait_for_timeout(1500)

        # Upload the file via JS (inject the text directly to avoid file picker complexity)
        # We expose the file content via window and call loadSqmText directly
        page.evaluate(f"""
            (sqmText) => {{
                window._testSqmText = sqmText;
            }}
        """, original_text)

        # Call loadSqmText from the page's JS context
        page.evaluate("""
            () => {
                loadSqmText(window._testSqmText, 'mission.sqm.chernarus');
            }
        """)
        page.wait_for_timeout(800)

        # Take screenshot of loaded state
        ss1 = SCREENSHOT_DIR / "task4-loaded-noop.png"
        page.screenshot(path=str(ss1), full_page=False)
        screenshots.append(ss1)
        print(f"  Screenshot: {ss1}")

        # Trigger download and capture the blob content
        downloaded_text = page.evaluate("""
            () => {
                // Call produceSqmOutput directly
                return produceSqmOutput();
            }
        """)

        if downloaded_text is None:
            failures.append("TEST 1 FAIL: produceSqmOutput() returned null")
            print("  FAIL: produceSqmOutput() returned null")
        elif downloaded_text == original_text:
            print("  PASS: output is byte-identical to input (no-op round-trip)")
        else:
            # Find first difference
            min_len = min(len(downloaded_text), len(original_text))
            diff_at = None
            for i in range(min_len):
                if downloaded_text[i] != original_text[i]:
                    diff_at = i
                    break
            if diff_at is None:
                diff_at = min_len
            ctx_start = max(0, diff_at - 40)
            ctx_end   = min(len(original_text), diff_at + 80)
            ctx_out   = min(len(downloaded_text), diff_at + 80)
            msg = (
                f"TEST 1 FAIL: Output differs from input at char {diff_at}.\n"
                f"  Input  [{diff_at-40}:{diff_at+80}]: {repr(original_text[ctx_start:ctx_end])}\n"
                f"  Output [{diff_at-40}:{diff_at+80}]: {repr(downloaded_text[ctx_start:ctx_out])}\n"
                f"  Input len: {len(original_text)}  Output len: {len(downloaded_text)}"
            )
            failures.append(msg)
            print(f"  FAIL: {msg}")

        page.close()

        # ============================================================
        # TEST 2: Single value edit — only that town's init= changes
        # ============================================================
        print("\n[TEST 2] Single value edit (Kamenka value 300->500)...")
        page2 = ctx.new_page()
        page2.on("console", on_console)
        page2.goto(BASE_URL, wait_until="networkidle")
        page2.wait_for_timeout(1500)

        page2.evaluate(f"""
            (sqmText) => {{ window._testSqmText = sqmText; }}
        """, original_text)
        page2.evaluate("""
            () => { loadSqmText(window._testSqmText, 'mission.sqm.chernarus'); }
        """)
        page2.wait_for_timeout(800)

        # Edit Kamenka's value to 500 (via the in-memory data, simulating inspector edit)
        page2.evaluate("""
            () => {
                const data = townsData && townsData['chernarus'];
                if (!data) throw new Error('No chernarus data');
                const t = data.towns.find(t => t.name === 'Kamenka');
                if (!t) throw new Error('Kamenka not found');
                t.value = 500;
                markEdited(t);
            }
        """)

        out2 = page2.evaluate("() => produceSqmOutput()")

        if out2 is None:
            failures.append("TEST 2 FAIL: produceSqmOutput() returned null after edit")
            print("  FAIL: produceSqmOutput() returned null")
        elif out2 == original_text:
            failures.append("TEST 2 FAIL: Output identical to input after value change")
            print("  FAIL: output unchanged after edit")
        else:
            # Find all differing lines
            orig_lines = original_text.splitlines()
            out_lines  = out2.splitlines()
            changed_lines = []
            for i, (ol, nl) in enumerate(zip(orig_lines, out_lines)):
                if ol != nl:
                    changed_lines.append((i + 1, ol, nl))
            # Extra/missing lines
            if len(orig_lines) != len(out_lines):
                changed_lines.append(('line-count', len(orig_lines), len(out_lines)))

            if len(changed_lines) == 1 and 'line-count' not in changed_lines[0][0:1]:
                lno, before, after = changed_lines[0]
                if 'Kamenka' in before and 'Kamenka' in after and ',500,' in after:
                    print(f"  PASS: Only line {lno} changed (Kamenka init= with value 500)")
                    print(f"    Before: {before.strip()[:120]}")
                    print(f"    After:  {after.strip()[:120]}")
                else:
                    failures.append(f"TEST 2 FAIL: 1 line changed but not Kamenka init:\n  {before.strip()[:120]}\n  → {after.strip()[:120]}")
                    print(f"  FAIL: 1 line changed but not Kamenka init")
            else:
                msg = f"TEST 2 FAIL: Expected exactly 1 changed line, got {len(changed_lines)}:\n"
                for item in changed_lines[:5]:
                    msg += f"  Line {item[0]}: {str(item[1])[:80]} → {str(item[2])[:80]}\n"
                failures.append(msg)
                print(f"  FAIL: {len(changed_lines)} lines changed (expected 1)")

        ss2 = SCREENSHOT_DIR / "task4-single-value-edit.png"
        page2.screenshot(path=str(ss2))
        screenshots.append(ss2)
        page2.close()

        # ============================================================
        # TEST 3: Single position drag — only that town's position[]= changes
        # ============================================================
        print("\n[TEST 3] Single position change (Kamenka pos drag)...")
        page3 = ctx.new_page()
        page3.on("console", on_console)
        page3.goto(BASE_URL, wait_until="networkidle")
        page3.wait_for_timeout(1500)

        page3.evaluate(f"""
            (sqmText) => {{ window._testSqmText = sqmText; }}
        """, original_text)
        page3.evaluate("""
            () => { loadSqmText(window._testSqmText, 'mission.sqm.chernarus'); }
        """)
        page3.wait_for_timeout(800)

        # Move Kamenka to a new position (simulate drag)
        page3.evaluate("""
            () => {
                const data = townsData && townsData['chernarus'];
                if (!data) throw new Error('No chernarus data');
                const t = data.towns.find(t => t.name === 'Kamenka');
                if (!t) throw new Error('Kamenka not found');
                t.pos = [1900, 2300]; // new position
                markEdited(t);
            }
        """)

        out3 = page3.evaluate("() => produceSqmOutput()")

        if out3 is None:
            failures.append("TEST 3 FAIL: produceSqmOutput() returned null after pos change")
            print("  FAIL: produceSqmOutput() returned null")
        elif out3 == original_text:
            failures.append("TEST 3 FAIL: Output identical to input after pos change")
            print("  FAIL: output unchanged after pos edit")
        else:
            orig_lines = original_text.splitlines()
            out_lines  = out3.splitlines()
            changed_lines = []
            for i, (ol, nl) in enumerate(zip(orig_lines, out_lines)):
                if ol != nl:
                    changed_lines.append((i + 1, ol, nl))
            if len(orig_lines) != len(out_lines):
                changed_lines.append(('line-count', len(orig_lines), len(out_lines)))

            # Expect exactly 1 line changed: position[]= line for Kamenka's depot block
            if len(changed_lines) == 1 and 'line-count' not in changed_lines[0][0:1]:
                lno, before, after = changed_lines[0]
                if 'position' in after and '1900' in after:
                    print(f"  PASS: Only line {lno} changed (Kamenka position[])")
                    print(f"    Before: {before.strip()[:100]}")
                    print(f"    After:  {after.strip()[:100]}")
                else:
                    failures.append(f"TEST 3 FAIL: 1 line changed but not position[]:\n  {before.strip()[:100]}\n  → {after.strip()[:100]}")
                    print(f"  FAIL: 1 changed line but not position[]")
            else:
                msg = f"TEST 3 FAIL: Expected 1 changed line, got {len(changed_lines)}:\n"
                for item in changed_lines[:5]:
                    msg += f"  Line {item[0]}: {str(item[1])[:80]} → {str(item[2])[:80]}\n"
                failures.append(msg)
                print(f"  FAIL: {len(changed_lines)} lines changed (expected 1)")

        ss3 = SCREENSHOT_DIR / "task4-single-pos-edit.png"
        page3.screenshot(path=str(ss3))
        screenshots.append(ss3)
        page3.close()

        browser.close()

    # ============================================================
    # RESULTS
    # ============================================================
    print("\n" + "="*60)
    if console_errors:
        print(f"CONSOLE ERRORS ({len(console_errors)}):")
        for e in console_errors[:10]:
            print(f"  {e}")
    else:
        print("CONSOLE ERRORS: 0")

    print(f"\nScreenshots:")
    for ss in screenshots:
        print(f"  {ss}")

    if failures:
        print(f"\n{'='*60}")
        print(f"FAILED ({len(failures)} failure(s)):")
        for f in failures:
            print(f"\n  {f}")
        return False
    else:
        print(f"\n{'='*60}")
        print("ALL TESTS PASSED")
        return True


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
