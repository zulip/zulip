"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

async function wait_for_drafts_to_dissapear(page) {
    await page.waitForFunction(
        () => $("#draft_overlay").length === 0 || $("#draft_overlay").css("opacity") === "0",
    );
}

async function wait_for_drafts_to_appear(page) {
    await page.waitForFunction(
        () => $("#draft_overlay").length === 1 && $("#draft_overlay").css("opacity") === "1",
    );
}

async function get_drafts_count(page) {
    return await page.$$eval(".draft-row", (drafts) => drafts.length);
}

const drafts_button = ".compose_drafts_button";
const drafts_overlay = "#draft_overlay";
const drafts_button_in_compose = "#below-compose-content .drafts-link";

async function test_empty_drafts(page) {
    await page.waitForSelector(drafts_button, {visible: true});
    await page.click(drafts_button);

    await wait_for_drafts_to_appear(page);
    await page.waitForSelector(drafts_overlay, {visible: true});
    assert.strictEqual(await common.get_text_from_selector(page, ".drafts-list"), "No drafts.");

    await page.click(`${drafts_overlay} .exit`);
    await wait_for_drafts_to_dissapear(page);
}

async function create_stream_message_draft(page) {
    console.log("Creating Stream Message Draft");
    await page.keyboard.press("KeyC");
    await page.waitForSelector("#stream-message", {visible: true});
    await common.fill_form(page, "form#send_message_form", {
        stream_message_recipient_stream: "all",
        stream_message_recipient_topic: "tests",
        content: "Test stream message.",
    });
    await page.click("#compose_close");
}

async function create_private_message_draft(page) {
    console.log("Creating private message draft");
    await page.keyboard.press("KeyX");
    await page.waitForSelector("#private_message_recipient", {visible: true});
    await common.fill_form(page, "form#send_message_form", {content: "Test private message."});
    await common.pm_recipient.set(page, "cordelia@zulip.com");
    await common.pm_recipient.set(page, "hamlet@zulip.com");
    await page.click("#compose_close");
}

async function open_compose_markdown_preview(page) {
    const new_topic_button = "#left_bar_compose_stream_button_big";
    await page.waitForSelector(new_topic_button, {visible: true});
    await page.click(new_topic_button);

    const markdown_preview_button = "#markdown_preview"; // eye icon.
    await page.waitForSelector(markdown_preview_button, {visible: true});
    await page.click(markdown_preview_button);
}

async function open_drafts_through_compose(page) {
    await open_compose_markdown_preview(page);
    await page.waitForSelector(drafts_button_in_compose, {visible: true});
    await page.click(drafts_button_in_compose);
    await wait_for_drafts_to_appear(page);
}

async function test_previously_created_drafts_rendered(page) {
    const drafts_count = await get_drafts_count(page);
    assert.strictEqual(drafts_count, 2, "Drafts improperly loaded.");
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".draft-row .message_header_stream .stream_label",
        ),
        "all",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".draft-row .message_header_stream .stream_topic",
        ),
        "tests",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, ".rendered_markdown.restore-draft:first"),
        "Test private message.",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".draft-row .message_header_private_message .stream_label",
        ),
        "You and Cordelia Lear, King Hamlet",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, ".rendered_markdown.restore-draft:last"),
        "Test stream message.",
    );
}

async function test_restore_message_draft(page) {
    console.log("Restoring Stream Message Draft");
    await page.click("#drafts_table .message_row:not(.private-message) .restore-draft");
    await wait_for_drafts_to_dissapear(page);
    await page.waitForSelector("#stream-message", {visible: true});
    await page.waitForSelector("#preview_message_area", {hidden: true});
    await common.check_form_contents(page, "form#send_message_form", {
        stream_message_recipient_stream: "all",
        stream_message_recipient_topic: "tests",
        content: "Test stream message.",
    });
    assert.strictEqual(
        await common.get_text_from_selector(page, "title"),
        "tests - Zulip Dev - Zulip",
        "Didn't narrow to the right topic.",
    );
}

async function edit_stream_message_draft(page) {
    await common.fill_form(page, "form#send_message_form", {
        stream_message_recipient_stream: "all",
        stream_message_recipient_topic: "tests",
        content: "Updated Stream Message",
    });
    await page.click("#compose_close");
}

async function test_edited_draft_message(page) {
    await page.waitForSelector(drafts_button, {visible: true});
    await page.click(drafts_button);

    await wait_for_drafts_to_appear(page);
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".draft-row .message_header_stream .stream_label",
        ),
        "all",
    );
    assert.strictEqual(
        await common.get_text_from_selector(
            page,
            ".draft-row .message_header_stream .stream_topic",
        ),
        "tests",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, ".rendered_markdown.restore-draft:first"),
        "Updated Stream Message",
    );
}

async function test_restore_private_message_draft(page) {
    console.log("Restoring private message draft.");
    await page.click("#drafts_table .message_row.private-message .restore-draft");
    await wait_for_drafts_to_dissapear(page);
    await page.waitForSelector("#private-message", {visible: true});
    await common.check_form_contents(page, "form#send_message_form", {
        content: "Test private message.",
    });
    const cordelia_internal_email = await common.get_internal_email_from_name(page, "cordelia");
    const hamlet_internal_email = await common.get_internal_email_from_name(page, "hamlet");
    await common.pm_recipient.expect(page, `${cordelia_internal_email},${hamlet_internal_email}`);
    assert.strictEqual(
        await common.get_text_from_selector(page, "title"),
        "Cordelia Lear, King Hamlet - Zulip Dev - Zulip",
        "Didn't narrow to the private messages with cordelia and hamlet",
    );
    await page.click("#compose_close");
}

async function test_delete_draft(page) {
    console.log("Deleting draft");
    await page.waitForSelector(drafts_button, {visible: true});
    await page.click(drafts_button);
    await wait_for_drafts_to_appear(page);
    await page.click("#drafts_table .message_row.private-message .delete-draft");
    const drafts_count = await get_drafts_count(page);
    assert.strictEqual(drafts_count, 1, "Draft not deleted.");
    await common.assert_selector_doesnt_exist(page, "#drafts_table .message_row.private-message");
    await page.click(`${drafts_overlay} .exit`);
    await wait_for_drafts_to_dissapear(page);
    await page.click("body");
}

async function test_save_draft_by_reloading(page) {
    console.log("Saving draft by reloading.");
    await page.keyboard.press("KeyX");
    await page.waitForSelector("#private-message", {visible: true});
    await common.fill_form(page, "form#send_message_form", {
        content: "Test private message draft.",
    });
    await common.pm_recipient.set(page, "cordelia@zulip.com");
    await page.reload();

    // Reloading into a private messages narrow opens compose box.
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
            ".draft-row .message_header_private_message .stream_label",
        ),
        "You and Cordelia Lear",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, ".rendered_markdown.restore-draft:first"),
        "Test private message draft.",
    );
}

async function test_delete_draft_on_sending(page) {
    await page.click("#drafts_table .message_row.private-message .restore-draft");
    await wait_for_drafts_to_dissapear(page);
    await page.waitForSelector("#private-message", {visible: true});
    await common.ensure_enter_does_not_send(page);
    await page.waitForSelector("#compose-send-button", {visible: true});
    await page.click("#compose-send-button");

    await page.waitForSelector(drafts_button_in_compose, {visible: true});
    await page.click(drafts_button_in_compose);
    await wait_for_drafts_to_appear(page);
    const drafts_count = await get_drafts_count(page);
    assert.strictEqual(drafts_count, 1, "Draft wasn't cleared on sending.");
    await common.assert_selector_doesnt_exist(page, "#drafts_table .message_row.private-message");
}

async function drafts_test(page) {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});

    await test_empty_drafts(page);

    await create_stream_message_draft(page);
    await create_private_message_draft(page);
    await open_drafts_through_compose(page);
    await test_previously_created_drafts_rendered(page);

    await test_restore_message_draft(page);
    await edit_stream_message_draft(page);
    await test_edited_draft_message(page);

    await test_restore_private_message_draft(page);
    await test_delete_draft(page);
    await test_save_draft_by_reloading(page);
    await test_delete_draft_on_sending(page);
}

common.run_test(drafts_test);
