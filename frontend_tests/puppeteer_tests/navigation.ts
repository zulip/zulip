import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import common from "../puppeteer_lib/common";

async function wait_for_tab(page: Page, tab: string): Promise<void> {
    const tab_slector = `#${CSS.escape(tab)}.tab-pane`;
    await page.waitForSelector(tab_slector, {visible: true});
}

async function navigate_using_left_sidebar(
    page: Page,
    click_target: string,
    tab: string,
): Promise<void> {
    console.log("Visiting #" + click_target);
    await page.click(`#left-sidebar a[href='#${CSS.escape(click_target)}']`);

    await wait_for_tab(page, tab);
}

async function open_menu(page: Page): Promise<void> {
    const menu_selector = "#settings-dropdown";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);
}

async function navigate_to_settings(page: Page): Promise<void> {
    console.log("Navigating to settings");

    await open_menu(page);

    const settings_selector = ".dropdown-menu a[href^='#settings']";
    await page.waitForSelector(settings_selector, {visible: true});
    await page.click(settings_selector);

    await page.waitForSelector("#settings_page", {visible: true});
    await page.waitForFunction(() => location.href.includes("/#settings/")); // eslint-disable-line no-undef

    await page.click("#settings_page .content-wrapper .exit");
    // Wait until the overlay is completely closed.
    await page.waitForSelector("#settings_overlay_container", {hidden: true});
}

async function navigate_to_subscriptions(page: Page): Promise<void> {
    console.log("Navigate to subscriptions");

    await open_menu(page);

    const manage_streams_selector = '.dropdown-menu a[href^="#streams"]';
    await page.waitForSelector(manage_streams_selector, {visible: true});
    await page.click(manage_streams_selector);

    await page.waitForSelector("#subscription_overlay", {visible: true});
    await page.waitForSelector("#manage_streams_container", {visible: true});

    await page.click("#subscription_overlay .exit");
    // Wait until the overlay is completely closed.
    await page.waitForSelector("#subscription_overlay", {hidden: true});
}

async function test_reload_hash(page: Page): Promise<void> {
    const initial_page_load_time = await page.evaluate(
        (): number => zulip_test.page_params.page_load_time,
    );
    console.log(`initial load time: ${initial_page_load_time}`);

    const initial_hash = await page.evaluate(() => window.location.hash);

    await page.evaluate(() => zulip_test.initiate_reload({immediate: true}));
    await page.waitForNavigation();
    await page.waitForSelector("#zfilt", {visible: true});

    const page_load_time = await page.evaluate(() => zulip_test.page_params.page_load_time);
    assert.ok(page_load_time > initial_page_load_time, "Page not reloaded.");

    const hash = await page.evaluate(() => window.location.hash);
    assert.strictEqual(hash, initial_hash, "Hash not preserved.");
}

async function navigation_tests(page: Page): Promise<void> {
    await common.log_in(page);

    await navigate_to_settings(page);

    const verona_id = await page.evaluate((): number => zulip_test.get_stream_id("Verona"));
    const verona_narrow = `narrow/stream/${verona_id}-Verona`;

    await navigate_using_left_sidebar(page, verona_narrow, "message_feed_container");

    // Hardcoded this instead of using `navigate_to`
    // as Puppeteer cannot click hidden elements.
    await page.evaluate(() => $("a[href='#message_feed_container]'").trigger("click"));
    await wait_for_tab(page, "message_feed_container");

    await navigate_to_subscriptions(page);
    await navigate_using_left_sidebar(page, "all_messages", "message_feed_container");
    await navigate_to_settings(page);
    await navigate_using_left_sidebar(page, "narrow/is/private", "message_feed_container");
    await navigate_to_subscriptions(page);
    await navigate_using_left_sidebar(page, verona_narrow, "message_feed_container");

    await test_reload_hash(page);

    // Verify that we're narrowed to the target stream
    await page.waitForXPath(
        '//*[@id="message_view_header"]//*[@class="stream" and normalize-space()="Verona"]',
    );
}

common.run_test(navigation_tests);
