"use strict";

const assert = require("assert").strict;

const common = require("../puppeteer_lib/common");

const message = "test star";

async function stars_count(page) {
    return await page.evaluate(() => $("#zhome .fa-star:not(.empty-star)").length);
}

async function toggle_test_star_message(page) {
    const error = await page.evaluate((message) => {
        const msg = $(`.message_content:contains(${message}):visible`).last();
        if (msg.length !== 1) {
            return "cannot find test star message";
        }

        const star_icon = msg.closest(".messagebox").find(".star");
        if (star_icon.length !== 1) {
            return "cannot find star icon";
        }

        star_icon.trigger("click");
    }, message);

    assert(!error, "\n\nERROR:" + error);
}

async function test_narrow_to_starred_messages(page) {
    await page.click('a[href^="#narrow/is/starred"]');
    await common.check_messages_sent(page, "zhome", [["Verona > stars", [message]]]);

    // Go back to all messages narrow.
    await page.keyboard.press("Escape");
    await page.waitForSelector("#zhome .message_row", {visible: true});
}

async function stars_test(page) {
    await common.log_in(page);
    await common.send_message(page, "stream", {
        stream: "Verona",
        topic: "stars",
        content: message,
    });

    assert.strictEqual(await stars_count(page), 0, "Messages are starred initially.");

    await toggle_test_star_message(page);
    await page.waitForSelector("#zhome .fa-star", {visible: true});
    assert.strictEqual(await stars_count(page), 1, "Stars count isn't 1.");

    await test_narrow_to_starred_messages(page);

    await toggle_test_star_message(page);
    assert.strictEqual(await stars_count(page), 0, "Stars count not reduced to 0");
}

common.run_test(stars_test);
