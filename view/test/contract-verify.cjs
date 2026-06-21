#!/usr/bin/env node
/**
 * contract-verify.cjs — Repeatable contract verification for I-Studio Frontend Shell.
 *
 * Uses Playwright (already in devDependencies) to verify the critical behavior
 * contract without a browser: drawer default/toggle ARIA, tablist/tab/tabpanel
 * links, resize behavior, and no backend calls.
 *
 * Usage:
 *   node test/contract-verify.cjs           # quick run (single large viewport)
 *   CONTRACT_VERIFY_ALL=1 node test/contract-verify.cjs   # full suite
 *
 * Returns exit code 0 on all pass, 1 on any failure.
 */

const { chromium } = require("playwright");

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";
const FULL_SUITE = Boolean(process.env.CONTRACT_VERIFY_ALL);

// Colours for output
const RED = "\x1b[31m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";

let passed = 0;
let failed = 0;
let assertions = [];

function check(name, condition, detail) {
  if (condition) {
    passed++;
    assertions.push(`  ${GREEN}✓${RESET} ${name}`);
  } else {
    failed++;
    assertions.push(`  ${RED}✗${RESET} ${name} — ${detail || "assertion failed"}`);
  }
}

async function main() {
  console.log(`${BOLD}I-Studio Frontend — Contract Verification${RESET}\n`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ ignoreHTTPSErrors: true });

  // ---------------------------------------------------------------------------
  // Check 1: Large viewport default — drawer open, ARIA correct
  // ---------------------------------------------------------------------------
  {
    const page = await context.newPage();

    // Track backend API calls (non-static, non-document requests under /api/)
    const apiCalls = [];
    page.on("request", (req) => {
      const url = req.url();
      try {
        if (new URL(url).pathname.startsWith("/api/") && !["document", "script", "stylesheet"].includes(req.resourceType())) {
          apiCalls.push(url);
        }
      } catch {
        // ignore invalid URLs
      }
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    // Allow React hydration to settle
    await page.waitForTimeout(300);

    const assetsBtn = page.locator('button[aria-controls="assets-drawer"]');
    const drawer = page.locator("#assets-drawer");

    check(
      "4.1: Assets button exists with aria-controls",
      (await assetsBtn.count()) === 1,
    );
    check(
      "4.2: aria-expanded=true at 1440px (large viewport default)",
      (await assetsBtn.getAttribute("aria-expanded")) === "true",
    );
    check(
      "4.3: Drawer is visible at 1440px (display:flex, not hidden)",
      !(await drawer.getAttribute("class"))?.includes("hidden"),
      `class=${await drawer.getAttribute("class")}`,
    );

    // Tablist contract
    const tablist = page.locator('[role="tablist"]');
    check(
      "4.4: Container has role=tablist",
      (await tablist.count()) === 1,
    );

    const tab = page.locator('[role="tab"][aria-selected="true"][aria-controls="panel-studio-canvas"]');
    check(
      "4.5: Active tab has role=tab, aria-selected=true, aria-controls=panel-studio-canvas",
      (await tab.count()) === 1,
    );

    const tabpanel = page.locator('[role="tabpanel"]#panel-studio-canvas');
    check(
      "4.6: Tabpanel has role=tabpanel, id=panel-studio-canvas",
      (await tabpanel.count()) === 1,
    );
    check(
      "4.7: Tabpanel aria-labelledby matches tab id",
      (await tabpanel.getAttribute("aria-labelledby")) === "tab-studio-canvas",
    );

    // No API calls
    check(
      "4.8: Zero backend API calls on page load",
      apiCalls.length === 0,
      `found ${apiCalls.length} calls: ${apiCalls.join(", ")}`,
    );

    // Toggle: close
    await assetsBtn.click();
    await page.waitForTimeout(150);
    check(
      "4.9: Toggle click → aria-expanded=false",
      (await assetsBtn.getAttribute("aria-expanded")) === "false",
    );
    check(
      "4.10: Toggle click → drawer hidden",
      (await drawer.getAttribute("class"))?.includes("hidden"),
      `class=${await drawer.getAttribute("class")}`,
    );

    // Re-toggle: open
    await assetsBtn.click();
    await page.waitForTimeout(150);
    check(
      "4.11: Re-toggle click → aria-expanded=true",
      (await assetsBtn.getAttribute("aria-expanded")) === "true",
    );
    check(
      "4.12: Re-toggle click → drawer visible",
      !(await drawer.getAttribute("class"))?.includes("hidden"),
      `class=${await drawer.getAttribute("class")}`,
    );

    await page.close();
  }

  // ---------------------------------------------------------------------------
  // Check 2: Small viewport default — drawer closed, ARIA correct
  // ---------------------------------------------------------------------------
  {
    const page = await context.newPage();
    await page.setViewportSize({ width: 375, height: 700 });
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    const assetsBtn = page.locator('button[aria-controls="assets-drawer"]');
    const drawer = page.locator("#assets-drawer");

    check(
      "4.13: aria-expanded=false at 375px (small viewport default)",
      (await assetsBtn.getAttribute("aria-expanded")) === "false",
    );
    check(
      "4.14: Drawer hidden at 375px",
      (await drawer.getAttribute("class"))?.includes("hidden"),
      `class=${await drawer.getAttribute("class")}`,
    );

    // Toggle open on small viewport
    await assetsBtn.click();
    await page.waitForTimeout(150);
    check(
      "4.15: Toggle on small viewport → aria-expanded=true",
      (await assetsBtn.getAttribute("aria-expanded")) === "true",
    );
    check(
      "4.16: Toggle on small viewport → drawer visible",
      !(await drawer.getAttribute("class"))?.includes("hidden"),
      `class=${await drawer.getAttribute("class")}`,
    );

    await page.close();
  }

  // ---------------------------------------------------------------------------
  // Check 3: Resize behavior (only in full suite — it's inherently slower)
  // ---------------------------------------------------------------------------
  if (FULL_SUITE) {
    // 3a: Large → small resize (no user toggle) — drawer should close
    {
      const page = await context.newPage();
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(BASE_URL, { waitUntil: "networkidle" });
      await page.waitForTimeout(300);

      const assetsBtn = page.locator('button[aria-controls="assets-drawer"]');
      const drawer = page.locator("#assets-drawer");

      // Resize down to small
      await page.setViewportSize({ width: 800, height: 700 });
      await page.waitForTimeout(200);

      check(
        "4.17: Resize 1440→800 → aria-expanded=false (no user toggle)",
        (await assetsBtn.getAttribute("aria-expanded")) === "false",
      );
      check(
        "4.18: Resize 1440→800 → drawer hidden",
        (await drawer.getAttribute("class"))?.includes("hidden"),
        `class=${await drawer.getAttribute("class")}`,
      );

      // Resize back up
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.waitForTimeout(200);

      check(
        "4.19: Resize 800→1440 → aria-expanded=true (back to default, no user toggle)",
        (await assetsBtn.getAttribute("aria-expanded")) === "true",
      );
      check(
        "4.20: Resize 800→1440 → drawer visible",
        !(await drawer.getAttribute("class"))?.includes("hidden"),
        `class=${await drawer.getAttribute("class")}`,
      );

      await page.close();
    }

    // 3b: User toggle + resize — user override preserved
    {
      const page = await context.newPage();
      await page.setViewportSize({ width: 375, height: 700 });
      await page.goto(BASE_URL, { waitUntil: "networkidle" });
      await page.waitForTimeout(300);

      const assetsBtn = page.locator('button[aria-controls="assets-drawer"]');
      const drawer = page.locator("#assets-drawer");

      // User toggles open on small viewport
      await assetsBtn.click();
      await page.waitForTimeout(150);

      // Resize to large
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.waitForTimeout(200);

      check(
        "4.21: User opened on small → resize to large → drawer stays open (user override preserved)",
        !(await drawer.getAttribute("class"))?.includes("hidden"),
        `class=${await drawer.getAttribute("class")}`,
      );
      // aria-expanded should still be true (state preserved)
      check(
        "4.22: User opened on small → resize to large → aria-expanded=true",
        (await assetsBtn.getAttribute("aria-expanded")) === "true",
      );

      await page.close();
    }

    // 3c: User toggled on large, resize small → stays closed (user override preserved)
    {
      const page = await context.newPage();
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.goto(BASE_URL, { waitUntil: "networkidle" });
      await page.waitForTimeout(300);

      const assetsBtn = page.locator('button[aria-controls="assets-drawer"]');
      const drawer = page.locator("#assets-drawer");

      // User closes drawer on large viewport
      await assetsBtn.click();
      await page.waitForTimeout(150);

      // Resize to small
      await page.setViewportSize({ width: 800, height: 700 });
      await page.waitForTimeout(200);

      check(
        "4.23: User closed on large → resize to small → drawer stays closed (user override preserved)",
        (await drawer.getAttribute("class"))?.includes("hidden"),
        `class=${await drawer.getAttribute("class")}`,
      );

      // Resize back to large
      await page.setViewportSize({ width: 1440, height: 900 });
      await page.waitForTimeout(200);

      check(
        "4.24: User closed on large → resize small → resize back to large → drawer stays closed (user override preserved)",
        (await drawer.getAttribute("class"))?.includes("hidden"),
        `class=${await drawer.getAttribute("class")}`,
      );

      await page.close();
    }
  }

  // ---------------------------------------------------------------------------
  // Check 4: ChatComposer behavior — Enter no-op, Shift+Enter, no backend
  // ---------------------------------------------------------------------------
  {
    const page = await context.newPage();
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(BASE_URL, { waitUntil: "networkidle" });
    await page.waitForTimeout(300);

    const textarea = page.locator('textarea[aria-label="Message Agent"]');
    const sendBtn = page.locator('button[aria-label="Send Message"]');
    const attachBtn = page.locator('button[aria-label="Attach File"]');

    // Verify elements exist
    check(
      "5.1: Chat composer textarea exists",
      (await textarea.count()) === 1,
    );
    check(
      "5.2: Send button exists with aria-label",
      (await sendBtn.count()) === 1,
    );
    check(
      "5.3: Attach button exists with aria-label",
      (await attachBtn.count()) === 1,
    );

    const initialValue = await textarea.inputValue();

    // Enter key — no-op (value unchanged, no message sent)
    await textarea.focus();
    await page.keyboard.press("Enter");
    await page.waitForTimeout(50);
    check(
      "5.4: Enter key no-op — textarea value unchanged",
      (await textarea.inputValue()) === initialValue,
      `expected "${initialValue}", got "${await textarea.inputValue()}"`,
    );

    // Shift+Enter — inserts newline (browser default)
    await page.keyboard.press("Shift+Enter");
    await page.waitForTimeout(50);
    const afterShiftEnter = await textarea.inputValue();
    check(
      "5.5: Shift+Enter inserts newline",
      afterShiftEnter.length > initialValue.length,
      `length before=${initialValue.length}, after=${afterShiftEnter.length}`,
    );

    // --- No-op contract: Send button click ---
    // Track API calls during no-op click tests
    const noopApiCalls = [];
    page.on("request", (req) => {
      const url = req.url();
      try {
        if (new URL(url).pathname.startsWith("/api/") && !["document", "script", "stylesheet"].includes(req.resourceType())) {
          noopApiCalls.push(url);
        }
      } catch {
        // ignore invalid URLs
      }
    });

    // Snapshot pre-click state
    const sendPreUrl = page.url();
    const sendPreValue = await textarea.inputValue();
    const sendPreMsgCount = await page.locator('section[aria-label="Messages"] article').count();

    await sendBtn.click();
    await page.waitForTimeout(50);

    check(
      "5.6: Send click — zero API calls",
      noopApiCalls.length === 0,
      `found ${noopApiCalls.length} calls: ${noopApiCalls.join(", ")}`,
    );

    const sendPostUrl = page.url();
    check(
      "5.7: Send click — URL unchanged",
      sendPostUrl === sendPreUrl,
      `expected "${sendPreUrl}", got "${sendPostUrl}"`,
    );

    const sendPostMsgCount = await page.locator('section[aria-label="Messages"] article').count();
    check(
      "5.8: Send click — message count unchanged",
      sendPostMsgCount === sendPreMsgCount,
      `expected ${sendPreMsgCount}, got ${sendPostMsgCount}`,
    );

    const sendPostValue = await textarea.inputValue();
    check(
      "5.9: Send click — textarea value unchanged",
      sendPostValue === sendPreValue,
      `expected "${sendPreValue}", got "${sendPostValue}"`,
    );

    check(
      "5.10: Send click — textarea still exists and interactable",
      (await textarea.count()) === 1,
    );

    // --- No-op contract: Attach button click ---
    // Snapshot pre-click state
    const attachPreCallCount = noopApiCalls.length;
    const attachPreUrl = page.url();
    const attachPreMsgCount = await page.locator('section[aria-label="Messages"] article').count();

    // If a file chooser appears (e.g. from browser native behavior), dismiss it immediately
    page.once("filechooser", (fileChooser) => {
      fileChooser.cancel();
    });

    await attachBtn.click();
    await page.waitForTimeout(50);

    check(
      "5.11: Attach click — zero API calls",
      noopApiCalls.length === attachPreCallCount,
      `found ${noopApiCalls.length - attachPreCallCount} new calls`,
    );

    const attachPostUrl = page.url();
    check(
      "5.12: Attach click — URL unchanged",
      attachPostUrl === attachPreUrl,
      `expected "${attachPreUrl}", got "${attachPostUrl}"`,
    );

    const attachPostMsgCount = await page.locator('section[aria-label="Messages"] article').count();
    check(
      "5.13: Attach click — message count unchanged",
      attachPostMsgCount === attachPreMsgCount,
      `expected ${attachPreMsgCount}, got ${attachPostMsgCount}`,
    );

    check(
      "5.14: Attach click — textarea still exists and interactable",
      (await textarea.count()) === 1,
    );

    await page.close();
  }

  // ---------------------------------------------------------------------------
  // Results
  // ---------------------------------------------------------------------------
  await browser.close();

  console.log(assertions.join("\n"));
  console.log(`\n${BOLD}Results:${RESET} ${GREEN}${passed} passed${RESET}${failed > 0 ? `, ${RED}${failed} failed${RESET}` : ""}`);

  if (failed > 0) {
    process.exit(1);
  }
}

main().catch((err) => {
  console.error(`${RED}Fatal error:${RESET}`, err);
  process.exit(1);
});
