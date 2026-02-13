---
name: visual-test
description: "Visually verify UI changes using Puppeteer screenshots. Use when you need to check layout, colors, positioning, or other visual aspects of a UI change."
---

# Visual Test

Skill for visually verifying UI changes using Puppeteer screenshots.

## When to use

When you need to visually verify that a UI change looks correct —
layout, colors, popover positioning, text content, etc. This runs a
real browser against the Zulip test server and takes screenshots that
you can read as images.

## Steps

### 1. Write the puppeteer test script

Create `web/e2e-tests/_claude_<feature>_test.test.ts` using this template:

```typescript
import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function visual_test(page: Page): Promise<void> {
    await common.log_in(page);
    await common.screenshot(page, "step-1-logged-in");

    // Navigate, interact, and screenshot each significant state.
    // See "Available helpers" below.
}

await common.run_test(visual_test);
```

Adapt the body to exercise whatever UI you need to verify. Take a
screenshot at every visually significant state using descriptive names
like `step-2-color-picker-open`, `step-3-color-selected`.

**Important patterns:**

- After login, wait for the page to settle before interacting:
  ```typescript
  await page.waitForSelector("#left-sidebar", {visible: true});
  await page.evaluate(() => new Promise((r) => setTimeout(r, 1000)));
  ```
- Add short delays (50–200ms) between keyboard actions to allow the
  UI to update:
  ```typescript
  await page.keyboard.press("ArrowDown");
  await page.evaluate(() => new Promise((r) => setTimeout(r, 100)));
  ```
- To change user settings (e.g., buddy list style), use the API and
  reload:
  ```typescript
  await page.evaluate(async () => {
      const csrfToken = document.querySelector<HTMLInputElement>(
          'input[name="csrfmiddlewaretoken"]',
      )?.value ?? "";
      await fetch("/json/settings", {
          method: "PATCH",
          headers: {
              "Content-Type": "application/x-www-form-urlencoded",
              "X-CSRFToken": csrfToken,
          },
          body: "user_list_style=1",
      });
  });
  await page.reload({waitUntil: "networkidle2"});
  ```
- To check DOM state (focus, classes, presence of elements), use
  `page.evaluate()`:
  ```typescript
  const on_vdot = await page.evaluate(() =>
      document.activeElement?.classList.contains("sidebar-menu-icon") ?? false,
  );
  ```
- For assertions that produce readable test output, use a helper
  pattern rather than `assert`:
  ```typescript
  const results: string[] = [];
  function check(name: string, ok: boolean): void {
      results.push(`${ok ? "PASS" : "FAIL"}: ${name}`);
      console.log(`${ok ? "PASS" : "FAIL"}: ${name}`);
  }
  // ... at end:
  const failures = results.filter((r) => r.startsWith("FAIL"));
  console.log(`\n${results.length - failures.length}/${results.length} tests passed`);
  ```
  This keeps the test running through failures so you see all results,
  unlike `assert` which aborts on the first failure.

### 2. Run the test

```bash
PUPPETEER_EXECUTABLE_PATH=/tmp/chromium-arm64/chrome-linux/chrome \
    ./tools/test-js-with-puppeteer _claude_<feature>_test
```

The `PUPPETEER_EXECUTABLE_PATH` override is required on this ARM
host (see "Environment details" below). The runner matches test file
names by prefix, so you don't need the full filename or `.test.ts`
suffix. This starts a fresh test server on port 9981, runs the
script, and saves screenshots to `var/puppeteer/`. The test database
is reset between test files.

To run all existing Puppeteer tests (to check for regressions), omit
the test name argument (but still set the env var):

```bash
PUPPETEER_EXECUTABLE_PATH=/tmp/chromium-arm64/chrome-linux/chrome \
    ./tools/test-js-with-puppeteer
```

This runs all `*.test.ts` files in `web/e2e-tests/` alphabetically,
including any `_claude_*` files. To run only the upstream tests, run
them individually by name.

**Timeout:** Tests can take 1–3 minutes each. Use a 300000ms timeout
for the Bash tool.

### 3. Read the screenshots

Use the Read tool on each `var/puppeteer/step-*.png` file. Claude's
multimodal vision will show the rendered page.

### 4. Analyze and report

Describe what you see — layout, colors, text content, positioning,
any issues. Compare against what was expected.

Zulip displays any JS exceptions encountered as a pop-up, but you
should also be able to get them from the puppeteer output.

### 5. Iterate if needed

If something is wrong, fix the source code (or adjust the test
script), then re-run from step 2.

### 6. Clean up

Leave test files as untracked `_claude_*` files so you can reuse them
when rebasing or iterating on the pull request. The `_claude_` prefix
is a convention to distinguish these from Zulip's committed test
files. Do not commit them.

## Environment details

- **Architecture:** aarch64 (ARM). Puppeteer's auto-downloaded
  Chrome is x86_64 and does NOT work (fails with
  `qemu-x86_64: Could not open '/lib64/ld-linux-x86-64.so.2'`).
  A native AArch64 Chromium is pre-installed at
  `/tmp/chromium-arm64/chrome-linux/chrome`. You **must** set the
  environment variable when running tests:
  ```bash
  PUPPETEER_EXECUTABLE_PATH=/tmp/chromium-arm64/chrome-linux/chrome \
      ./tools/test-js-with-puppeteer _claude_<feature>_test
  ```
- **If the Chrome binary is missing** (e.g., after `/tmp` is
  cleared), download a native ARM64 Chromium snapshot:
  ```bash
  mkdir -p /tmp/chromium-arm64 && cd /tmp/chromium-arm64
  curl -L -o chromium.zip \
      'https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_Arm%2FLAST_CHANGE?alt=media'
  # Read the revision number from LAST_CHANGE, then:
  REVISION=$(cat chromium.zip)  # it's a text file with the rev number
  curl -L -o chromium.zip \
      "https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_Arm%2F${REVISION}%2Fchrome-linux.zip?alt=media"
  unzip chromium.zip
  ```
  If the snapshot CDN doesn't have ARM builds, try the Ubuntu
  `chromium-browser` snap or download from another source. The key
  requirement is a native AArch64 ELF binary at the expected path.
- **Headless mode:** Tests run headless by default (`headless: true`
  in `common.ts`). There is no display server.
- **`prepare_puppeteer_run()`** in `tools/lib/test_script.py` calls
  `node install.mjs` in the puppeteer package dir and clears old
  `failure-*.png` screenshots before each run.

## Test infrastructure facts

- **Server URL:** `http://zulip.zulipdev.com:9981/`
- **Login:** `common.log_in(page)` uses credentials from
  `var/puppeteer/test_credentials.json` (auto-generated by the test
  harness). Default user is Desdemona (realm admin).
- **Known users:** `common.fullname.cordelia`, `.othello`, `.hamlet`
- **Screenshots:** saved to `var/puppeteer/<name>.png`
- **Window size:** 1400 x 1024
- **Test data:** The test database includes channels like "Verona",
  "Denmark", "Scotland" with topics and messages. Non-system user
  group `hamletcharacters` (members: Cordelia, Hamlet).
- **`zulip_test` global:** Only a limited set of internal functions
  are exposed — see `web/src/zulip_test.ts`. Functions like
  `get_stream_id` and `get_user_id_from_name` are available, but
  `user_groups` is not. Navigate to groups via URL hash routes
  or by clicking list items instead.
- **Database reset:** The test runner calls
  `reset_zulip_test_database()` and `POST /flush_caches` between
  test files, so each test file starts with a clean state.
- **`common.run_test()`** handles browser lifecycle, console log
  forwarding with source-map resolution, automatic failure
  screenshots, and logout at the end.

## Available helpers (from `web/e2e-tests/lib/common.ts`)

| Helper                                        | Purpose                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------------------ |
| `common.log_in(page)`                         | Log in as the default user (Desdemona)                                               |
| `common.screenshot(page, "name")`             | Save `var/puppeteer/name.png`                                                        |
| `common.clear_and_type(page, selector, text)` | Clear input and type                                                                 |
| `common.wait_for_micromodal_to_open(page)`    | Wait for modal open animation                                                        |
| `common.wait_for_micromodal_to_close(page)`   | Wait for modal close animation                                                       |
| `common.get_stream_id(page, name)`            | Get a stream's ID                                                                    |
| `common.get_user_id_from_name(page, name)`    | Get a user's ID                                                                      |
| `common.open_personal_menu(page)`             | Open the personal menu                                                               |
| `common.manage_organization(page)`            | Navigate to org settings                                                             |
| `common.send_message(page, type, params)`     | Send a stream or DM message                                                          |
| `common.send_multiple_messages(page, msgs)`   | Send several messages in sequence                                                    |
| `common.select_item_via_typeahead(page, ...)` | Type into a field and select a typeahead item                                        |
| `page.waitForSelector(sel, {visible: true})`  | Wait for element                                                                     |
| `page.click(selector)`                        | Click an element                                                                     |
| `page.goto(url)`                              | Navigate (e.g., hash routes like `http://zulip.zulipdev.com:9981/#groups/1/general`) |
| `page.evaluate(() => ...)`                    | Run JS in browser context                                                            |
| `page.keyboard.press("Escape")`               | Dismiss popovers/modals                                                              |
| `page.keyboard.press("Tab")`                  | Move focus between elements                                                          |
