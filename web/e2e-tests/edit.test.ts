import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function trigger_edit_last_message(page: Page): Promise<void> {
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
    await page.waitForSelector(".popover_edit_message", {visible: true});
    await page.click(".popover_edit_message");
    await page.waitForSelector(".message_edit_content", {visible: true});
}

async function edit_stream_message(page: Page, content: string): Promise<void> {
    await trigger_edit_last_message(page);

    await common.clear_and_type(page, ".message_edit_content", content);
    await page.click(".message_edit_save");

    await common.wait_for_fully_processed_message(page, content);
}

async function test_stream_message_edit(page: Page): Promise<void> {
    await common.send_message(page, "stream", {
        stream_name: "Verona",
        topic: "edits",
        content: "test editing",
    });

    await edit_stream_message(page, "test edited");

    const message_list_id = await common.get_current_msg_list_id(page, false);
    await common.check_messages_sent(page, message_list_id, [["Verona > edits", ["test edited"]]]);
}

async function test_edit_message_with_slash_me(page: Page): Promise<void> {
    const last_message_xpath = `(//*[${common.has_class_x("message-list")}]//*[${common.has_class_x(
        "messagebox",
    )}])[last()]`;

    await common.send_message(
        page,
        "stream",
        {
            stream_name: "Verona",
            topic: "edits",
            content: "/me test editing a message with me",
        },
        // We already narrow in test_stream_message_edit.
        false,
    );
    await page.waitForSelector(
        `xpath/${last_message_xpath}//*[${common.has_class_x(
            "status-message",
        )} and text()="test editing a message with me"]`,
    );
    await page.waitForSelector(
        `xpath/${last_message_xpath}//*[${common.has_class_x(
            "sender_name",
        )} and normalize-space()="Desdemona"]`,
    );

    await edit_stream_message(page, "/me test edited a message with me");

    await page.waitForSelector(
        `xpath/${last_message_xpath}//*[${common.has_class_x(
            "status-message",
        )} and text()="test edited a message with me"]`,
    );
    await page.waitForSelector(
        `xpath/${last_message_xpath}//*[${common.has_class_x(
            "sender_name",
        )} and normalize-space()="Desdemona"]`,
    );
}

async function test_edit_private_message(page: Page): Promise<void> {
    await common.send_message(page, "private", {
        recipient: "cordelia@zulip.com",
        content: "test editing pm",
    });
    await trigger_edit_last_message(page);

    await common.clear_and_type(page, ".message_edit_content", "test edited pm");
    await page.click(".message_edit_save");
    await common.wait_for_fully_processed_message(page, "test edited pm");

    const message_list_id = await common.get_current_msg_list_id(page, false);
    await common.check_messages_sent(page, message_list_id, [
        ["You and Cordelia, Lear's daughter", ["test edited pm"]],
    ]);
}

async function edit_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(
        `.message-list[data-message-list-id='${message_list_id}'] .message_row`,
        {visible: true},
    );

    await test_stream_message_edit(page);
    await test_edit_message_with_slash_me(page);
    await test_edit_private_message(page);
}

common.run_test(edit_tests);
