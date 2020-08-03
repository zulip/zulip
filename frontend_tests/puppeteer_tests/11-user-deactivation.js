"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

async function navigate_to_user_list(page) {
    const menu_selector = "#settings-dropdown";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);
    await page.click('a[href="#organization"]');
    await page.waitForSelector("#settings_overlay_container.show", {visible: true});
    await page.click("li[data-section='user-list-admin']");
}

async function user_row(page, name) {
    const user_id = await common.get_user_id_from_name(page, name);
    return `.user_row[data-user-id="${user_id}"]`;
}

async function test_deactivate_user(page) {
    const cordelia_user_row = await user_row(page, "cordelia");
    await page.waitForSelector(cordelia_user_row, {visible: true});
    await page.waitForSelector(cordelia_user_row + " .fa-user-times");
    await page.click(cordelia_user_row + " .deactivate");
    await page.waitForSelector("#deactivation_user_modal", {visible: true});

    assert.strictEqual(
        await common.get_text_from_selector(page, "#deactivation_user_modal_label"),
        "Deactivate " + (await common.get_internal_email_from_name(page, "cordelia")),
        "Deactivate modal has wrong user.",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#deactivation_user_modal .do_deactivate_button"),
        "Deactivate now",
        "Deactivate button has incorrect text.",
    );
    await page.click("#deactivation_user_modal .do_deactivate_button");
    await page.waitForSelector("#user-field-status", {hidden: true});
}

async function test_reactivate_user(page) {
    let cordelia_user_row = await user_row(page, "cordelia");
    await page.waitForSelector(cordelia_user_row + ".deactivated_user");
    await page.waitForSelector(cordelia_user_row + " .fa-user-plus");
    await page.click(cordelia_user_row + " .reactivate");

    await page.waitForSelector(cordelia_user_row + ":not(.deactivated_user)", {visible: true});
    cordelia_user_row = await user_row(page, "cordelia");
    await page.waitForSelector(cordelia_user_row + " .fa-user-times");
    await page.waitForSelector("#user-field-status", {hidden: true});
}

async function test_deactivated_users_section(page) {
    const cordelia_user_row = await user_row(page, "cordelia");
    await test_deactivate_user(page);

    // "Deactivated users" section doesn't render just deactivated users until reloaded.
    await page.reload();
    const deactivated_users_section = "li[data-section='deactivated-users-admin']";
    await page.waitForSelector(deactivated_users_section, {visible: true});
    await page.click(deactivated_users_section);

    await page.waitForSelector(
        "#admin_deactivated_users_table " + cordelia_user_row + " .reactivate",
        {visible: true},
    );
    await page.click("#admin_deactivated_users_table " + cordelia_user_row + " .reactivate");
    await page.waitForSelector(
        "#admin_deactivated_users_table " + cordelia_user_row + " button:not(.reactivate)",
        {visible: true},
    );
}

async function test_bot_deactivation_and_reactivation(page) {
    await page.click("li[data-section='bot-list-admin']");

    const default_bot_user_row = await user_row(page, "Zulip Default Bot");

    await page.click(default_bot_user_row + " .deactivate");
    await page.waitForSelector(default_bot_user_row + ".deactivated_user", {visible: true});
    await page.waitForSelector(default_bot_user_row + " .fa-user-plus");
    await page.waitForSelector("#bot-field-status", {hidden: true});

    await page.click(default_bot_user_row + " .reactivate");
    await page.waitForSelector(default_bot_user_row + ":not(.deactivated_user)", {visible: true});
    await page.waitForSelector(default_bot_user_row + " .fa-user-times");
}

async function user_deactivation_test(page) {
    await common.log_in(page);
    await navigate_to_user_list(page);
    await test_deactivate_user(page);
    await test_reactivate_user(page);
    await test_deactivated_users_section(page);
    await test_bot_deactivation_and_reactivation(page);
    await common.log_out(page);
}

common.run_test(user_deactivation_test);
