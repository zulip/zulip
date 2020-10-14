"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

async function submit_notifications_stream_settings(page) {
    await page.waitForSelector('#org-submit-notifications[data-status="unsaved"]', {visible: true});

    const save_button = "#org-submit-notifications";
    assert.strictEqual(
        await common.get_text_from_selector(page, save_button),
        "Save changes",
        "Save button has incorrect text.",
    );
    await page.click(save_button);

    await page.waitForSelector('#org-submit-notifications[data-status="saved"]', {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "#org-submit-notifications"),
        "Saved",
        "Saved text didn't appear after saving new stream notifications setting",
    );

    await page.waitForSelector("#org-submit-notifications", {hidden: true});
}

async function test_change_new_stream_notifications_setting(page) {
    await page.click("#realm_notifications_stream_id_widget button.dropdown-toggle");
    await page.waitForSelector("#realm_notifications_stream_id_widget ul.dropdown-menu", {
        visible: true,
    });

    await page.type(
        "#realm_notifications_stream_id_widget  .dropdown-search > input[type=text]",
        "verona",
    );

    const verona_in_dropdown =
        "#realm_notifications_stream_id_widget .dropdown-list-body > li:nth-of-type(1)";

    await common.wait_for_text(page, verona_in_dropdown, "Verona");
    await page.waitForSelector(verona_in_dropdown, {visible: true});
    await page.evaluate((selector) => $(selector).click(), verona_in_dropdown);

    await submit_notifications_stream_settings(page);

    const disable_stream_notifications =
        "#realm_notifications_stream_id_widget  .dropdown_list_reset_button";
    await page.waitForSelector(disable_stream_notifications, {visible: true});
    await page.click(disable_stream_notifications);
    await submit_notifications_stream_settings(page);
}

async function test_change_signup_notifications_stream(page) {
    console.log('Changing signup notifications stream to Verona by filtering with "verona"');

    await page.click("#id_realm_signup_notifications_stream_id > button.dropdown-toggle");
    await page.waitForSelector(
        "#realm_signup_notifications_stream_id_widget  .dropdown-search > input[type=text]",
        {visible: true},
    );

    await page.type(
        "#realm_signup_notifications_stream_id_widget  .dropdown-search > input[type=text]",
        "verona",
    );
    await page.waitForSelector(
        "#realm_signup_notifications_stream_id_widget  .dropdown-list-body > li.list_item",
        {visible: true},
    );
    await page.keyboard.press("ArrowDown");
    await page.keyboard.press("Enter");
    await submit_notifications_stream_settings(page);

    const disable_signup_notifications =
        "#realm_signup_notifications_stream_id_widget  .dropdown_list_reset_button";
    await page.click(disable_signup_notifications);
    await submit_notifications_stream_settings(page);
}

async function test_permissions_change_save_worked(page) {
    const saved_status = '#org-submit-stream-permissions[data-status="saved"]';
    await page.waitForSelector(saved_status, {
        visible: true,
    });
    await page.waitForSelector(saved_status, {hidden: true});
}

async function submit_stream_permissions_change(page) {
    const save_button = "#org-submit-stream-permissions";
    await page.waitForSelector(save_button, {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, save_button),
        "Save changes",
        "Save button didn't appear for permissions change.",
    );
    await page.click(save_button);

    await test_permissions_change_save_worked(page);
}

async function test_set_create_streams_to_admins_only(page) {
    console.log("Test setting create streams policy to 'admins only'.");
    await page.waitForSelector("#id_realm_create_stream_policy", {visible: true});
    await page.evaluate(() => $("#id_realm_create_stream_policy").val(2).change());
    await submit_stream_permissions_change(page);
}

async function test_set_create_streams_to_members_and_admins(page) {
    console.log("Test setting create streams policy to 'members and admins'.");
    await page.waitForSelector("#id_realm_create_stream_policy", {visible: true});
    await page.evaluate(() => $("#id_realm_create_stream_policy").val(1).change());
    await submit_stream_permissions_change(page);
}

async function test_set_create_streams_policy_to_full_members(page) {
    console.log("Test setting create streams policy to 'full members'.");
    await page.waitForSelector("#id_realm_create_stream_policy", {visible: true});
    await page.evaluate(() => $("#id_realm_create_stream_policy").val(3).change());
    await submit_stream_permissions_change(page);
}

async function test_set_invite_to_streams_policy_to_admins_only(page) {
    console.log("Test setting invite to streams policy to 'admins only'.");
    await page.waitForSelector("#id_realm_invite_to_stream_policy", {visible: true});
    await page.evaluate(() => $("#id_realm_invite_to_stream_policy").val(2).change());
    await submit_stream_permissions_change(page);
}

async function test_set_invite_to_streams_policy_to_members_and_admins(page) {
    console.log("Test setting invite to streams policy to 'members and admins'.");
    await page.waitForSelector("#id_realm_invite_to_stream_policy", {visible: true});
    await page.evaluate(() => $("#id_realm_invite_to_stream_policy").val(1).change());
    await submit_stream_permissions_change(page);
}

async function test_set_invite_to_streams_policy_to_full_members(page) {
    console.log("Test setting invite to streams policy to 'full members'.");
    await page.waitForSelector("#id_realm_invite_to_stream_policy", {visible: true});
    await page.evaluate(() => $("#id_realm_invite_to_stream_policy").val(3).change());
    await submit_stream_permissions_change(page);
}

async function test_save_joining_organization_change_worked(page) {
    const saved_status = '#org-submit-org-join[data-status="saved"]';
    await page.waitForSelector(saved_status, {
        visible: true,
    });
    await page.waitForSelector(saved_status, {hidden: true});
}

async function submit_joining_organization_change(page) {
    const save_button = "#org-submit-org-join";
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

async function test_set_new_user_threshold_to_three_days(page) {
    console.log("Test setting new user threshold to three days.");
    await page.waitForSelector("#id_realm_waiting_period_setting", {visible: true});
    await page.evaluate(() => $("#id_realm_waiting_period_setting").val("three_days").change());
    await submit_joining_organization_change(page);
}

async function test_set_new_user_threshold_to_N_days(page) {
    console.log("Test setting new user threshold to three days.");
    await page.waitForSelector("#id_realm_waiting_period_setting", {visible: true});
    await page.evaluate(() => $("#id_realm_waiting_period_setting").val("custom_days").change());

    const N = 10;
    await page.evaluate((N) => $("#id_realm_waiting_period_threshold").val(N), N);
    await submit_joining_organization_change(page);
}

async function test_organization_permissions(page) {
    await page.click("li[data-section='organization-permissions']");

    await test_set_create_streams_to_admins_only(page);
    await test_set_create_streams_to_members_and_admins(page);
    await test_set_create_streams_policy_to_full_members(page);

    await test_set_invite_to_streams_policy_to_admins_only(page);
    await test_set_invite_to_streams_policy_to_members_and_admins(page);
    await test_set_invite_to_streams_policy_to_full_members(page);

    await test_set_new_user_threshold_to_three_days(page);
    await test_set_new_user_threshold_to_N_days(page);
}

async function test_add_emoji(page) {
    await common.fill_form(page, "form.admin-emoji-form", {name: "zulip logo"});

    const emoji_upload_handle = await page.$("#emoji_file_input");
    await emoji_upload_handle.uploadFile("static/images/logo/zulip-icon-128x128.png");
    await page.click("#admin_emoji_submit");

    const emoji_status = "div#admin-emoji-status";
    await page.waitForSelector(emoji_status, {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, emoji_status),
        "Custom emoji added!",
    );

    await page.waitForSelector("tr#emoji_zulip_logo", {visible: true});
    assert.strictEqual(
        await common.get_text_from_selector(page, "tr#emoji_zulip_logo .emoji_name"),
        "zulip logo",
        "Emoji name incorrectly saved.",
    );
    await page.waitForSelector("tr#emoji_zulip_logo img", {visible: true});
}

async function test_delete_emoji(page) {
    await page.click("tr#emoji_zulip_logo button.delete");

    // assert the emoji is deleted.
    await page.waitForFunction(() => $("tr#emoji_zulip_logo").length === 0);
}

async function test_custom_realm_emoji(page) {
    await page.click("li[data-section='emoji-settings']");
    await page.waitForSelector(".admin-emoji-form", {visible: true});

    await test_add_emoji(page);
    await test_delete_emoji(page);
}

async function get_suggestions(page, str) {
    await page.evaluate((str) => {
        $(".create_default_stream")
            .trigger("focus")
            .val(str)
            .trigger($.Event("keyup", {which: 0}));
    }, str);
}

async function select_from_suggestions(page, item) {
    await page.evaluate((item) => {
        const tah = $(".create_default_stream").data().typeahead;
        tah.mouseenter({
            currentTarget: $('.typeahead:visible li:contains("' + item + '")')[0],
        });
        tah.select();
    }, item);
}

async function test_add_default_stream(page, stream_name, row) {
    // It matches with all the stream names which has 'O' as a substring (Rome, Scotland, Verona
    // etc). 'O' is used to make sure that it works even if there are multiple suggestions.
    // Uppercase 'O' is used instead of the lowercase version to make sure that the suggestions
    // are case insensitive.
    await get_suggestions(page, "o");
    await select_from_suggestions(page, stream_name);
    await page.click(".default-stream-form #do_submit_stream");

    await page.waitForSelector(row, {visible: true});
}

async function test_remove_default_stream(page, row) {
    await page.click(row + " button.remove-default-stream");

    // assert row doesn't exist.
    await page.waitForFunction((row) => $(row).length === 0, {}, row);
}

async function test_default_streams(page) {
    await page.click("li[data-section='default-streams-list']");
    await page.waitForSelector(".create_default_stream", {visible: true});

    const stream_name = "Scotland";
    const stream_id = await common.get_stream_id(page, stream_name);
    const row = `.default_stream_row[data-stream-id='${stream_id}']`;

    await test_add_default_stream(page, stream_name, row);
    await test_remove_default_stream(page, row);
}

async function test_upload_realm_icon_image(page) {
    const upload_handle = await page.$("#realm-icon-upload-widget .image_file_input");
    await upload_handle.uploadFile("static/images/logo/zulip-icon-128x128.png");

    await page.waitForSelector("#realm-icon-upload-widget .upload-spinner-background", {
        visible: true,
    });
    await page.waitForSelector("#realm-icon-upload-widget .upload-spinner-background", {
        visible: false,
    });
    await page.waitForSelector(
        '#realm-icon-upload-widget .image-block[src^="/user_avatars/2/realm/icon.png?version=2"]',
        {visible: true},
    );
}

async function delete_realm_icon(page) {
    await page.click("li[data-section='organization-profile']");
    await page.click("#realm-icon-upload-widget .image-delete-button");

    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {visible: false});
}

async function test_organization_profile(page) {
    await page.click("li[data-section='organization-profile']");
    const gravatar_selctor =
        '#realm-icon-upload-widget .image-block[src^="https://secure.gravatar.com/avatar/"]';
    await page.waitForSelector(gravatar_selctor, {visible: true});
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {visible: false});

    await test_upload_realm_icon_image(page);
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {visible: true});

    await delete_realm_icon(page);
    await page.waitForSelector("#realm-icon-upload-widget .image-delete-button", {visible: false});
    await page.waitForSelector(gravatar_selctor, {visible: true});
}

async function submit_default_user_settings(page) {
    assert.strictEqual(
        await common.get_text_from_selector(page, "#org-submit-user-defaults"),
        "Save changes",
    );
    await page.click("#org-submit-user-defaults");
    const saved_status = '#org-submit-user-defaults[data-status="saved"]';
    await page.waitForSelector(saved_status, {visible: false});
}

async function test_change_organization_default_language(page) {
    console.log("Changing realm default language");
    await page.click("li[data-section='organization-settings']");
    await page.waitForSelector("#id_realm_default_language", {visible: true});

    await page.evaluate(() => $("#id_realm_default_language").val("de").change());
    await submit_default_user_settings(page);
}

async function test_authentication_methods(page) {
    await page.click("li[data-section='auth-methods']");
    await page.waitForSelector(".method_row[data-method='Google'] input[type='checkbox'] + span", {
        visible: true,
    });

    await page.click(".method_row[data-method='Google'] input[type='checkbox'] + span");
    const save_button = "#org-submit-auth_settings";
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
    await page.waitForFunction(
        () => !$(".method_row[data-method='Google'] input[type='checkbox']")[0].checked,
    );
}

async function admin_test(page) {
    await common.log_in(page);

    await common.manage_organization(page);
    await test_change_new_stream_notifications_setting(page);
    await test_change_signup_notifications_stream(page);
    await test_change_organization_default_language(page);

    await test_organization_permissions(page);
    await test_custom_realm_emoji(page);
    await test_default_streams(page);
    await test_organization_profile(page);
    await test_authentication_methods(page);
}

common.run_test(admin_test);
