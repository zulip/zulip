import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function navigate_using_left_sidebar(page: Page, stream_name: string): Promise<void> {
    console.log("Visiting #" + stream_name);
    const stream_id = await page.evaluate(() => zulip_test.get_sub("Verona")!.stream_id);
    await page.click(`.narrow-filter[data-stream-id="${stream_id}"] .stream-name`);
    await page.waitForSelector("#message_view_header .zulip-icon-hashtag", {visible: true});
}

async function open_menu(page: Page): Promise<void> {
    const menu_selector = "#settings-dropdown";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);
}

async function navigate_to_settings(page: Page): Promise<void> {
    console.log("Navigating to settings");

    await common.open_personal_menu(page);

    const settings_selector = "#personal-menu-dropdown a[href^='#settings']";
    await page.waitForSelector(settings_selector, {visible: true});
    await page.click(settings_selector);

    const profile_section_tab_selector = "li[data-section='profile']";
    await page.waitForSelector(profile_section_tab_selector, {visible: true});
    await page.click(profile_section_tab_selector);
    await page.waitForFunction(
        () => document.activeElement?.getAttribute("data-section") === "profile",
    );

    await page.click("#settings_page .content-wrapper .exit");
    // Wait until the overlay is completely closed.
    await page.waitForSelector("#settings_overlay_container", {hidden: true});
}

async function navigate_to_subscriptions(page: Page): Promise<void> {
    console.log("Navigate to subscriptions");

    await open_menu(page);

    const manage_streams_selector = '.link-item a[href^="#channels"]';
    await page.waitForSelector(manage_streams_selector, {visible: true});
    await page.click(manage_streams_selector);

    await page.waitForSelector("#subscription_overlay", {visible: true});

    await page.click("#subscription_overlay .exit");
    // Wait until the overlay is completely closed.
    await page.waitForSelector("#subscription_overlay", {hidden: true});
}

async function navigate_to_private_messages(page: Page): Promise<void> {
    console.log("Navigate to direct messages");

    const all_private_messages_icon = "#show-all-direct-messages";
    await page.waitForSelector(all_private_messages_icon, {visible: true});
    await page.click(all_private_messages_icon);

    await page.waitForSelector("#message_view_header .zulip-icon-user", {visible: true});
}

async function test_reload_hash(page: Page): Promise<void> {
    const initial_page_load_time = await page.evaluate(() => zulip_test.page_load_time);
    assert.ok(initial_page_load_time !== undefined);
    console.log(`initial load time: ${initial_page_load_time}`);

    const initial_hash = await page.evaluate(() => window.location.hash);

    await page.evaluate(() => {
        zulip_test.initiate_reload({immediate: true});
    });
    await page.waitForNavigation();
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await page.waitForSelector(`.message-list[data-message-list-id='${message_list_id}']`, {
        visible: true,
    });

    const page_load_time = await page.evaluate(() => zulip_test.page_load_time);
    assert.ok(page_load_time !== undefined);
    assert.ok(page_load_time > initial_page_load_time, "Page not reloaded.");

    const hash = await page.evaluate(() => window.location.hash);
    assert.strictEqual(hash, initial_hash, "Hash not preserved.");
}

async function navigation_tests(page: Page): Promise<void> {
    await common.log_in(page);

    await navigate_to_settings(page);

    await navigate_using_left_sidebar(page, "Verona");

    await page.click("#left-sidebar-navigation-list .home-link");
    await page.waitForSelector("#message_view_header .zulip-icon-all-messages", {visible: true});

    await navigate_to_subscriptions(page);

    await page.click("#left-sidebar-navigation-list .home-link");
    await page.waitForSelector("#message_view_header .zulip-icon-all-messages", {visible: true});

    await navigate_to_settings(page);
    await navigate_to_private_messages(page);
    await navigate_to_subscriptions(page);
    await navigate_using_left_sidebar(page, "Verona");

    await test_reload_hash(page);

    // Verify that we're narrowed to the target stream
    await page.waitForSelector(
        `xpath///*[@id="message_view_header"]//*[${common.has_class_x(
            "message-header-stream-settings-button",
        )} and normalize-space()="Verona"]`,
    );
}

common.run_test(navigation_tests);
