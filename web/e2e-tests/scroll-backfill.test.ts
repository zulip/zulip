import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function test_rerender_preserves_selection_class(page: Page): Promise<void> {
    console.log("Sending messages");
    const msgs = [];
    for (let i = 0; i < 15; i += 1) {
        msgs.push({
            stream_name: "Verona",
            topic: "scroll rerender test",
            content: `rerender test message ${i}`,
        });
    }
    await common.send_multiple_messages(page, msgs);

    const has_class_before = await page.evaluate(
        () => document.querySelector(".selected_message") !== null,
    );
    assert.ok(has_class_before, ".selected_message class should exist before rerender");

    await page.evaluate(() => {
        zulip_test.current_msg_list!.view.rerender_preserving_scrolltop();
    });

    const has_class_after = await page.evaluate(
        () => document.querySelector(".selected_message") !== null,
    );
    assert.ok(has_class_after, ".selected_message class should be preserved after rerender");
}

async function scroll_backfill_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await common.get_current_msg_list_id(page, true);
    await test_rerender_preserves_selection_class(page);
}

await common.run_test(scroll_backfill_tests);
