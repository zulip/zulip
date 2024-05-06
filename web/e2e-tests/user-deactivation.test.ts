import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function navigate_to_user_list(page: Page): Promise<void> {
    const menu_selector = "#settings-dropdown";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);

    const organization_settings = '.link-item a[href="#organization"]';
    await page.waitForSelector(organization_settings, {visible: true});
    await page.click(organization_settings);

    await page.waitForSelector("#settings_overlay_container.show", {visible: true});
    await page.click("li[data-section='user-list-admin']");
}

async function user_row(page: Page, name: string): Promise<string> {
    const user_id = await common.get_user_id_from_name(page, name);
    assert(user_id !== undefined);
    return `.user_row[data-user-id="${CSS.escape(user_id.toString())}"]`;
}

async function test_reactivation_confirmation_modal(page: Page, fullname: string): Promise<void> {
    await common.wait_for_micromodal_to_open(page);

    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Reactivate " + fullname,
        "Unexpected title for reactivate user modal",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_widget_modal .dialog_submit_button"),
        "Confirm",
        "Reactivate button has incorrect text.",
    );
    await page.click("#dialog_widget_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);
}

async function test_deactivate_user(page: Page): Promise<void> {
    const cordelia_user_row = await user_row(page, "cordelia");
    await page.waitForSelector(cordelia_user_row, {visible: true});
    await page.waitForSelector(cordelia_user_row + " .fa-user-times");
    await page.click(cordelia_user_row + " .deactivate");
    await common.wait_for_micromodal_to_open(page);

    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Deactivate " + common.fullname.cordelia + "?",
        "Unexpected title for deactivate user modal",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_widget_modal .dialog_submit_button"),
        "Deactivate",
        "Deactivate button has incorrect text.",
    );
    await page.click("#dialog_widget_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);
}

async function test_reactivate_user(page: Page): Promise<void> {
    let cordelia_user_row = await user_row(page, "cordelia");
    await page.waitForSelector(cordelia_user_row + ".deactivated_user");
    await page.waitForSelector(cordelia_user_row + " .fa-user-plus");
    await page.click(cordelia_user_row + " .reactivate");

    await test_reactivation_confirmation_modal(page, common.fullname.cordelia);

    await page.waitForSelector(cordelia_user_row + ":not(.deactivated_user)", {visible: true});
    cordelia_user_row = await user_row(page, "cordelia");
    await page.waitForSelector(cordelia_user_row + " .fa-user-times");
}

async function test_deactivated_users_section(page: Page): Promise<void> {
    const cordelia_user_row = await user_row(page, "cordelia");
    await test_deactivate_user(page);

    // "Deactivated users" section doesn't render just deactivated users until reloaded.
    await page.reload();
    const deactivated_users_section = "li[data-section='deactivated-users-admin']";
    await page.waitForSelector(deactivated_users_section, {visible: true});
    await page.click(deactivated_users_section);

    // Instead of waiting for reactivate button using the `waitForSelector` function,
    // we wait until the input is focused because the `waitForSelector` function
    // doesn't guarantee that element is interactable.
    await page.waitForSelector("input[aria-label='Filter deactivated users']", {visible: true});
    await page.click("input[aria-label='Filter deactivated users']");
    await page.waitForFunction(
        () => document.activeElement?.classList?.contains("search") === true,
    );
    await page.click("#admin_deactivated_users_table " + cordelia_user_row + " .reactivate");

    await test_reactivation_confirmation_modal(page, common.fullname.cordelia);

    await page.waitForSelector(
        "#admin_deactivated_users_table " + cordelia_user_row + " button:not(.reactivate)",
        {visible: true},
    );
}

async function test_bot_deactivation_and_reactivation(page: Page): Promise<void> {
    await page.click("li[data-section='bot-list-admin']");

    const default_bot_user_row = await user_row(page, "Zulip Default Bot");

    await page.click(default_bot_user_row + " .deactivate");
    await common.wait_for_micromodal_to_open(page);

    assert.strictEqual(
        await common.get_text_from_selector(page, ".dialog_heading"),
        "Deactivate Zulip Default Bot?",
        "Unexpected title for deactivate bot modal",
    );
    assert.strictEqual(
        await common.get_text_from_selector(page, "#dialog_widget_modal .dialog_submit_button"),
        "Deactivate",
        "Deactivate button has incorrect text.",
    );
    await page.click("#dialog_widget_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector(default_bot_user_row + ".deactivated_user", {visible: true});
    await page.waitForSelector(default_bot_user_row + " .fa-user-plus");

    await page.click(default_bot_user_row + " .reactivate");
    await test_reactivation_confirmation_modal(page, "Zulip Default Bot");
    await page.waitForSelector(default_bot_user_row + ":not(.deactivated_user)", {visible: true});
    await page.waitForSelector(default_bot_user_row + " .fa-user-times");
}

async function user_deactivation_test(page: Page): Promise<void> {
    await common.log_in(page);
    await navigate_to_user_list(page);
    await test_deactivate_user(page);
    await test_reactivate_user(page);
    await test_deactivated_users_section(page);
    await test_bot_deactivation_and_reactivation(page);
}

common.run_test(user_deactivation_test);
