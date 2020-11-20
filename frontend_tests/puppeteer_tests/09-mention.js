"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

async function test_mention(page) {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
    await page.keyboard.press("KeyC");
    await page.waitForSelector("#compose", {visible: true});

    await common.fill_form(page, 'form[action^="/json/messages"]', {
        stream_message_recipient_stream: "Verona",
        stream_message_recipient_topic: "Test mention all",
    });
    await common.select_item_via_typeahead(page, "#compose-textarea", "@**all**", "all");
    await common.ensure_enter_does_not_send(page);

    console.log("Checking for all everyone warning");
    const stream_size = await page.evaluate(() => stream_data.get_sub("Verona").subscribers.size);
    const threshold = await page.evaluate(() => {
        compose.wildcard_mention_large_stream_threshold = 5;
        return compose.wildcard_mention_large_stream_threshold;
    });
    assert(stream_size > threshold);
    await page.click("#compose-send-button");

    await common.wait_for_text(
        page,
        ".compose-all-everyone-msg",
        "Are you sure you want to mention all",
    );
    await page.click(".compose-all-everyone-confirm");
    await page.waitForSelector(".compose-all-everyone-msg", {hidden: true});
    await page.waitForSelector("#compose-send-status", {hidden: true});

    await common.check_messages_sent(page, "zhome", [["Verona > Test mention all", ["@all"]]]);
    await common.log_out(page);
}

common.run_test(test_mention);
