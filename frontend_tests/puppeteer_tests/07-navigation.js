"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

async function wait_for_tab(page, tab) {
    const tab_slector = `#${CSS.escape(tab)}.tab-pane.active`;
    await page.waitForSelector(tab_slector, {visible: true});
}

async function navigate_to(page, click_target, tab) {
    console.log("Visiting #" + click_target);
    await page.click(`a[href='#${CSS.escape(click_target)}']`);

    await wait_for_tab(page, tab);
}

async function open_menu(page) {
    const menu_selector = "#settings-dropdown";
    await page.waitForSelector(menu_selector, {visible: true});
    await page.click(menu_selector);
}

async function navigate_to_settings(page) {
    console.log("Navigating to settings");

    await open_menu(page);

    const settings_selector = "a[href^='#settings']";
    await page.waitForSelector(settings_selector, {visible: true});
    await page.click(settings_selector);

    await page.waitForSelector("#settings_page", {visible: true});

    await page.click("#settings_page .content-wrapper .exit");
}

async function navigate_to_subscriptions(page) {
    console.log("Navigate to subscriptions");

    await open_menu(page);

    const manage_streams_selector = 'a[href^="#streams"]';
    await page.waitForSelector(manage_streams_selector, {visible: true});
    await page.click(manage_streams_selector);

    await page.waitForSelector("#subscription_overlay", {visible: true});
    await page.waitForSelector("#subscriptions_table", {visible: true});

    await page.click("#subscription_overlay .exit");
}

async function test_reload_hash(page) {
    const initial_page_load_time = await page.evaluate(() => page_params.page_load_time);
    console.log("initial load time: " + initial_page_load_time);

    const initial_hash = await page.evaluate(() => window.location.hash);

    await page.evaluate(() => reload.initiate({immediate: true}));
    await page.waitForSelector("#zfilt", {visible: true});

    const page_load_time = await page.evaluate(() => page_params.page_load_time);
    assert(page_load_time > initial_page_load_time, "Page not reloaded.");

    const hash = await page.evaluate(() => window.location.hash);
    assert.strictEqual(hash, initial_hash, "Hash not preserved.");
}

async function navigation_tests(page) {
    await common.log_in(page);

    await navigate_to_settings(page);

    const verona_id = await page.evaluate(() => stream_data.get_stream_id("Verona"));
    const verona_narrow = `narrow/stream/${verona_id}-Verona`;

    await navigate_to(page, verona_narrow, "message_feed_container");

    // Hardcoded this instead of using `navigate_to`
    // as Puppeteer cannot click hidden elements.
    await page.evaluate(() => $("a[href='#message_feed_container]'").click());
    await wait_for_tab(page, "message_feed_container");

    await navigate_to_subscriptions(page);
    await navigate_to(page, "", "message_feed_container");
    await navigate_to_settings(page);
    await navigate_to(page, "narrow/is/private", "message_feed_container");
    await navigate_to_subscriptions(page);
    await navigate_to(page, verona_narrow, "message_feed_container");

    await test_reload_hash(page);

    // Verify that we're narrowed to the target stream
    await common.wait_for_text(page, "#message_view_header .stream", "Verona");

    await common.log_out(page);
}

common.run_test(navigation_tests);
