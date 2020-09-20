"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

async function check_compose_form_empty(page) {
    await common.check_form_contents(page, "#send_message_form", {
        stream_message_recipient_stream: "",
        stream_message_recipient_topic: "",
        content: "",
    });
}

async function close_compose_box(page) {
    await page.keyboard.press("Escape");
    await page.waitForSelector("#compose-textarea", {hidden: true});
}

function get_message_xpath(text) {
    return `//p[text()='${text}']`;
}

function get_last_element(array) {
    return array.slice(-1)[0];
}

async function test_send_messages(page) {
    const initial_msgs_count = await page.evaluate(() => $("#zhome .message_row").length);

    await common.send_multiple_messages(page, [
        {stream: "Verona", topic: "Reply test", content: "Compose stream reply test"},
        {recipient: "cordelia@zulip.com", content: "Compose private message reply test"},
    ]);

    assert.equal(
        await page.evaluate(() => $("#zhome .message_row").length),
        initial_msgs_count + 2,
    );
}

async function test_stream_compose_keyboard_shortcut(page) {
    await page.keyboard.press("KeyC");
    await page.waitForSelector("#stream-message", {visible: true});
    await check_compose_form_empty(page);
    await close_compose_box(page);
}

async function test_private_message_compose_shortcut(page) {
    await page.keyboard.press("KeyX");
    await page.waitForSelector("#private_message_recipient", {visible: true});
    await common.pm_recipient.expect(page, "");
    await close_compose_box(page);
}

async function test_keyboard_shortcuts(page) {
    await test_stream_compose_keyboard_shortcut(page);
    await test_private_message_compose_shortcut(page);
}

async function test_reply_by_click_prepopulates_stream_topic_names(page) {
    const stream_message = get_last_element(
        await page.$x(get_message_xpath("Compose stream reply test")),
    );
    // we chose only the last element make sure we don't click on any duplicates.
    await stream_message.click();
    await common.check_form_contents(page, "#send_message_form", {
        stream_message_recipient_stream: "Verona",
        stream_message_recipient_topic: "Reply test",
        content: "",
    });
    await close_compose_box(page);
}

async function test_reply_by_click_prepopulates_private_message_recipient(page) {
    const private_message = get_last_element(
        await page.$x(get_message_xpath("Compose private message reply test")),
    );
    await private_message.click();
    await page.waitForSelector("#private_message_recipient", {visible: true});
    await common.pm_recipient.expect(
        page,
        await common.get_internal_email_from_name(page, "cordelia"),
    );
    await close_compose_box(page);
}

async function test_reply_with_r_shortcut(page) {
    // The last message(private) in the narrow is currently selected as a result of previous tests.
    // Now we go up and open compose box with r key.
    await page.keyboard.press("KeyK");
    await page.keyboard.press("KeyR");
    await common.check_form_contents(page, "#send_message_form", {
        stream_message_recipient_stream: "Verona",
        stream_message_recipient_topic: "Reply test",
        content: "",
    });
}

async function test_open_close_compose_box(page) {
    await page.waitForSelector("#stream-message", {visible: true});
    await close_compose_box(page);
    await page.waitForSelector("#stream-message", {hidden: true});

    await page.keyboard.press("KeyX");
    await page.waitForSelector("#private-message", {visible: true});
    await close_compose_box(page);
    await page.waitForSelector("#private-message", {hidden: true});
}

async function test_narrow_to_private_messages_with_cordelia(page) {
    const you_and_cordelia_selector =
        '*[title="Narrow to your private messages with Cordelia Lear"]';
    // For some unknown reason page.click() isn't working here.
    await page.evaluate(
        (selector) => document.querySelector(selector).click(),
        you_and_cordelia_selector,
    );
    const cordelia_user_id = await common.get_user_id_from_name(page, "Cordelia Lear");
    const pm_list_selector = `li[data-user-ids-string="${cordelia_user_id}"].expanded_private_message.active-sub-filter`;
    await page.waitForSelector(pm_list_selector, {visible: true});
    await close_compose_box(page);

    await page.keyboard.press("KeyC");
    await page.waitForSelector("#compose", {visible: true});
    await page.waitForFunction(
        () => document.activeElement === $(".compose_table #stream_message_recipient_stream")[0],
    );
    await close_compose_box(page);
}

async function test_send_multirecipient_pm_from_cordelia_pm_narrow(page) {
    const recipients = ["cordelia@zulip.com", "othello@zulip.com"];
    const multiple_recipients_pm = "A huddle to check spaces";
    const pm_selector = `.messagebox:contains('${multiple_recipients_pm}')`;
    await common.send_message(page, "private", {
        recipient: recipients.join(", "),
        outside_view: true,
        content: multiple_recipients_pm,
    });

    // Go back to all messages view and make sure all messages are loaded.
    await page.click(".top_left_all_messages");

    await page.waitForSelector("#zhome .message_row", {visible: true});
    await page.waitForFunction((selector) => $(selector).length !== 0, {}, pm_selector);
    await page.evaluate((selector) => {
        $(selector).slice(-1)[0].click();
    }, pm_selector);
    await page.waitForSelector("#compose-textarea", {visible: true});
    const recipient_internal_emails = [
        await common.get_internal_email_from_name(page, "othello"),
        await common.get_internal_email_from_name(page, "cordelia"),
    ].join(",");
    await common.pm_recipient.expect(page, recipient_internal_emails);
}

const markdown_preview_button = "#markdown_preview";
const markdown_preview_hide_button = "#undo_markdown_preview";

async function test_markdown_preview_buttons_visibility(page) {
    await page.waitForSelector(markdown_preview_button, {visible: true});
    await page.waitForSelector(markdown_preview_hide_button, {hidden: true});

    // verify if markdowm preview button works.
    await page.click(markdown_preview_button);
    await page.waitForSelector(markdown_preview_button, {hidden: true});
    await page.waitForSelector(markdown_preview_hide_button, {visible: true});

    // verify if write button works.
    await page.click(markdown_preview_hide_button);
    await page.waitForSelector(markdown_preview_button, {visible: true});
    await page.waitForSelector(markdown_preview_hide_button, {hidden: true});
}

async function test_markdown_preview_without_any_content(page) {
    await page.click("#markdown_preview");
    await page.waitForSelector("#undo_markdown_preview", {visible: true});
    const markdown_preview_element = await page.$("#preview_content");
    assert.equal(
        await page.evaluate((element) => element.textContent, markdown_preview_element),
        "Nothing to preview",
    );
    await page.click("#undo_markdown_preview");
}

async function test_markdown_rendering(page) {
    await page.waitForSelector("#markdown_preview", {visible: true});
    let markdown_preview_element = await page.$("#preview_content");
    assert.equal(
        await page.evaluate((element) => element.textContent, markdown_preview_element),
        "",
    );
    await common.fill_form(page, 'form[action^="/json/messages"]', {
        content: "**Markdown preview** >> Test for Markdown preview",
    });
    await page.click("#markdown_preview");
    await page.waitForSelector("#preview_content", {visible: true});
    const expected_markdown_html =
        "<p><strong>Markdown preview</strong> &gt;&gt; Test for Markdown preview</p>";
    await page.waitForFunction(() => $("#preview_content").html() !== "");
    markdown_preview_element = await page.$("#preview_content");
    assert.equal(
        await page.evaluate((element) => element.innerHTML, markdown_preview_element),
        expected_markdown_html,
    );
}

async function test_markdown_preview(page) {
    await test_markdown_preview_buttons_visibility(page);
    await test_markdown_preview_without_any_content(page);
    await test_markdown_rendering(page);
}

async function compose_tests(page) {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});
    await test_send_messages(page);
    await test_keyboard_shortcuts(page);
    await test_reply_by_click_prepopulates_stream_topic_names(page);
    await test_reply_by_click_prepopulates_private_message_recipient(page);
    await test_reply_with_r_shortcut(page);
    await test_open_close_compose_box(page);
    await test_narrow_to_private_messages_with_cordelia(page);
    await test_send_multirecipient_pm_from_cordelia_pm_narrow(page);
    await test_markdown_preview(page);
    await common.log_out(page);
}

common.run_test(compose_tests);
