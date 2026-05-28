---
name: visual-test
description: "Visually verify UI changes using Puppeteer screenshots. Use when you need to check layout, colors, positioning, or other visual aspects of a UI change."
---

# Visual Test

Runs a real browser against the Zulip test server and takes
screenshots you can read as images to verify layout, colors,
positioning, text content, etc.

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

These patterns are derived from the existing Puppeteer tests in
`web/e2e-tests/`. Follow them to write reliable, non-flaky tests.

#### Waiting: never use hardcoded timeouts

The existing test suite has essentially zero `setTimeout` calls
(the two in `common.ts` are explicitly commented workarounds for
specific animation flakes). Always wait for the specific condition
you expect instead. The three main waiting primitives, in order of
preference:

- **`waitForSelector`** — wait for an element to appear or disappear.
  This is the most common pattern in the test suite (100+ uses):

  ```typescript
  // Wait for element to be visible (most common)
  await page.waitForSelector("#left-sidebar", {visible: true});

  // Wait for element to disappear (e.g., overlay closed, row deleted)
  await page.waitForSelector("#subscription_overlay", {hidden: true});
  ```

- **`waitForFunction`** — wait for a condition that can't be
  expressed as a single selector (text content, element count,
  attribute value, application state):

  ```typescript
  // Wait for specific text content
  await page.waitForFunction(
      () => document.querySelector(".save-button")?.textContent?.trim() === "Save changes",
  );

  // Wait for element count after filtering
  await page.waitForFunction(
      () => document.querySelectorAll(".linkifier_row").length === 4,
  );

  // Wait for an input's value to update
  await page.waitForFunction(
      () => document.querySelector<HTMLInputElement>("#full_name")?.value === "New name",
  );

  // Wait for focus to land on a specific element
  await page.waitForFunction(
      () => document.activeElement?.classList?.contains("search") === true,
  );

  // Wait for internal app state via zulip_test
  await page.waitForFunction(
      (content) => {
          const last_msg = zulip_test.current_msg_list?.last();
          return last_msg !== undefined && last_msg.raw_content === content
              && !last_msg.locally_echoed;
      },
      {},
      content,
  );
  ```

- **`waitForNavigation`** — only for actual full-page navigations
  (form submits, reloads). Wrap with `Promise.all` when the
  navigation is triggered by an action:
  ```typescript
  await Promise.all([
      page.waitForNavigation(),
      page.$eval("form#login_form", (form) => { form.submit(); }),
  ]);
  ```

#### Interacting with elements

- **`page.click(selector)`** is the standard for clicking. When it's
  unreliable (overlapping elements, timing), fall back to clicking
  via `evaluate` — several existing tests do this with a comment
  explaining why:

  ```typescript
  // When page.click() is unreliable, click via the DOM directly
  await page.evaluate(() => {
      document.querySelector<HTMLElement>(".dialog_submit_button")?.click();
  });
  ```

- **`page.type(selector, text)`** for typing. Use `{delay: 100}`
  when typing triggers a typeahead or filter that needs per-keystroke
  updates:

  ```typescript
  await page.type('[name="user_list_filter"]', "ot", {delay: 100});
  ```

- **`common.clear_and_type(page, selector, text)`** to replace
  existing input content (triple-click + Delete + type).

- **`common.fill_form(page, selector, params)`** to fill multiple
  form fields at once — handles text inputs, checkboxes (by
  toggling), and `<select>` elements.

- **`common.select_item_via_typeahead(page, selector, str, item)`**
  to type into a field and pick a typeahead suggestion.

- **`page.keyboard.press("KeyC")`** for Zulip keyboard shortcuts.
  After pressing, wait for the resulting UI change:

  ```typescript
  await page.keyboard.press("KeyC");
  await page.waitForSelector("#compose-textarea", {visible: true});
  ```

- **Hover before clicking action buttons** that only appear on
  hover (e.g., message action icons):
  ```typescript
  const msg = (await page.$$(".message_row")).at(-1)!;
  await msg.hover();
  await page.waitForSelector(".message-actions-menu-button", {visible: true});
  await page.click(".message-actions-menu-button");
  ```

#### Navigating within the app

- **Click sidebar items** for in-app navigation:

  ```typescript
  await page.click(".narrow-filter[data-stream-id='...'] .stream-name");
  await page.waitForSelector("#message_view_header .zulip-icon-hashtag", {visible: true});
  ```

- **`page.goto(url)`** for hash-route navigation:

  ```typescript
  await page.goto(`http://zulip.zulipdev.com:9981/#channels/${stream_id}/Denmark`);
  ```

- **`common.manage_organization(page)`** to navigate to org settings,
  **`common.open_personal_menu(page)`** to open the personal menu.

#### Reading state with page.evaluate

Use `page.evaluate()` to read internal application state or DOM
properties not accessible through selectors:

```typescript
// Read internal Zulip state via the zulip_test global
const stream_id = await page.evaluate(
    () => zulip_test.get_sub("Verona")!.stream_id,
);

// Read DOM properties
const page_language = await page.evaluate(
    () => document.documentElement.lang,
);
```

#### Changing user settings via the API

Use `page.evaluate` with `fetch()` and reload, rather than clicking
through the settings UI:

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

#### XPath selectors for text matching

When you need to match elements by text content, use XPath with
`common.has_class_x()`:

```typescript
await page.waitForSelector(
    `xpath///*[${common.has_class_x("stream-name")} and normalize-space()="Verona"]`,
);
```

#### Assertions for visual tests

For visual test scripts, prefer a soft-assertion pattern that
reports all failures rather than aborting on the first:

```typescript
const results: string[] = [];
function check(name: string, ok: boolean): void {
    results.push(`${ok ? "PASS" : "FAIL"}: ${name}`);
    console.log(`${ok ? "PASS" : "FAIL"}: ${name}`);
}
// ... run checks ...
const failures = results.filter((r) => r.startsWith("FAIL"));
console.log(`\n${results.length - failures.length}/${results.length} tests passed`);
```

This keeps the test running through failures so you see all results,
unlike `assert` which aborts on the first failure.

### 2. Run the test

```bash
./tools/test-js-with-puppeteer _claude_<feature>_test
```

The runner matches test file names by prefix, so you don't need the
full filename or `.test.ts` suffix. This starts a fresh test server
on port 9981, runs the script, and saves screenshots to
`var/puppeteer/`. The test database is reset between test files.

On **aarch64 (ARM) hosts**, you must set `PUPPETEER_EXECUTABLE_PATH`
(see "Environment details" below):

```bash
PUPPETEER_EXECUTABLE_PATH=$(echo ~/.cache/ms-playwright/chromium-*/chrome-linux/chrome) \
    ./tools/test-js-with-puppeteer _claude_<feature>_test
```

To run all existing Puppeteer tests, omit the test name argument.

**Timeout:** Tests can take 1–3 minutes each. Use a 300000ms timeout
for the Bash tool.

### 3. Read the screenshots

Use the Read tool on each `var/puppeteer/step-*.png` file. Claude's
multimodal vision will show the rendered page.

### 4. Analyze and report

Describe what you see — layout, colors, text content, positioning,
any issues. Compare against what was expected.

Zulip displays any JS exceptions encountered as a pop-up, but you should
also be able to get them from the puppeteer output.

### 5. Iterate if needed

If something is wrong, fix the source code (or adjust the test
script), then re-run from step 2.

### 6. Clean up

Leave test files as untracked `_claude_*` files so you can reuse them
when rebasing or iterating on the pull request. The `_claude_` prefix
is a convention to distinguish these from Zulip's committed test
files. Do not commit them.

## Environment details

- **Architecture:** On x86_64, Puppeteer's bundled Chrome works. On
  **aarch64**, it does NOT (fails with rosetta/ld-linux errors). Use
  `uname -m` to check. For aarch64, install Playwright's Chromium
  and point `PUPPETEER_EXECUTABLE_PATH` at it (shown in step 2).
- **If the Playwright Chromium is missing**, install it:
  ```bash
  npx --yes playwright install chromium
  ```
- **Headless mode:** Tests run headless (`headless: true` in
  `common.ts`). There is no display server.

## Test infrastructure facts

- **Server URL:** `http://zulip.zulipdev.com:9981/`
- **Login:** `common.log_in(page)` uses credentials from
  `var/puppeteer/test_credentials.json` (auto-generated by the test
  harness). Default user is Desdemona (realm owner).
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

| Helper                                        | Purpose                                  |
| --------------------------------------------- | ---------------------------------------- |
| `common.log_in(page)`                         | Log in as the default user (Desdemona)   |
| `common.screenshot(page, "name")`             | Save `var/puppeteer/name.png`            |
| `common.clear_and_type(page, selector, text)` | Clear input and type                     |
| `common.fill_form(page, selector, params)`    | Fill multiple form fields at once        |
| `common.wait_for_micromodal_to_open(page)`    | Wait for modal open animation            |
| `common.wait_for_micromodal_to_close(page)`   | Wait for modal close animation           |
| `common.get_stream_id(page, name)`            | Get a stream's ID                        |
| `common.get_user_id_from_name(page, name)`    | Get a user's ID                          |
| `common.open_personal_menu(page)`             | Open the personal menu                   |
| `common.manage_organization(page)`            | Navigate to org settings                 |
| `common.send_message(page, type, params)`     | Send a stream or DM message              |
| `common.send_multiple_messages(page, msgs)`   | Send several messages in sequence        |
| `common.select_item_via_typeahead(page, ...)` | Type into a field and select a typeahead |
