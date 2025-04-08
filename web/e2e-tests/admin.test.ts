import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function submit_announcements_stream_settings(page: Page): Promise<void> {
    await page.waitForSelector('#org-notifications .save-button[data-status="unsaved"]', {
        visible: true,
    });

    const save_button = "#org-notifications .save-button";
    await page.waitForFunction(
        (save_button: string) => {
            const button = document.querySelector(save_button);
            return button && button.textContent?.trim() === "Save changes";
        },
        {},
        save_button,
    );
    await page.click(save_button);

    await page.waitForSelector('#org-notifications .save-button[data-status="saved"]', {
        visible: true,
    });
    await page.waitForFunction(
        (save_button: string) => {
            const button = document.querySelector(save_button);
            return button && button.textContent?.trim() === "Saved";
        },
        {},
        save_button,
    );

    await page.waitForSelector("#org-notifications .save-button", {hidden: true});
}

async function test_change_new_stream_announcements_stream(page: Page): Promise<void> {
    await page.click("#realm_new_stream_announcements_stream_id_widget.dropdown-widget-button");
    await page.waitForSelector(".dropdown-list-container", {
        visible: true,
    });

    await page.type(".dropdown-list-search-input", "rome");

    const rome_in_dropdown = await page.waitForSelector(
        `xpath///*[${common.has_class_x("list-item")}][normalize-space()="Rome"]`,
        {visible: true},
    );
    assert.ok(rome_in_dropdown);
    await rome_in_dropdown.click();

    await submit_announcements_stream_settings(page);
}

async function test_change_signup_announcements_stream(page: Page): Promise<void> {
    await page.click("#realm_signup_announcements_stream_id_widget.dropdown-widget-button");
    await page.waitForSelector(".dropdown-list-container", {
        visible: true,
    });

    await page.type(".dropdown-list-search-input", "rome");

    const rome_in_dropdown = await page.waitForSelector(
        `xpath///*[${common.has_class_x("list-item")}][normalize-space()="Rome"]`,
        {visible: true},
    );
    assert.ok(rome_in_dropdown);
    await rome_in_dropdown.click();

    await submit_announcements_stream_settings(page);
}

async function test_change_zulip_update_announcements_stream(page: Page): Promise<void> {
    await page.click("#realm_zulip_update_announcements_stream_id_widget.dropdown-widget-button");
    await page.waitForSelector(".dropdown-list-container", {
        visible: true,
    });

    await page.type(".dropdown-list-search-input", "rome");

    const rome_in_dropdown = await page.waitForSelector(
        `xpath///*[${common.has_class_x("list-item")}][normalize-space()="Rome"]`,
        {visible: true},
    );
    assert.ok(rome_in_dropdown);
    await rome_in_dropdown.click();

    await submit_announcements_stream_settings(page);
}

async function test_save_joining_organization_change_worked(page: Page): Promise<void> {
    const saved_status = '#org-join-settings .save-button[data-status="saved"]';
    await page.waitForSelector(saved_status, {
        visible: true,
    });
    await page.waitForSelector(saved_status, {hidden: true});
}

async function submit_joining_organization_change(page: Page): Promise<void> {
    const save_button = "#org-join-settings .save-button";
    await page.waitForSelector(save_button, {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, save_button),
        "Save changes",
        "Save button didn't appear for permissions change.",
    );
    await page.waitForSelector(save_button, {visible: true});
    await page.click(save_button);

    await test_save_joining_organization_change_worked(page);
}

async function test_set_new_user_threshold_to_three_days(page: Page): Promise<void> {
    console.log("Test setting new user threshold to three days.");
    await page.waitForSelector("#id_realm_waiting_period_threshold", {visible: true});
    await page.select("#id_realm_waiting_period_threshold", "3");
    await submit_joining_organization_change(page);
}

async function test_set_new_user_threshold_to_N_days(page: Page): Promise<void> {
    console.log("Test setting new user threshold to N days.");
    await page.waitForSelector("#id_realm_waiting_period_threshold", {visible: true});
    await page.select("#id_realm_waiting_period_threshold", "custom_period");

    const N = "10";
    await common.clear_and_type(page, "#id_realm_waiting_period_threshold_custom_input", N);
    await submit_joining_organization_change(page);
}

async function test_organization_permissions(page: Page): Promise<void> {
    await page.click("li[data-section='organization-permissions']");

    // Test temporarily disabled 2024-02-25 due to nondeterminsitic failures.
    // See https://chat.zulip.org/#narrow/channel/43-automated-testing/topic/main.20failing/near/1743361
    console.log("Skipping", test_set_new_user_threshold_to_three_days);
    console.log("Skipping", test_set_new_user_threshold_to_N_days);
}

async function test_add_emoji(page: Page): Promise<void> {
    await common.fill_form(page, "#add-custom-emoji-form", {name: "zulip logo"});

    const emoji_upload_handle = await page.$("input#emoji_file_input");
    assert.ok(emoji_upload_handle);
    await emoji_upload_handle.uploadFile("static/images/logo/zulip-icon-128x128.png");
    await page.click("#add-custom-emoji-modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    await page.waitForSelector("tr#emoji_zulip_logo", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "tr#emoji_zulip_logo .emoji_name"),
        "zulip logo",
        "Emoji name incorrectly saved.",
    );
    await page.waitForSelector("tr#emoji_zulip_logo img", {visible: true});
}

async function test_delete_emoji(page: Page): Promise<void> {
    await page.click("tr#emoji_zulip_logo button.delete");

    await common.wait_for_micromodal_to_open(page);
    await page.click("#confirm_deactivate_custom_emoji_modal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    // assert the emoji is deleted.
    await page.waitForSelector("tr#emoji_zulip_logo", {hidden: true});
}

async function test_custom_realm_emoji(page: Page): Promise<void> {
    await page.click("li[data-section='emoji-settings']");
    await page.click("#add-custom-emoji-button");
    await common.wait_for_micromodal_to_open(page);

    await test_add_emoji(page);
    await test_delete_emoji(page);
}

async function test_upload_realm_icon_image(page: Page): Promise<void> {
    const upload_handle = await page.$("#realm-icon-upload-widget input.image_file_input");
    assert.ok(upload_handle);
    await upload_handle.uploadFile("static/images/logo/zulip-icon-128x128.png");

    await page.waitForSelector("#realm-icon-upload-widget .upload-spinner-background", {
        visible: true,
    });
    await page.waitForSelector("#realm-icon-upload-widget .upload-spinner-background", {
        hidden: true,
    });
    await page.waitForSelector(
        '#realm-icon-upload-widget .image-block[src^="/user_avatars/2/realm/icon.png?version=2"]',
        {visible: true},
    );
}

async function delete_realm_icon(page: Page): Promise<void> {
    await page.click("li[data-section='organization-profile']");
    await page.click("#realm-icon-upload-widget .image-delete-button");

    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {hidden: true});
}

async function test_organization_profile(page: Page): Promise<void> {
    await page.click("li[data-section='organization-profile']");
    const gravatar_selector =
        '#realm-icon-upload-widget .image-block[src^="https://secure.gravatar.com/avatar/"]';
    await page.waitForSelector(gravatar_selector, {visible: true});
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {hidden: true});

    await test_upload_realm_icon_image(page);
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {visible: true});

    await delete_realm_icon(page);
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {hidden: true});
    await page.waitForSelector(gravatar_selector, {visible: true});
}

async function test_authentication_methods(page: Page): Promise<void> {
    await page.click("li[data-section='auth-methods']");
    await page.waitForSelector(".method_row[data-method='Google'] input[type='checkbox'] + span", {
        visible: true,
    });

    await page.click(".method_row[data-method='Google'] input[type='checkbox'] + span");
    const save_button = "#org-auth_settings .save-button";
    assert.strictEqual(await common.get_text_from_selector(page, save_button), "Save changes");
    await page.click(save_button);

    // Leave the page and return.
    const settings_dropdown = "#settings-dropdown";
    await page.click(settings_dropdown);

    await common.manage_organization(page);
    await page.click("li[data-section='auth-methods']");

    // Test setting was saved.
    await page.waitForSelector(".method_row[data-method='Google'] input[type='checkbox'] + span", {
        visible: true,
    });
    await page.waitForSelector(
        ".method_row[data-method='Google'] input[type='checkbox']:not(:checked)",
    );
}

async function admin_test(page: Page): Promise<void> {
    await common.log_in(page);

    await common.manage_organization(page);
    await test_change_new_stream_announcements_stream(page);
    await test_change_signup_announcements_stream(page);
    await test_change_zulip_update_announcements_stream(page);

    await test_organization_permissions(page);
    // Currently, Firefox (with puppeteer) does not support file upload:
    //    https://github.com/puppeteer/puppeteer/issues/6688.
    // Until that is resolved upstream, we need to skip the tests that involve
    // doing file upload on Firefox.
    if (!common.is_firefox) {
        await test_custom_realm_emoji(page);
        await test_organization_profile(page);
    }
    await test_authentication_methods(page);
}

common.run_test(admin_test);
