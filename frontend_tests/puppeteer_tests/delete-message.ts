import type {Page} from "puppeteer";

import common from "../puppeteer_lib/common";

async function click_delete_and_return_last_msg_id(page: Page): Promise<string | undefined> {
    await common.open_message_actions_popovoer(page);
    return await page.evaluate(() => {
        $(".delete_message").trigger("click");
        return $("#zhome .message_row").last().attr("id");
    });
}

async function delete_message_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
    const messages_quantitiy = await page.evaluate(() => $("#zhome .message_row").length);
    const last_message_id = await click_delete_and_return_last_msg_id(page);

    await page.waitForSelector("#dialog_widget_modal", {visible: true});
    await page.click(".dialog_submit_button");
    await page.waitForSelector(".dialog_submit_button .loader", {
        visible: true,
    });
    await page.waitForSelector(".dialog_submit_button span", {hidden: true});

    await page.waitForFunction(
        (expected_length: number) => $("#zhome .message_row").length === expected_length,
        {},
        messages_quantitiy - 1,
    );

    await page.waitForSelector(`#${CSS.escape(last_message_id!)}`, {hidden: true});
    await page.waitForSelector(".dialog_submit_button .loader", {
        hidden: true,
    });
}

common.run_test(delete_message_test);
