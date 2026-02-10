# Visual Test

User-invocable skill for visually verifying UI changes using Puppeteer
screenshots.

## When to use

When you need to visually verify that a UI change looks correct —
layout, colors, popover positioning, text content, etc. This runs a
real browser against the Zulip test server and takes screenshots that
you can read as images.

## Steps

### 1. Write the puppeteer test script

Create `web/e2e-tests/_claude_feature_x_test.test.ts` using this template:

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

### 2. Run the test

```bash
./tools/test-js-with-puppeteer _clause_feature_x_test
```

This starts a fresh test server on port 9981, runs the script, and
saves screenshots to `var/puppeteer/`.

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

Once you've gotten a solid test, leave it as an untracked file, so
that you can use it when rebasing or iterating on the pull request.

## Test infrastructure facts

- **Server URL:** `http://zulip.zulipdev.com:9981/`
- **Login:** `common.log_in(page)` uses credentials from
  `var/puppeteer/test_credentials.json` (auto-generated). Default
  user is Desdemona (realm admin).
- **Known users:** `common.fullname.cordelia`, `.othello`, `.hamlet`
- **Screenshots:** saved to `var/puppeteer/<name>.png`
- **Window size:** 1400 x 1024
- **Test data:** The test database includes a non-system user group
  `hamletcharacters` (members: Cordelia, Hamlet).
- **`zulip_test` global:** Only a limited set of internal functions
  are exposed — see `web/src/zulip_test.ts`. Functions like
  `get_stream_id` and `get_user_id_from_name` are available, but
  `user_groups` is not. Navigate to groups via URL hash routes
  or by clicking list items instead.

## Available helpers (from `web/e2e-tests/lib/common.ts`)

| Helper                                        | Purpose                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------------------ |
| `common.log_in(page)`                         | Log in as the default user (Iago)                                                    |
| `common.screenshot(page, "name")`             | Save `var/puppeteer/name.png`                                                        |
| `common.clear_and_type(page, selector, text)` | Clear input and type                                                                 |
| `common.wait_for_micromodal_to_open(page)`    | Wait for modal open animation                                                        |
| `common.wait_for_micromodal_to_close(page)`   | Wait for modal close animation                                                       |
| `common.get_stream_id(page, name)`            | Get a stream's ID                                                                    |
| `common.get_user_id_from_name(page, name)`    | Get a user's ID                                                                      |
| `common.open_personal_menu(page)`             | Open the personal menu                                                               |
| `common.manage_organization(page)`            | Navigate to org settings                                                             |
| `page.waitForSelector(sel, {visible: true})`  | Wait for element                                                                     |
| `page.click(selector)`                        | Click an element                                                                     |
| `page.goto(url)`                              | Navigate (e.g., hash routes like `http://zulip.zulipdev.com:9981/#groups/1/general`) |
| `page.evaluate(() => ...)`                    | Run JS in browser context                                                            |
| `page.keyboard.press("Escape")`               | Dismiss popovers/modals                                                              |
