import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function check_compose_form_empty(page: Page): Promise<void> {
    await common.check_compose_state(page, {
        stream_name: "",
        topic: "",
        content: "",
    });
}

async function close_compose_box(page: Page): Promise<void> {
    const recipient_dropdown_visible = (await page.$(".dropdown-list-container")) !== null;

    if (recipient_dropdown_visible) {
        await page.keyboard.press("Escape");
        await page.waitForSelector(".dropdown-list-container", {hidden: true});
    }
    await page.keyboard.press("Escape");
    await page.waitForSelector("#compose-textarea", {hidden: true});
}

function get_message_selector(text: string): string {
    return `xpath/(//p[text()='${text}'])[last()]`;
}

async function test_send_messages(page: Page): Promise<void> {
    const initial_msgs_count = (await page.$$(".message-list .message_row")).length;

    await common.send_multiple_messages(page, [
        {stream_name: "Verona", topic: "Reply test", content: "Compose stream reply test"},
        {recipient: "cordelia@zulip.com", content: "Compose direct message reply test"},
    ]);

    assert.equal((await page.$$(".message-list .message_row")).length, initial_msgs_count + 2);
}

async function test_stream_compose_keyboard_shortcut(page: Page): Promise<void> {
    await page.keyboard.press("KeyC");
    await page.waitForSelector("#stream_message_recipient_topic", {visible: true});
    await check_compose_form_empty(page);
    await close_compose_box(page);
}

async function test_private_message_compose_shortcut(page: Page): Promise<void> {
    await page.keyboard.press("KeyX");
    await page.waitForSelector("#private_message_recipient", {visible: true});
    await common.pm_recipient.expect(page, "");
    await close_compose_box(page);
}

async function test_keyboard_shortcuts(page: Page): Promise<void> {
    await test_stream_compose_keyboard_shortcut(page);
    await test_private_message_compose_shortcut(page);
}

async function test_reply_by_click_prepopulates_stream_topic_names(page: Page): Promise<void> {
    const stream_message_selector = get_message_selector("Compose stream reply test");
    const stream_message = await page.waitForSelector(stream_message_selector, {visible: true});
    assert.ok(stream_message !== null);
    // we chose only the last element make sure we don't click on any duplicates.
    await stream_message.click();
    await common.check_compose_state(page, {
        stream_name: "Verona",
        topic: "Reply test",
        content: "",
    });
    await close_compose_box(page);
}

async function test_reply_by_click_prepopulates_private_message_recipient(
    page: Page,
): Promise<void> {
    const private_message = await page.$(get_message_selector("Compose direct message reply test"));
    assert.ok(private_message !== null);
    await private_message.click();
    await page.waitForSelector("#private_message_recipient", {visible: true});
    const email = await common.get_internal_email_from_name(page, "cordelia");
    assert(email !== undefined);
    await common.pm_recipient.expect(page, email);
    await close_compose_box(page);
}

async function test_reply_with_r_shortcut(page: Page): Promise<void> {
    // The last message(private) in the narrow is currently selected as a result of previous tests.
    // Now we go up and open compose box with r key.
    await page.keyboard.press("KeyK");
    await page.keyboard.press("KeyR");
    await common.check_compose_state(page, {
        stream_name: "Verona",
        topic: "Reply test",
        content: "",
    });
}

async function test_open_close_compose_box(page: Page): Promise<void> {
    await page.waitForSelector("#stream_message_recipient_topic", {visible: true});
    await close_compose_box(page);
    await page.waitForSelector("#stream_message_recipient_topic", {hidden: true});

    await page.keyboard.press("KeyX");
    await page.waitForSelector("#compose-direct-recipient", {visible: true});
    await close_compose_box(page);
    await page.waitForSelector("#compose-direct-recipient", {hidden: true});
}

async function test_narrow_to_private_messages_with_cordelia(page: Page): Promise<void> {
    const you_and_cordelia_selector =
        '*[data-tippy-content="Go to direct messages with Cordelia, Lear\'s daughter"]';
    // For some unknown reason page.click() isn't working here.
    await page.evaluate((selector: string) => {
        document.querySelector<HTMLElement>(selector)!.click();
    }, you_and_cordelia_selector);
    const cordelia_user_id = await common.get_user_id_from_name(page, "Cordelia, Lear's daughter");
    const pm_list_selector = `li[data-user-ids-string="${cordelia_user_id}"].dm-list-item.active-sub-filter`;
    await page.waitForSelector(pm_list_selector, {visible: true});
    await close_compose_box(page);

    await page.keyboard.press("KeyC");
    await page.waitForSelector("#compose", {visible: true});
    await page.waitForSelector(`.dropdown-list-container .list-item`, {visible: true});
    await close_compose_box(page);
}

async function test_send_multirecipient_pm_from_cordelia_pm_narrow(page: Page): Promise<void> {
    const recipients = ["cordelia@zulip.com", "othello@zulip.com"];
    const multiple_recipients_pm = "A huddle to check spaces";
    await common.send_message(page, "private", {
        recipient: recipients.join(", "),
        outside_view: true,
        content: multiple_recipients_pm,
    });

    // Go back to the combined feed view and make sure all messages are loaded.
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");

    await page.waitForSelector(".message-list .message_row", {visible: true});
    // Assert that there is only one message list.
    assert.equal((await page.$$(".message-list")).length, 1);
    const pm = await page.waitForSelector(
        `xpath/(//*[${common.has_class_x(
            "messagebox",
        )} and contains(normalize-space(), "${multiple_recipients_pm}") and count(.//*[${common.has_class_x(
            "star",
        )}])>0])[last()]`,
    );
    assert.ok(pm !== null);
    await pm.click();
    await page.waitForSelector("#compose-textarea", {visible: true});
    const recipient_internal_emails = [
        await common.get_internal_email_from_name(page, "othello"),
        await common.get_internal_email_from_name(page, "cordelia"),
    ].join(",");
    await common.pm_recipient.expect(page, recipient_internal_emails);
}

const markdown_preview_button = "#compose .markdown_preview";
const markdown_preview_hide_button = "#compose .undo_markdown_preview";

async function test_markdown_preview_buttons_visibility(page: Page): Promise<void> {
    await page.waitForSelector(markdown_preview_button, {visible: true});
    await page.waitForSelector(markdown_preview_hide_button, {hidden: true});

    // verify if Markdown preview button works.
    await page.click(markdown_preview_button);
    await page.waitForSelector(markdown_preview_button, {hidden: true});
    await page.waitForSelector(markdown_preview_hide_button, {visible: true});

    // verify if hide button works.
    await page.click(markdown_preview_hide_button);
    await page.waitForSelector(markdown_preview_button, {visible: true});
    await page.waitForSelector(markdown_preview_hide_button, {hidden: true});
}

async function test_markdown_preview_without_any_content(page: Page): Promise<void> {
    await page.click("#compose .markdown_preview");
    await page.waitForSelector("#compose .undo_markdown_preview", {visible: true});
    const markdown_preview_element = await page.$("#compose .preview_content");
    assert.ok(markdown_preview_element);
    assert.equal(
        await page.evaluate((element: Element) => element.textContent, markdown_preview_element),
        "Nothing to preview",
    );
    await page.click("#compose .undo_markdown_preview");
}

async function test_markdown_rendering(page: Page): Promise<void> {
    await page.waitForSelector("#compose .markdown_preview", {visible: true});
    assert.equal(await common.get_text_from_selector(page, "#compose .preview_content"), "");
    await common.fill_form(page, 'form[action^="/json/messages"]', {
        content: "**Markdown preview** >> Test for Markdown preview",
    });
    await page.click("#compose .markdown_preview");
    const preview_content = await page.waitForSelector(
        `xpath///*[@id="compose"]//*[${common.has_class_x(
            "preview_content",
        )} and normalize-space()!=""]`,
        {visible: true},
    );
    assert.ok(preview_content !== null);
    const expected_markdown_html =
        "<p><strong>Markdown preview</strong> &gt;&gt; Test for Markdown preview</p>";
    assert.equal(
        await (await preview_content.getProperty("innerHTML")).jsonValue(),
        expected_markdown_html,
    );
}

async function test_markdown_preview(page: Page): Promise<void> {
    await test_markdown_preview_buttons_visibility(page);
    await test_markdown_preview_without_any_content(page);
    await test_markdown_rendering(page);
}

async function compose_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await page.waitForSelector(".message-list .message_row", {visible: true});
    await test_send_messages(page);
    await test_keyboard_shortcuts(page);
    await test_reply_by_click_prepopulates_stream_topic_names(page);
    await test_reply_by_click_prepopulates_private_message_recipient(page);
    await test_reply_with_r_shortcut(page);
    await test_open_close_compose_box(page);
    await test_narrow_to_private_messages_with_cordelia(page);
    await test_send_multirecipient_pm_from_cordelia_pm_narrow(page);
    await test_markdown_preview(page);
}

common.run_test(compose_tests);
