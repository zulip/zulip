import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function click_delete_and_return_last_msg_id(page: Page): Promise<string> {
    const msg = (await page.$$("#zhome .message_row")).at(-1);
    assert.ok(msg !== undefined);
    const id = await (await msg.getProperty("id")).jsonValue();
    await msg.hover();
    const info = await page.waitForSelector(
        `#${CSS.escape(id)} .message_control_button.actions_hover`,
        {visible: true},
    );
    assert.ok(info !== null);
    await info.click();
    await page.waitForSelector(".delete_message", {visible: true});
    await page.click(".delete_message");
    return id;
}

async function delete_message_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
    const messages_quantity = (await page.$$("#zhome .message_row")).length;
    const last_message_id = await click_delete_and_return_last_msg_id(page);

    await common.wait_for_micromodal_to_open(page);
    await page.evaluate(() => {
        document.querySelector<HTMLButtonElement>(".dialog_submit_button")?.click();
    });
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector(`#${CSS.escape(last_message_id)}`, {hidden: true});
    assert.equal((await page.$$("#zhome .message_row")).length, messages_quantity - 1);
}

common.run_test(delete_message_test);
