import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import {test_credentials} from "../../var/puppeteer/test_credentials";
import common from "../puppeteer_lib/common";

const OUTGOING_WEBHOOK_BOT_TYPE = "3";
const GENERIC_BOT_TYPE = "1";

const zuliprc_regex =
    /^data:application\/octet-stream;charset=utf-8,\[api]\nemail=.+\nkey=.+\nsite=.+\n$/;

async function get_decoded_url_in_selector(page: Page, selector: string): Promise<string> {
    return await page.evaluate(
        (selector: string) => decodeURIComponent($(selector).attr("href")!),
        selector,
    );
}

async function open_settings(page: Page): Promise<void> {
    const menu_selector = "#settings-dropdown";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);

    const settings_selector = '.dropdown-menu a[href="#settings"]';
    await page.waitForSelector(settings_selector, {visible: true});
    await page.click(settings_selector);

    await page.waitForSelector("#settings_content .profile-settings-form", {visible: true});
    const page_url = await common.page_url_with_fragment(page);
    assert.ok(
        page_url.includes("/#settings/"),
        `Page url: ${page_url} does not contain /#settings/`,
    );
}

async function test_change_full_name(page: Page): Promise<void> {
    await page.click("#full_name");

    const full_name_input_selector = 'input[name="full_name"]';
    await common.clear_and_type(page, full_name_input_selector, "New name");

    await page.click("#settings_content .profile-settings-form");
    await page.waitForSelector(".full-name-change-form .alert-success", {visible: true});
    await page.waitForFunction(() => $("#full_name").val() === "New name");
}

async function test_change_password(page: Page): Promise<void> {
    await page.click('[data-section="account-and-privacy"]');
    await page.click("#change_password");

    const change_password_button_selector = "#change_password_button";
    await page.waitForSelector(change_password_button_selector, {visible: true});

    // For some strange reason #change_password_modal:focus is not working with Firefox.
    // The below line is an alternative to that.
    // TODO: Replace the below line with `await page.waitForSelector("#change_password_modal:focus", {visible: true})`
    // when the above issue is resolved.
    await page.waitForFunction(() => document.activeElement!.id === "change_password_modal");
    await page.type("#old_password", test_credentials.default_user.password);
    test_credentials.default_user.password = "new_password";
    await page.type("#new_password", test_credentials.default_user.password);
    await page.click(change_password_button_selector);

    // On success the change password modal gets closed.
    await page.waitForFunction(() => $("#change_password_modal").attr("aria-hidden") === "true");
    await common.wait_for_modal_to_close(page);
}

async function test_get_api_key(page: Page): Promise<void> {
    const show_change_api_key_selector = "#api_key_button";
    await page.click(show_change_api_key_selector);

    const get_api_key_button_selector = "#get_api_key_button";
    await page.waitForSelector(get_api_key_button_selector, {visible: true});
    await page.waitForFunction(() => $(":focus").attr("id") === "api_key_modal");
    await common.fill_form(page, "#api_key_form", {
        password: test_credentials.default_user.password,
    });

    // When typing the password in Firefox, it shows "Not Secure" warning
    // which was hiding the Get API key button.
    // You can see the screenshot of it in https://github.com/zulip/zulip/pull/17136.
    // Focusing on it will remove the warning.
    await page.focus(get_api_key_button_selector);
    await page.click(get_api_key_button_selector);

    await page.waitForSelector("#show_api_key", {visible: true});
    const api_key = await common.get_text_from_selector(page, "#api_key_value");
    assert.match(api_key, /[\dA-Za-z]{32}/, "Incorrect API key format.");

    const download_zuliprc_selector = "#download_zuliprc";
    await page.click(download_zuliprc_selector);
    const zuliprc_decoded_url = await get_decoded_url_in_selector(page, download_zuliprc_selector);
    assert.match(zuliprc_decoded_url, zuliprc_regex, "Incorrect zuliprc file");
    await page.click("#api_key_modal .close");
    await common.wait_for_modal_to_close(page);
}

async function test_webhook_bot_creation(page: Page): Promise<void> {
    await common.fill_form(page, "#create_bot_form", {
        bot_name: "Bot 1",
        bot_short_name: "1",
        bot_type: OUTGOING_WEBHOOK_BOT_TYPE,
        payload_url: "http://hostname.example.com/bots/followup",
    });

    await page.click("#create_bot_button");

    const bot_email = "1-bot@zulip.testserver";
    const download_zuliprc_selector = `.download_bot_zuliprc[data-email="${CSS.escape(
        bot_email,
    )}"]`;
    const outgoing_webhook_zuliprc_regex =
        /^data:application\/octet-stream;charset=utf-8,\[api]\nemail=.+\nkey=.+\nsite=.+\ntoken=.+\n$/;

    await page.waitForSelector(download_zuliprc_selector, {visible: true});
    await page.click(download_zuliprc_selector);

    const zuliprc_decoded_url = await get_decoded_url_in_selector(page, download_zuliprc_selector);
    assert.match(
        zuliprc_decoded_url,
        outgoing_webhook_zuliprc_regex,
        "Incorrect outgoing webhook bot zulirc format",
    );
}

async function test_normal_bot_creation(page: Page): Promise<void> {
    await page.click(".add-a-new-bot-tab");
    await page.waitForSelector("#create_bot_button", {visible: true});

    await common.fill_form(page, "#create_bot_form", {
        bot_name: "Bot 2",
        bot_short_name: "2",
        bot_type: GENERIC_BOT_TYPE,
    });

    await page.click("#create_bot_button");

    const bot_email = "2-bot@zulip.testserver";
    const download_zuliprc_selector = `.download_bot_zuliprc[data-email="${CSS.escape(
        bot_email,
    )}"]`;

    await page.waitForSelector(download_zuliprc_selector, {visible: true});
    await page.click(download_zuliprc_selector);
    const zuliprc_decoded_url = await get_decoded_url_in_selector(page, download_zuliprc_selector);
    assert.match(zuliprc_decoded_url, zuliprc_regex, "Incorrect zuliprc format for bot.");
}

async function test_botserverrc(page: Page): Promise<void> {
    await page.click("#download_botserverrc");
    await page.waitForSelector('#download_botserverrc[href^="data:application"]', {visible: true});
    const botserverrc_decoded_url = await get_decoded_url_in_selector(
        page,
        "#download_botserverrc",
    );
    const botserverrc_regex =
        /^data:application\/octet-stream;charset=utf-8,\[]\nemail=.+\nkey=.+\nsite=.+\ntoken=.+\n$/;
    assert.match(botserverrc_decoded_url, botserverrc_regex, "Incorrect botserverrc format.");
}

async function test_edit_bot_form(page: Page): Promise<void> {
    const bot1_email = "1-bot@zulip.testserver";
    const bot1_edit_btn = `.open_edit_bot_form[data-email="${CSS.escape(bot1_email)}"]`;
    await page.click(bot1_edit_btn);

    const edit_form_selector = `.edit_bot_form[data-email="${CSS.escape(bot1_email)}"]`;
    await page.waitForSelector(edit_form_selector, {visible: true});
    const name_field_selector = edit_form_selector + " [name=bot_name]";
    assert.equal(
        await page.$eval(name_field_selector, (el) => (el as HTMLInputElement).value),
        "Bot 1",
    );

    await common.fill_form(page, edit_form_selector, {bot_name: "Bot one"});
    const save_btn_selector = edit_form_selector + " .edit_bot_button";
    await page.click(save_btn_selector);

    // The form gets closed on saving. So, assert it's closed by waiting for it to be hidden.
    await page.waitForSelector("#edit_bot_modal", {hidden: true});

    await page.waitForXPath(
        `//*[@class="btn open_edit_bot_form tippy-zulip-tooltip" and @data-email="${bot1_email}"]/ancestor::*[@class="details"]/*[@class="name" and text()="Bot one"]`,
    );

    await common.wait_for_modal_to_close(page);
}

async function test_invalid_edit_bot_form(page: Page): Promise<void> {
    const bot1_email = "1-bot@zulip.testserver";
    const bot1_edit_btn = `.open_edit_bot_form[data-email="${CSS.escape(bot1_email)}"]`;
    await page.click(bot1_edit_btn);

    const edit_form_selector = `.edit_bot_form[data-email="${CSS.escape(bot1_email)}"]`;
    await page.waitForSelector(edit_form_selector, {visible: true});
    const name_field_selector = edit_form_selector + " [name=bot_name]";
    assert.equal(
        await page.$eval(name_field_selector, (el) => (el as HTMLInputElement).value),
        "Bot one",
    );

    await common.fill_form(page, edit_form_selector, {bot_name: "Bot 2"});
    const save_btn_selector = edit_form_selector + " .edit_bot_button";
    await page.click(save_btn_selector);

    // The form should not get closed on saving. Errors should be visible on the form.
    await page.waitForSelector("#edit_bot_modal", {visible: true});
    await page.waitForSelector(".bot_edit_errors", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "div.bot_edit_errors"),
        "Name is already in use!",
    );
    await page.click("button.cancel_bot_button");
    await page.waitForSelector("#edit_bot_modal", {hidden: true});

    await page.waitForXPath(
        `//*[@class="btn open_edit_bot_form tippy-zulip-tooltip" and @data-email="${bot1_email}"]/ancestor::*[@class="details"]/*[@class="name" and text()="Bot one"]`,
    );

    await common.wait_for_modal_to_close(page);
}

async function test_your_bots_section(page: Page): Promise<void> {
    await page.click('[data-section="your-bots"]');
    await test_webhook_bot_creation(page);
    await test_normal_bot_creation(page);
    await test_botserverrc(page);
    await test_edit_bot_form(page);
    await test_invalid_edit_bot_form(page);
}

const alert_word_status_selector = "#alert_word_status";

async function add_alert_word(page: Page, word: string): Promise<void> {
    await page.type("#create_alert_word_name", word);
    await page.click("#create_alert_word_button");
}

async function check_alert_word_added(page: Page, word: string): Promise<void> {
    const added_alert_word_selector = `.alert-word-item[data-word='${CSS.escape(word)}']`;
    await page.waitForSelector(added_alert_word_selector, {visible: true});
}

async function get_alert_words_status_text(page: Page): Promise<string> {
    await page.waitForSelector(alert_word_status_selector, {visible: true});
    const status_text = await common.get_text_from_selector(page, ".alert_word_status_text");
    return status_text;
}

async function close_alert_words_status(page: Page): Promise<void> {
    const status_close_btn = ".close-alert-word-status";
    await page.click(status_close_btn);
    await page.waitForSelector(alert_word_status_selector, {hidden: true});
}

async function test_and_close_alert_word_added_successfully_status(
    page: Page,
    word: string,
): Promise<void> {
    const status_text = await get_alert_words_status_text(page);
    assert.strictEqual(status_text, `Alert word "${word}" added successfully!`);
    await close_alert_words_status(page);
}

async function test_duplicate_alert_words_cannot_be_added(
    page: Page,
    duplicate_word: string,
): Promise<void> {
    await add_alert_word(page, duplicate_word);
    const status_text = await get_alert_words_status_text(page);
    assert.strictEqual(status_text, "Alert word already exists!");
    await close_alert_words_status(page);
}

async function delete_alert_word(page: Page, word: string): Promise<void> {
    const delete_btn_selector = `.remove-alert-word[data-word="${CSS.escape(word)}"]`;
    await page.click(delete_btn_selector);
    await page.waitForSelector(delete_btn_selector, {hidden: true});
}

async function test_alert_word_deletion(page: Page, word: string): Promise<void> {
    await delete_alert_word(page, word);
    const status_text = await get_alert_words_status_text(page);
    assert.strictEqual(status_text, "Alert word removed successfully!");
    await close_alert_words_status(page);
}

async function test_alert_words_section(page: Page): Promise<void> {
    await page.click('[data-section="alert-words"]');
    const word = "puppeteer";
    await add_alert_word(page, word);
    await test_and_close_alert_word_added_successfully_status(page, word);
    await check_alert_word_added(page, word);
    await test_duplicate_alert_words_cannot_be_added(page, word);
    await test_alert_word_deletion(page, word);
}

async function change_language(page: Page, language_data_code: string): Promise<void> {
    await page.waitForSelector("#default_language", {visible: true});
    await page.click("#default_language");
    await page.waitForSelector("#default_language_modal", {visible: true});
    const language_selector = `a[data-code="${CSS.escape(language_data_code)}"]`;
    await page.click(language_selector);
}

async function check_language_setting_status(page: Page): Promise<void> {
    await page.waitForSelector("#language-settings-status .reload_link", {visible: true});
}

async function assert_language_changed_to_chinese(page: Page): Promise<void> {
    await page.waitForSelector("#default_language", {visible: true});
    const default_language = await common.get_text_from_selector(page, "#default_language");
    assert.strictEqual(
        default_language,
        "简体中文",
        "Default language has not been changed to Chinese.",
    );
}

async function test_i18n_language_precedence(page: Page): Promise<void> {
    const settings_url_for_german = "http://zulip.zulipdev.com:9981/de/#settings";
    await page.goto(settings_url_for_german);
    await page.waitForSelector("#settings-change-box", {visible: true});
    const page_language_code = await page.evaluate(() => document.documentElement.lang);
    assert.strictEqual(page_language_code, "de");
}

async function test_default_language_setting(page: Page): Promise<void> {
    const display_settings_section = '[data-section="display-settings"]';
    await page.click(display_settings_section);

    const chinese_language_data_code = "zh-hans";
    await change_language(page, chinese_language_data_code);
    // Check that the saved indicator appears
    await check_language_setting_status(page);
    await page.click(".reload_link");
    await page.waitForSelector("#default_language", {visible: true});
    await assert_language_changed_to_chinese(page);
    await test_i18n_language_precedence(page);
    await page.waitForSelector(display_settings_section, {visible: true});
    await page.click(display_settings_section);

    // Change the language back to English so that subsequent tests pass.
    await change_language(page, "en");

    // Check that the saved indicator appears
    await check_language_setting_status(page);
    await page.goto("http://zulip.zulipdev.com:9981/#settings"); // get back to normal language.
    await page.waitForSelector(display_settings_section, {visible: true});
    await page.click(display_settings_section);
    await page.waitForSelector("#language-settings-status", {visible: true});
    await page.waitForSelector("#default_language", {visible: true});
}

async function test_notifications_section(page: Page): Promise<void> {
    await page.click('[data-section="notifications"]');
    // At the beginning, "PMs, mentions, and alerts"(checkbox name=enable_sounds) audio will be on
    // and "Streams"(checkbox name=enable_stream_audible_notifications) audio will be off by default.

    const notification_sound_enabled = "#notification_sound:enabled";
    await page.waitForSelector(notification_sound_enabled, {visible: true});

    await common.fill_form(page, ".notification-settings-form", {
        enable_stream_audible_notifications: true,
        enable_sounds: false,
    });
    await page.waitForSelector(notification_sound_enabled, {visible: true});

    await common.fill_form(page, ".notification-settings-form", {
        enable_stream_audible_notifications: true,
    });
    /*
    Usually notifications sound dropdown gets disabled on disabling
    all audio notifications. But this seems flaky in tests.
    TODO: Find the right fix and enable this.

    const notification_sound_disabled = "#notification_sound:disabled";
    await page.waitForSelector(notification_sound_disabled);
    */
}

async function settings_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await open_settings(page);
    await test_change_full_name(page);
    await test_change_password(page);
    await test_get_api_key(page);
    await test_alert_words_section(page);
    await test_your_bots_section(page);
    await test_default_language_setting(page);
    await test_notifications_section(page);
}

common.run_test(settings_tests);
