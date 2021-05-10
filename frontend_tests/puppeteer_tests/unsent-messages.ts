import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import common from "../puppeteer_lib/common";

type Message = {
    stream_message_recipient_stream: string;
    stream_message_recipient_topic: string;
    content: string;
};

async function _send_stream_message(
    page: Page,
    id_ends_with: string,
    params: Message,
): Promise<void> {
    await page.keyboard.press("KeyC");
    await common.fill_form(page, 'form[action^="/json/messages"]', params);
    await common.assert_compose_box_content(page, params.content);
    await common.ensure_enter_does_not_send(page);
    await page.waitForSelector("#compose-send-button", {visible: true});
    await page.click("#compose-send-button");

    // Here we do a cross-check that message is not acknowledged by the server
    // when we are offline with the following two conditions:
    // 1. star icon should not appear, as we don't add it until the server responds.
    // 2. message `zid` must be equal to the local id which is highest message ID with 0.01 added to it.

    assert(
        await page.evaluate(() => {
            const row = zulip_test.last_visible_row();
            return row.find(".star").length === 0;
        }),
    );

    const zid = await page.evaluate(() => {
        const row = zulip_test.last_visible_row();
        return row.attr("zid");
    });

    const pattern = new RegExp(`\\d+\\.${id_ends_with}`);
    assert(pattern.test(zid));
}

async function _send_message_when_server_unreachable(page: Page): Promise<void> {
    await _send_stream_message(page, "01", {
        stream_message_recipient_stream: "Denmark",
        stream_message_recipient_topic: "1st topic",
        content: "1st message in Denmark",
    });

    await _send_stream_message(page, "02", {
        stream_message_recipient_stream: "Venice",
        stream_message_recipient_topic: "2nd topic",
        content: "2nd message in Venice",
    });

    await _send_stream_message(page, "03", {
        stream_message_recipient_stream: "Verona",
        stream_message_recipient_topic: "3rd topic",
        content: "3rd message in Verona",
    });
}

async function send_unsent_messages(
    page: Page,
    content: string,
    send_this_msg: boolean,
): Promise<void> {
    await page.waitForXPath(
        '//*[@class="compose-unsent-message-msg" and contains(text(), "Following message was not sent to the server.")]',
    );

    await common.assert_compose_box_content(page, content);

    if (send_this_msg) {
        await page.click(".compose-unsent-message-confirm");
        await common.wait_for_fully_processed_message(page, content);
    } else {
        await page.click(".compose-unsent-message-cancel");
        const last_msg_content = await page.evaluate(() => {
            const last_msg = zulip_test.current_msg_list.last();
            return last_msg.raw_content;
        });
        assert(last_msg_content !== content);
    }
}

async function set_throttling_property(page: Page, is_offline: boolean): Promise<void> {
    // Connect to Chrome DevTools
    const client = await page.target().createCDPSession();
    // Set throttling property
    await client.send("Network.emulateNetworkConditions", {
        offline: is_offline,
        downloadThroughput: (200 * 1024) / 8,
        uploadThroughput: (200 * 1024) / 8,
        latency: 20,
    });
}

async function test_unsent_messages(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});

    // Going offline to send messages which won't be responded by the server.
    await set_throttling_property(page, true);
    await _send_message_when_server_unreachable(page);

    // Going online to send the last unsent messages.
    await set_throttling_property(page, false);
    await page.reload();
    await page.waitForSelector("#zhome .message_row", {visible: true});
    await page.waitForSelector("#compose-textarea", {visible: true});

    // Unsent messages must pop up in the order they were sent earlier.
    await send_unsent_messages(page, "1st message in Denmark", true);
    await send_unsent_messages(page, "2nd message in Venice", false);
    await send_unsent_messages(page, "3rd message in Verona", true);
    // After all the unsent messages are acknowledged, compose_unsent_messages
    // template should be no longer visible.
    await page.waitForSelector("#compose-unsent-message", {hidden: true});

    // Here we ensure that we don't get any other/older unsent messages on another reload.
    await page.reload();
    await page.waitForSelector("#zhome .message_row", {visible: true});
    await page.keyboard.press("KeyR");
    await page.waitForSelector("#compose-textarea", {visible: true});
    await common.assert_compose_box_content(page, "");
    await page.waitForSelector("#compose-unsent-message", {hidden: true});
}

common.run_test(test_unsent_messages);
