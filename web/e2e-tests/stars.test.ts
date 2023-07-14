import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

const message = "test star";

async function stars_count(page: Page): Promise<number> {
    return (await page.$$("#zhome .zulip-icon-star-filled:not(.empty-star)")).length;
}

async function toggle_test_star_message(page: Page): Promise<void> {
    const messagebox = await page.waitForSelector(
        `xpath/(//*[@id="zhome"]//*[${common.has_class_x(
            "message_content",
        )} and normalize-space()="${message}"])[last()]/ancestor::*[${common.has_class_x(
            "messagebox",
        )}]`,
        {visible: true},
    );
    assert.ok(messagebox !== null);
    await messagebox.hover();

    const star_icon = await messagebox.waitForSelector(".star", {visible: true});
    assert.ok(star_icon !== null);
    await star_icon.click();
}

async function test_narrow_to_starred_messages(page: Page): Promise<void> {
    await page.click('#global_filters a[href^="#narrow/is/starred"]');
    await common.check_messages_sent(page, "zfilt", [["Verona > stars", [message]]]);

    // Go back to all messages narrow.
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
}

async function stars_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
    await common.send_message(page, "stream", {
        stream_name: "Verona",
        topic: "stars",
        content: message,
    });

    assert.strictEqual(await stars_count(page), 0, "Unexpected already starred message(s).");

    await toggle_test_star_message(page);
    await page.waitForSelector("#zhome .zulip-icon-star-filled", {visible: true});
    assert.strictEqual(
        await stars_count(page),
        1,
        "Failed to ensure 1 starred message after change.",
    );

    await test_narrow_to_starred_messages(page);
    assert.strictEqual(
        await stars_count(page),
        1,
        "Message star disappeared after switching views.",
    );

    await toggle_test_star_message(page);
    assert.strictEqual(await stars_count(page), 0, "Message was not unstarred correctly.");
}

common.run_test(stars_test);
