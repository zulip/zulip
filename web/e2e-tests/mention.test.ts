import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function test_mention(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await page.waitForSelector(".message-list .message_row", {visible: true});
    await page.keyboard.press("KeyC");
    await page.waitForSelector("#compose", {visible: true});

    await common.select_stream_in_compose_via_dropdown(page, "Verona");
    await common.fill_form(page, 'form[action^="/json/messages"]', {
        stream_message_recipient_topic: "Test mention all",
    });
    await common.select_item_via_typeahead(page, "#compose-textarea", "@**all", "all");
    await common.ensure_enter_does_not_send(page);

    console.log("Checking for all everyone warning");
    const stream_size = await page.evaluate(() =>
        zulip_test.get_subscriber_count(zulip_test.get_sub("Verona")!.stream_id),
    );
    const threshold = await page.evaluate(() => {
        zulip_test.set_wildcard_mention_threshold(5);
        return zulip_test.wildcard_mention_threshold;
    });
    assert.ok(stream_size > threshold);
    await page.click("#compose-send-button");

    await page.waitForSelector("#compose_banners .wildcard_warning", {visible: true});
    await page.click("#compose_banners .wildcard_warning .main-view-banner-action-button");
    await page.waitForSelector(".wildcard_warning", {hidden: true});

    const message_list_id = await common.get_current_msg_list_id(page, true);
    await common.check_messages_sent(page, message_list_id, [
        ["Verona > Test mention all", ["@all"]],
    ]);
}

common.run_test(test_mention);
