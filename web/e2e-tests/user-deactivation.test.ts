import {strict as assert} from "assert";

import type {ElementHandle, Page} from "puppeteer";

import * as common from "./lib/common";

async function navigate_to_user_list(page: Page): Promise<void> {
    const menu_selector = "#settings-dropdown";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);

    const organization_settings = '.link-item a[href="#organization"]';
    await page.waitForSelector(organization_settings, {visible: true});
    await page.click(organization_settings);

    await page.waitForSelector("#settings_overlay_container.show", {visible: true});
    await page.click("li[data-section='users']");
    await page.waitForSelector("#admin-user-list.show", {visible: true});
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
        await common.get_text_from_selector(page, ".micromodal .dialog_submit_button"),
        "Confirm",
        "Reactivate button has incorrect text.",
    );
    await page.click(".micromodal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);
}

async function test_deactivate_user(page: Page): Promise<void> {
    const cordelia_user_row = await user_row(page, common.fullname.cordelia);
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
        await common.get_text_from_selector(page, ".micromodal .dialog_submit_button"),
        "Deactivate",
        "Deactivate button has incorrect text.",
    );
    await page.click(".micromodal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);
}

async function test_reactivate_user(page: Page): Promise<void> {
    let cordelia_user_row = await user_row(page, common.fullname.cordelia);
    await page.waitForSelector(cordelia_user_row + ".deactivated_user");
    await page.waitForSelector(cordelia_user_row + " .fa-user-plus");
    await page.click(cordelia_user_row + " .reactivate");

    await test_reactivation_confirmation_modal(page, common.fullname.cordelia);

    await page.waitForSelector(cordelia_user_row + ":not(.deactivated_user)", {visible: true});
    cordelia_user_row = await user_row(page, common.fullname.cordelia);
    await page.waitForSelector(cordelia_user_row + " .fa-user-times");
}

async function test_deactivated_users_section(page: Page): Promise<void> {
    const cordelia_user_row = await user_row(page, common.fullname.cordelia);
    await test_deactivate_user(page);

    // "Deactivated users" section doesn't render just deactivated users until reloaded.
    await page.reload();
    await page.waitForSelector("#admin-user-list.show", {visible: true});
    const deactivated_users_section = ".tab-container .ind-tab[data-tab-key='deactivated']";
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
        await common.get_text_from_selector(page, ".micromodal .dialog_submit_button"),
        "Deactivate",
        "Deactivate button has incorrect text.",
    );
    await page.click(".micromodal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector(default_bot_user_row + ".deactivated_user", {visible: true});
    await page.waitForSelector(default_bot_user_row + " .fa-user-plus");

    await page.click(default_bot_user_row + " .reactivate");
    await test_reactivation_confirmation_modal(page, "Zulip Default Bot");
    await page.waitForSelector(default_bot_user_row + ":not(.deactivated_user)", {visible: true});
    await page.waitForSelector(default_bot_user_row + " .fa-user-times");
}

async function test_deactivate_user_with_ban_reason(page: Page): Promise<void> {
    await page.waitForSelector("#settings_overlay_container.show", {visible: true});
    await page.click("li[data-section='users']");
    await page.waitForSelector("#admin-user-list.show", {visible: true});

    await page.reload();
    await page.waitForSelector("#admin-user-list.show", {visible: true});
    const activate_users_section = ".tab-container .ind-tab[data-tab-key='active']";
    await page.waitForSelector(activate_users_section, {visible: true});
    await page.click(activate_users_section);

    const aaron_user_row = await user_row(page, "aaron");
    await page.waitForSelector(aaron_user_row, {visible: true});
    await page.waitForSelector(aaron_user_row + " .fa-user-times");
    await page.click(aaron_user_row + " .deactivate");
    await common.wait_for_micromodal_to_open(page);

    // Wait for checkbox
    await page.waitForSelector("#ban_reason_checkbox", {visible: true});

    // Click ban reason checkbox
    await page.click("#ban_reason_checkbox");
    await page.waitForSelector("#ban_reason_dropdown", {visible: true});

    await page.click("#id-deactivation-message");
    await page.waitForSelector("#id-deactivation-message", {visible: true});

    // Choose ban reason
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");

    // Deactivate user
    await page.click(".micromodal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);
}

async function get_text(element: ElementHandle): Promise<string> {
    const text = await (await element.getProperty("value")).jsonValue();
    assert.ok(typeof text === "string");
    return text;
}

async function get_text_from_textarea(page: Page, selector: string): Promise<string> {
    const elements = await page.$$(selector);
    const texts = await Promise.all(elements.map(async (element) => get_text(element)));
    return texts.join("").trim();
}

async function test_ban_reason(page: Page): Promise<void> {
    // This test depends on test_deactivate_user_with_ban_reason
    // First we open the deactivated users section
    await page.reload();
    await page.waitForSelector("#admin-user-list.show", {visible: true});
    const deactivated_users_section = ".tab-container .ind-tab[data-tab-key='deactivated']";
    await page.waitForSelector(deactivated_users_section, {visible: true});
    await page.click(deactivated_users_section);

    const aaron_user_row = await user_row(page, "aaron");
    await page.waitForSelector(aaron_user_row, {visible: true});
    await page.waitForSelector(aaron_user_row + " .ban_reason");

    // Click to inspect aarons ban reason
    await page.click(aaron_user_row + " .ban_reason");
    await common.wait_for_micromodal_to_open(page);
    await page.waitForSelector("#ban_reason_field_textarea");

    // Verify it was correctly stored
    assert.strictEqual(
        await get_text_from_textarea(page, "#ban_reason_field_textarea"),
        "Disruptive behavior",
    );

    // Delete it
    const ban_reason_text_area = await page.$("#ban_reason_field_textarea");
    if (ban_reason_text_area) {
        // These three clicks open the text area and select the whole text to delete it
        await ban_reason_text_area.click({clickCount: 3});

        // Change it
        await ban_reason_text_area.press("Backspace");
        await ban_reason_text_area.type("This user did not comply with the privacy policy");
    }

    // Save it
    await page.click(".micromodal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);
    await page.reload();

    // Click to inspect aarons ban reason
    await page.click(aaron_user_row + " .ban_reason");
    await common.wait_for_micromodal_to_open(page);
    await page.waitForSelector("#ban_reason_field_textarea");

    // Verify it was correctly stored
    assert.strictEqual(
        await get_text_from_textarea(page, "#ban_reason_field_textarea"),
        "This user did not comply with the privacy policy",
    );
}

async function user_deactivation_test(page: Page): Promise<void> {
    await common.log_in(page);
    await navigate_to_user_list(page);
    await test_deactivate_user(page);
    await test_reactivate_user(page);
    await test_deactivated_users_section(page);
    await test_bot_deactivation_and_reactivation(page);
    await test_deactivate_user_with_ban_reason(page);
    await test_ban_reason(page);
}

common.run_test(user_deactivation_test);
