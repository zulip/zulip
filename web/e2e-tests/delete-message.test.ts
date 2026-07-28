import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function open_actions_menu_for_last_message(page: Page): Promise<string> {
    const msg = (await page.$$(".message-list .message_row")).at(-1);
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
    return id;
}

async function delete_message_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(
        `.message-list[data-message-list-id='${message_list_id}'] .message_row`,
        {visible: true},
    );
    // Assert that there is only one message list.
    assert.equal((await page.$$(".message-list")).length, 1);
    const messages_quantity = (await page.$$(".message-list .message_row")).length;

    // Open the action menu on the last message and pick "Delete
    // messages". This enters selection mode with that message
    // already selected.
    const last_message_id = await open_actions_menu_for_last_message(page);
    await page.click(".delete_message");
    await page.waitForSelector("#selection_mode_banner.selection-mode-banner-visible");

    // Confirm the deletion. The messages are deleted immediately for
    // everyone; the server's delete event removes the row from the DOM,
    // and an undo toast appears.
    await page.click("#selection_mode_banner .selection-mode-delete-button");
    await page.waitForSelector(`#${CSS.escape(last_message_id)}`, {hidden: true});
    assert.equal((await page.$$(".message-list .message_row")).length, messages_quantity - 1);

    const undo_button = await page.waitForSelector(
        "#message_delete_undo_banner .message-delete-undo-button",
        {visible: true},
    );
    assert.ok(undo_button !== null);

    // Undo restores the message from the archive; it reappears via the
    // server's restored_message event, with its original ID.
    await undo_button.click();
    await page.waitForSelector(`#${CSS.escape(last_message_id)}`, {visible: true});
    assert.equal((await page.$$(".message-list .message_row")).length, messages_quantity);
}

await common.run_test(delete_message_test);
