"use strict";

const common = require("../puppeteer_lib/common");

async function click_delete_and_return_last_msg_id(page) {
    return await page.evaluate(() => {
        const msg = $("#zhome .message_row").last();
        msg.find(".info").trigger("click");
        $(".delete_message").trigger("click");
        return msg.attr("id");
    });
}

async function delete_message_test(page) {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
    const messages_quantitiy = await page.evaluate(() => $("#zhome .message_row").length);
    const last_message_id = await click_delete_and_return_last_msg_id(page);

    await page.waitForSelector("#delete_message_modal", {visible: true});
    await page.click("#do_delete_message_button");
    await page.waitForSelector("#do_delete_message_spinner .loading_indicator_spinner", {
        visible: true,
    });
    await page.waitForSelector("#do_delete_message_button", {hidden: true});

    await page.waitForFunction(
        (expected_length) => $("#zhome .message_row").length === expected_length,
        {},
        messages_quantitiy - 1,
    );

    await common.assert_selector_doesnt_exist(page, last_message_id);
    await page.waitForSelector("#do_delete_message_spinner .loading_indicator_spinner", {
        hidden: true,
    });
}

common.run_test(delete_message_test);
