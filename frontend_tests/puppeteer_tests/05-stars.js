"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

const message = "test star";

async function stars_count(page) {
    return await page.evaluate(() => $("#zhome .fa-star:not(.empty-star)").length);
}

async function toggle_test_star_message(page) {
    await page.evaluate((message) => {
        const msg = $(`.message_content:contains(${message}):visible`).last();
        if (msg.length !== 1) {
            throw new Error("cannot find test star message");
        }

        const star_icon = msg.closest(".messagebox").find(".star");
        if (star_icon.length !== 1) {
            throw new Error("cannot find star icon");
        }

        star_icon.trigger("click");
    }, message);
}

async function test_narrow_to_starred_messages(page) {
    await page.click('a[href^="#narrow/is/starred"]');
    await common.check_messages_sent(page, "zfilt", [["Verona > stars", [message]]]);

    // Go back to all messages narrow.
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
}

async function stars_test(page) {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
    await common.send_message(page, "stream", {
        stream: "Verona",
        topic: "stars",
        content: message,
    });

    assert.strictEqual(await stars_count(page), 0, "Unexpected already starred message(s).");

    await toggle_test_star_message(page);
    await page.waitForSelector("#zhome .fa-star", {visible: true});
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
