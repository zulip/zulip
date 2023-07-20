import {strict as assert} from "assert";

import type {ElementHandle, Page} from "puppeteer";

import {test_credentials} from "../../var/puppeteer/test_credentials";

import * as common from "./lib/common";

const OUTGOING_WEBHOOK_BOT_TYPE = "3";
const GENERIC_BOT_TYPE = "1";

const zuliprc_regex =
    /^data:application\/octet-stream;charset=utf-8,\[api]\nemail=.+\nkey=.+\nsite=.+\n$/;

async function get_decoded_url_in_selector(page: Page, selector: string): Promise<string> {
    const a = (await page.$(selector)) as ElementHandle<HTMLAnchorElement>;
    return decodeURIComponent(await (await a.getProperty("href")).jsonValue());
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

async function close_settings_and_date_picker(page: Page): Promise<void> {
    const date_picker_selector = ".custom_user_field_value.datepicker.form-control";
    await page.click(date_picker_selector);

    await page.waitForSelector(".flatpickr-calendar", {visible: true});

    await page.keyboard.press("Escape");
    await page.waitForSelector(".flatpickr-calendar", {hidden: true});
}

async function test_change_full_name(page: Page): Promise<void> {
    await page.click("#full_name");

    const full_name_input_selector = 'input[name="full_name"]';
    await common.clear_and_type(page, full_name_input_selector, "New name");

    await page.click("#settings_content .profile-settings-form");
    await page.waitForSelector(".full-name-change-container .alert-success", {visible: true});
    await page.waitForFunction(
        () => document.querySelector<HTMLInputElement>("#full_name")?.value === "New name",
    );
}

async function test_change_password(page: Page): Promise<void> {
    await page.click("#change_password");

    const change_password_button_selector = "#change_password_modal .dialog_submit_button";
    await page.waitForSelector(change_password_button_selector, {visible: true});

    await common.wait_for_micromodal_to_open(page);
    await page.type("#old_password", test_credentials.default_user.password);
    test_credentials.default_user.password = "new_password";
    await page.type("#new_password", test_credentials.default_user.password);
    await page.click(change_password_button_selector);

    // On success the change password modal gets closed.
    await common.wait_for_micromodal_to_close(page);
}

async function test_get_api_key(page: Page): Promise<void> {
    await page.click('[data-section="account-and-privacy"]');
    const show_change_api_key_selector = "#api_key_button";
    await page.click(show_change_api_key_selector);

    const get_api_key_button_selector = "#get_api_key_button";
    await page.waitForSelector(get_api_key_button_selector, {visible: true});
    await common.wait_for_micromodal_to_open(page);
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
    await page.click("#api_key_modal .modal__close");
    await common.wait_for_micromodal_to_close(page);
}

async function test_webhook_bot_creation(page: Page): Promise<void> {
    await page.click("#bot-settings .add-a-new-bot");
    await common.wait_for_micromodal_to_open(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Add a new bot",
        "Unexpected title for deactivate user modal",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_widget_modal .dialog_submit_button"),
        "Add",
        "Deactivate button has incorrect text.",
    );
    await common.fill_form(page, "#create_bot_form", {
        bot_name: "Bot 1",
        bot_short_name: "1",
        bot_type: OUTGOING_WEBHOOK_BOT_TYPE,
        payload_url: "http://hostname.example.com/bots/followup",
    });
    await page.click("#dialog_widget_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

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
        "Incorrect outgoing webhook bot zuliprc format",
    );
}

async function test_normal_bot_creation(page: Page): Promise<void> {
    await page.click("#bot-settings .add-a-new-bot");
    await common.wait_for_micromodal_to_open(page);
    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Add a new bot",
        "Unexpected title for deactivate user modal",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_widget_modal .dialog_submit_button"),
        "Add",
        "Deactivate button has incorrect text.",
    );
    await common.fill_form(page, "#create_bot_form", {
        bot_name: "Bot 2",
        bot_short_name: "2",
        bot_type: GENERIC_BOT_TYPE,
    });
    await page.click("#dialog_widget_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

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

// Disabled the below test due to non-deterministic failures.
// The test often fails to close the modal, as does the
// test_invalid_edit_bot_form above.
// TODO: Debug this and re-enable with a fix.
async function test_edit_bot_form(page: Page): Promise<void> {
    return;
    const bot1_email = "1-bot@zulip.testserver";
    const bot1_edit_btn = `.open_edit_bot_form[data-email="${CSS.escape(bot1_email)}"]`;
    await page.click(bot1_edit_btn);

    const edit_form_selector = `#bot-edit-form[data-email="${CSS.escape(bot1_email)}"]`;
    await page.waitForSelector(edit_form_selector, {visible: true});
    const name_field_selector = edit_form_selector + " [name=full_name]";
    assert.equal(
        await page.$eval(name_field_selector, (el) => (el as HTMLInputElement).value),
        "Bot 1",
    );

    await common.fill_form(page, edit_form_selector, {full_name: "Bot one"});
    const save_btn_selector = "#user-profile-modal .dialog_submit_button";
    await page.click(save_btn_selector);

    // The form gets closed on saving. So, assert it's closed by waiting for it to be hidden.
    await page.waitForSelector("#edit_bot_modal", {hidden: true});

    await page.waitForSelector(
        `xpath///*[${common.has_class_x(
            "open_edit_bot_form",
        )} and @data-email="${bot1_email}"]/ancestor::*[${common.has_class_x(
            "details",
        )}]/*[${common.has_class_x("name")} and text()="Bot one"]`,
    );

    await common.wait_for_micromodal_to_close(page);
}

// Disabled the below test due to non-deterministic failures.
// The test often fails to close the modal.
// TODO: Debug this and re-enable with a fix.
async function test_invalid_edit_bot_form(page: Page): Promise<void> {
    return;
    const bot1_email = "1-bot@zulip.testserver";
    const bot1_edit_btn = `.open_edit_bot_form[data-email="${CSS.escape(bot1_email)}"]`;
    await page.click(bot1_edit_btn);

    const edit_form_selector = `#bot-edit-form[data-email="${CSS.escape(bot1_email)}"]`;
    await page.waitForSelector(edit_form_selector, {visible: true});
    const name_field_selector = edit_form_selector + " [name=full_name]";
    assert.equal(
        await page.$eval(name_field_selector, (el) => (el as HTMLInputElement).value),
        "Bot one",
    );

    await common.fill_form(page, edit_form_selector, {full_name: "Bot 2"});
    const save_btn_selector = "#user-profile-modal .dialog_submit_button";
    await page.click(save_btn_selector);

    // The form should not get closed on saving. Errors should be visible on the form.
    await common.wait_for_micromodal_to_open(page);
    await page.waitForSelector("#dialog_error", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_error"),
        "Failed: Name is already in use!",
    );

    const cancel_button_selector = "#user-profile-modal .dialog_exit_button";
    await page.waitForFunction(
        (cancel_button_selector: string) =>
            !document.querySelector(cancel_button_selector)?.hasAttribute("disabled"),
        {},
        cancel_button_selector,
    );
    await page.click(cancel_button_selector);
    await page.waitForSelector(
        `xpath///*[${common.has_class_x(
            "open_edit_bot_form",
        )} and @data-email="${bot1_email}"]/ancestor::*[${common.has_class_x(
            "details",
        )}]/*[${common.has_class_x("name")} and text()="Bot one"]`,
    );

    await common.wait_for_micromodal_to_close(page);
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
    await page.click("#open-add-alert-word-modal");
    await common.wait_for_micromodal_to_open(page);

    await page.type("#add-alert-word-name", word);
    await page.click("#add-alert-word .dialog_submit_button");

    await common.wait_for_micromodal_to_close(page);
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

async function test_duplicate_alert_words_cannot_be_added(
    page: Page,
    duplicate_word: string,
): Promise<void> {
    await page.click("#open-add-alert-word-modal");
    await common.wait_for_micromodal_to_open(page);

    await page.type("#add-alert-word-name", duplicate_word);
    await page.click("#add-alert-word .dialog_submit_button");

    const alert_word_status_selector = "#dialog_error";
    await page.waitForSelector(alert_word_status_selector, {visible: true});
    const status_text = await common.get_text_from_selector(page, alert_word_status_selector);
    assert.strictEqual(status_text, "Alert word already exists!");

    await page.click("#add-alert-word .dialog_exit_button");
    await common.wait_for_micromodal_to_close(page);
}

async function delete_alert_word(page: Page, word: string): Promise<void> {
    const delete_btn_selector = `.remove-alert-word[data-word="${CSS.escape(word)}"]`;
    await page.click(delete_btn_selector);
    await page.waitForSelector(delete_btn_selector, {hidden: true});
}

async function test_alert_word_deletion(page: Page, word: string): Promise<void> {
    await delete_alert_word(page, word);
    const status_text = await get_alert_words_status_text(page);
    assert.strictEqual(status_text, `Alert word "${word}" removed successfully!`);
    await close_alert_words_status(page);
}

async function test_alert_words_section(page: Page): Promise<void> {
    await page.click('[data-section="alert-words"]');
    const word = "puppeteer";
    await add_alert_word(page, word);
    await check_alert_word_added(page, word);
    await test_duplicate_alert_words_cannot_be_added(page, word);
    await test_alert_word_deletion(page, word);
}

async function change_language(page: Page, language_data_code: string): Promise<void> {
    await page.waitForSelector("#user-preferences .language_selection_button", {
        visible: true,
    });
    await page.click("#user-preferences .language_selection_button");
    await common.wait_for_micromodal_to_open(page);
    const language_selector = `a[data-code="${CSS.escape(language_data_code)}"]`;
    await page.click(language_selector);
}

async function check_language_setting_status(page: Page): Promise<void> {
    await page.waitForSelector("#user-preferences .general-settings-status .reload_link", {
        visible: true,
    });
}

async function assert_language_changed_to_chinese(page: Page): Promise<void> {
    await page.waitForSelector("#user-preferences .language_selection_button", {
        visible: true,
    });
    const default_language = await common.get_text_from_selector(
        page,
        "#user-preferences .language_selection_button",
    );
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
    const display_settings_section = '[data-section="preferences"]';
    await page.click(display_settings_section);

    const chinese_language_data_code = "zh-hans";
    await change_language(page, chinese_language_data_code);
    // Check that the saved indicator appears
    await check_language_setting_status(page);
    await page.click(".reload_link");
    await page.waitForSelector("#user-preferences .language_selection_button", {
        visible: true,
    });
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
    await page.waitForSelector("#user-preferences .general-settings-status", {
        visible: true,
    });
    await page.waitForSelector("#user-preferences .language_selection_button", {
        visible: true,
    });
}

async function test_notifications_section(page: Page): Promise<void> {
    await page.click('[data-section="notifications"]');
    // At the beginning, "DMs, mentions, and alerts"(checkbox name=enable_sounds) audio will be on
    // and "Streams"(checkbox name=enable_stream_audible_notifications) audio will be off by default.

    const notification_sound_enabled =
        "#user-notification-settings .setting_notification_sound:enabled";
    await page.waitForSelector(notification_sound_enabled, {visible: true});

    await common.fill_form(page, "#user-notification-settings .notification-settings-form", {
        enable_stream_audible_notifications: true,
        enable_sounds: false,
    });
    await page.waitForSelector(notification_sound_enabled, {visible: true});

    await common.fill_form(page, "#user-notification-settings .notification-settings-form", {
        enable_stream_audible_notifications: true,
    });
    /*
    Usually notifications sound dropdown gets disabled on disabling
    all audio notifications. But this seems flaky in tests.
    TODO: Find the right fix and enable this.

    const notification_sound_disabled = ".setting_notification_sound:disabled";
    await page.waitForSelector(notification_sound_disabled);
    */
}

async function settings_tests(page: Page): Promise<void> {
    await common.log_in(page);
    await open_settings(page);
    await close_settings_and_date_picker(page);
    await open_settings(page);
    await test_change_full_name(page);
    await test_alert_words_section(page);
    await test_your_bots_section(page);
    await test_default_language_setting(page);
    await test_notifications_section(page);
    await test_get_api_key(page);
    await test_change_password(page);
    // test_change_password should be the very last test, because it
    // replaces your session, which can lead to some nondeterministic
    // failures in test code after it, involving `GET /events`
    // returning a 401. (We reset the test database after each file).
}

common.run_test(settings_tests);
