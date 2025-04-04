import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function wait_for_drafts_to_disappear(page: Page): Promise<void> {
    await page.waitForSelector("#draft_overlay.show", {hidden: true});
}

async function wait_for_drafts_to_appear(page: Page): Promise<void> {
    await page.waitForSelector("#draft_overlay.show");
}

async function get_drafts_count(page: Page): Promise<number> {
    return await page.$$eval("#drafts_table .overlay-message-row", (drafts) => drafts.length);
}

const drafts_button = ".top_left_drafts";
const drafts_overlay = "#draft_overlay";

async function test_empty_drafts(page: Page): Promise<void> {
    await page.waitForSelector(drafts_button, {visible: true});
    await page.click(drafts_button);

    await wait_for_drafts_to_appear(page);
    await page.waitForSelector(drafts_overlay, {visible: true});
    assert.strictEqual(await common.get_text_from_selector(page, ".drafts-list"), "No drafts.");

    await page.click(`${drafts_overlay} .exit`);
    await wait_for_drafts_to_disappear(page);
}

async function create_stream_message_draft(page: Page): Promise<void> {
    console.log("Creating stream message draft");
    await page.keyboard.press("KeyC");
    await page.waitForSelector("#stream_message_recipient_topic", {visible: true});
    await common.select_stream_in_compose_via_dropdown(page, "Denmark");
    await common.fill_form(page, "form#send_message_form", {
        content: "Test stream message.",
    });
    await page.type("#stream_message_recipient_topic", "tests", {delay: 100});
    await page.click("#compose_close");
}

async function test_restore_stream_message_draft_by_opening_compose_box(page: Page): Promise<void> {
    await page.click(".search_icon");
    await page.waitForSelector("#search_query", {visible: true});
    await common.clear_and_type(page, "#search_query", "stream:Denmark topic:tests");
    await page.keyboard.press("Enter");
    // Wait for narrow to complete.
    const wait_for_change = true;
    await common.get_current_msg_list_id(page, wait_for_change);
    await page.keyboard.press("Enter");

    await page.click("#left_bar_compose_reply_button_big");
    await page.waitForSelector("#send_message_form", {visible: true});

    await common.check_compose_state(page, {
        stream_name: "Denmark",
        topic: "tests",
        content: "Test stream message. ",
    });
    await page.click("#compose_close");
    await page.waitForSelector("#send_message_form", {visible: false});
}

async function create_private_message_draft(page: Page): Promise<void> {
    console.log("Creating direct message draft");
    await page.keyboard.press("KeyX");
    await page.waitForSelector("#private_message_recipient", {visible: true});
    await common.fill_form(page, "form#send_message_form", {content: "Test direct message."});
    await common.pm_recipient.set(page, "cordelia@zulip.com");
    await common.pm_recipient.set(page, "hamlet@zulip.com");
}

async function test_restore_private_message_draft_by_opening_composebox(page: Page): Promise<void> {
    await page.click("#left_bar_compose_reply_button_big");
    await page.waitForSelector("#private_message_recipient", {visible: true});

    await common.check_form_contents(page, "form#send_message_form", {
        content: "Test direct message. ",
    });
    await page.click("#compose_close");
    await page.waitForSelector("#private_message_recipient", {visible: false});
}

async function open_compose_markdown_preview(page: Page): Promise<void> {
    const new_conversation_button = "#new_conversation_button";
    await page.waitForSelector(new_conversation_button, {visible: true});
    await page.click(new_conversation_button);

    const markdown_preview_button = "#compose .markdown_preview"; // eye icon.
    await page.waitForSelector(markdown_preview_button, {visible: true});
    await page.click(markdown_preview_button);
}

async function open_drafts_after_markdown_preview(page: Page): Promise<void> {
    await open_compose_markdown_preview(page);
    await page.waitForSelector(drafts_button, {visible: true});
    await page.click(drafts_button);
    await wait_for_drafts_to_appear(page);
}

async function test_previously_created_drafts_rendered(page: Page): Promise<void> {
    const drafts_count = await get_drafts_count(page);
    assert.strictEqual(drafts_count, 2, "Drafts improperly loaded.");
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row .message_header_stream .stream_label",
        ),
        "Denmark",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row .message_header_stream .stream_topic",
        ),
        "tests",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row:nth-last-child(2) .rendered_markdown.restore-overlay-message",
        ),
        "Test direct message.",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row .message_header_private_message .stream_label",
        ),
        "You and Cordelia, Lear's daughter, King Hamlet",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row:last-child .rendered_markdown.restore-overlay-message",
        ),
        "Test stream message.",
    );
}

async function test_restore_message_draft_via_draft_overlay(page: Page): Promise<void> {
    console.log("Restoring stream message draft");
    await page.click("#drafts_table .message_row:not(.private-message) .restore-overlay-message");
    await wait_for_drafts_to_disappear(page);
    await page.waitForSelector("#stream_message_recipient_topic", {visible: true});
    await page.waitForSelector("#preview_message_area", {hidden: true});
    await common.check_compose_state(page, {
        stream_name: "Denmark",
        topic: "tests",
        content: "Test stream message.",
    });
    assert.strictEqual(
        await common.get_text_from_selector(page, "title"),
        "#Denmark > tests - Zulip Dev - Zulip",
        "Didn't narrow to the right topic.",
    );
}

async function edit_stream_message_draft(page: Page): Promise<void> {
    await common.select_stream_in_compose_via_dropdown(page, "Denmark");
    await common.fill_form(page, "form#send_message_form", {
        content: "Updated stream message",
    });
    await page.click("#compose_close");
}

async function test_edited_draft_message(page: Page): Promise<void> {
    await page.waitForSelector(drafts_button, {visible: true});
    await page.click(drafts_button);

    await wait_for_drafts_to_appear(page);
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row .message_header_stream .stream_label",
        ),
        "Denmark",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row .message_header_stream .stream_topic",
        ),
        "tests",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row .message_row:not(.private-message) .rendered_markdown.restore-overlay-message",
        ),
        "Updated stream message",
    );
}

async function test_restore_private_message_draft_via_draft_overlay(page: Page): Promise<void> {
    console.log("Restoring direct message draft.");
    await page.click(".message_row.private-message .restore-overlay-message");
    await wait_for_drafts_to_disappear(page);
    await page.waitForSelector("#compose-direct-recipient", {visible: true});
    await common.check_compose_state(page, {
        content: "Test direct message.",
    });
    const cordelia_internal_email = await common.get_internal_email_from_name(
        page,
        common.fullname.cordelia,
    );
    const hamlet_internal_email = await common.get_internal_email_from_name(
        page,
        common.fullname.hamlet,
    );
    await common.pm_recipient.expect(page, `${cordelia_internal_email},${hamlet_internal_email}`);
    assert.strictEqual(
        await common.get_text_from_selector(page, "title"),
        "Cordelia, Lear's daughter and King Hamlet - Zulip Dev - Zulip",
        "Didn't narrow to the direct messages with cordelia and hamlet",
    );
    await page.click("#compose_close");
}

async function test_delete_draft(page: Page): Promise<void> {
    console.log("Deleting draft");
    await page.waitForSelector(drafts_button, {visible: true});
    await page.click(drafts_button);
    await wait_for_drafts_to_appear(page);
    await page.click("#drafts_table .message_row.private-message .delete-overlay-message");
    const drafts_count = await get_drafts_count(page);
    assert.strictEqual(drafts_count, 1, "Draft not deleted.");
    await page.waitForSelector("#drafts_table .message_row.private-message", {hidden: true});
    await page.click(`${drafts_overlay} .exit`);
    await wait_for_drafts_to_disappear(page);
    await page.click("body");
}

async function test_save_draft_by_reloading(page: Page): Promise<void> {
    console.log("Saving draft by reloading.");
    await page.keyboard.press("KeyX");
    await page.waitForSelector("#compose-direct-recipient", {visible: true});
    await common.fill_form(page, "form#send_message_form", {
        content: "Test direct message draft.",
    });
    await common.pm_recipient.set(page, "cordelia@zulip.com");
    await page.reload();

    // Reloading into a direct messages narrow opens compose box.
    await page.waitForSelector("#compose-textarea", {visible: true});
    await page.click("#compose_close");

    console.log("Reloading finished. Opening drafts again now.");
    await page.waitForSelector(drafts_button, {visible: true});
    await page.click(drafts_button);

    console.log("Checking drafts survived after the reload");
    await wait_for_drafts_to_appear(page);
    const drafts_count = await get_drafts_count(page);
    assert.strictEqual(drafts_count, 2, "All drafts aren't loaded.");
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row .message_header_private_message .stream_label",
        ),
        "You and Cordelia, Lear's daughter",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            "#drafts_table .overlay-message-row:nth-last-child(2) .rendered_markdown.restore-overlay-message",
        ),
        "Test direct message draft.",
    );
}

async function test_delete_draft_on_clearing_text(page: Page): Promise<void> {
    console.log("Deleting draft by clearing compose box textarea.");
    await page.click("#drafts_table .message_row:not(.private-message) .restore-overlay-message");
    await wait_for_drafts_to_disappear(page);
    await page.waitForSelector("#send_message_form", {visible: true});
    await common.fill_form(page, "form#send_message_form", {content: ""});
    await page.click("#compose_close");
    await page.waitForSelector("#send_message_form", {hidden: true});
    await page.click(drafts_button);
    await wait_for_drafts_to_appear(page);
    const drafts_count = await get_drafts_count(page);
    assert.strictEqual(drafts_count, 1, "Draft not deleted.");
}

async function drafts_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(
        `.message-list[data-message-list-id='${message_list_id}'] .message_row`,
        {visible: true},
    );

    await test_empty_drafts(page);

    await create_stream_message_draft(page);
    await test_restore_stream_message_draft_by_opening_compose_box(page);

    // Send a private message so that the draft we create is
    // for an existing conversation.
    await common.send_message(page, "private", {
        recipient: "cordelia@zulip.com, hamlet@zulip.com",
        content: "howdy doo",
    });
    await create_private_message_draft(page);
    // Close and try restoring it by opening the composebox again.
    await page.click("#compose_close");
    await test_restore_private_message_draft_by_opening_composebox(page);

    await open_drafts_after_markdown_preview(page);
    await test_previously_created_drafts_rendered(page);

    await test_restore_message_draft_via_draft_overlay(page);
    await edit_stream_message_draft(page);
    await test_edited_draft_message(page);

    await test_restore_private_message_draft_via_draft_overlay(page);
    await test_delete_draft(page);
    await test_save_draft_by_reloading(page);
    await test_delete_draft_on_clearing_text(page);
}

common.run_test(drafts_test);
