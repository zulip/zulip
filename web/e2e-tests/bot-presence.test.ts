import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function get_all_bot_ids(page: Page): Promise<number[]> {
    // Get all bot user IDs using zulip_test helper
    return await page.evaluate(() => zulip_test.get_bot_ids());
}

async function test_bots_section_exists(page: Page): Promise<void> {
    console.log("Testing that bots section exists in sidebar");

    // Wait for the right sidebar to load - the user-list-filter is always visible
    await page.waitForSelector(".user-list-filter", {visible: true, timeout: 30000});

    // Check that the bots container exists in the DOM (it might have no-display class)
    const bots_container = await page.$("#buddy-list-bots-container");
    assert.ok(bots_container, "Bots container should exist in the sidebar");
}

async function test_bot_presence_updates(page: Page): Promise<void> {
    console.log("Testing bot presence updates");

    // Get all bot IDs
    const bot_ids = await get_all_bot_ids(page);
    console.log(`Found ${bot_ids.length} bots in the realm`);

    if (bot_ids.length === 0) {
        console.log("No bots found in test realm, skipping presence update test");
        return;
    }

    const test_bot_id = bot_ids[0]!;
    console.log(`Testing with bot ID: ${test_bot_id}`);

    // Set bot as connected using the unified presence system
    // For bots, active_timestamp set = connected, null = disconnected
    const now = Date.now() / 1000;
    await page.evaluate(
        (bot_id: number, timestamp: number) => {
            zulip_test.update_presence(
                bot_id,
                {active_timestamp: timestamp, idle_timestamp: timestamp, is_bot: true},
                timestamp,
            );
        },
        test_bot_id,
        now,
    );

    // Trigger a redraw of the buddy list
    await page.evaluate(() => {
        zulip_test.redraw_buddy_list();
    });

    // Wait a moment for the UI to update
    await page.waitForFunction(
        (bot_id: number) => {
            return zulip_test.is_bot_connected(bot_id);
        },
        {},
        test_bot_id,
    );

    // Verify the bot is now connected
    const is_connected = await page.evaluate((bot_id: number) => {
        return zulip_test.is_bot_connected(bot_id);
    }, test_bot_id);

    assert.ok(is_connected, "Bot should be connected after update");

    // Now disconnect the bot (set active_timestamp to undefined)
    await page.evaluate(
        (bot_id: number, timestamp: number) => {
            zulip_test.update_presence(
                bot_id,
                {active_timestamp: undefined, idle_timestamp: timestamp, is_bot: true},
                timestamp,
            );
        },
        test_bot_id,
        now,
    );

    // Trigger a redraw
    await page.evaluate(() => {
        zulip_test.redraw_buddy_list();
    });

    // Verify the bot is now disconnected
    const is_still_connected = await page.evaluate((bot_id: number) => {
        return zulip_test.is_bot_connected(bot_id);
    }, test_bot_id);

    assert.ok(!is_still_connected, "Bot should be disconnected after update");
}

async function test_bot_presence_indicator_classes(page: Page): Promise<void> {
    console.log("Testing bot presence indicator CSS classes");

    const bot_ids = await get_all_bot_ids(page);
    if (bot_ids.length === 0) {
        console.log("No bots found in test realm, skipping presence indicator test");
        return;
    }

    const test_bot_id = bot_ids[0]!;
    const now = Date.now() / 1000;

    // Set bot as connected
    await page.evaluate(
        (bot_id: number, timestamp: number) => {
            zulip_test.update_presence(
                bot_id,
                {active_timestamp: timestamp, idle_timestamp: timestamp, is_bot: true},
                timestamp,
            );
        },
        test_bot_id,
        now,
    );

    await page.evaluate(() => {
        zulip_test.redraw_buddy_list();
    });

    // Check that the connected class is used for the presence indicator
    // The buddy_data.get_user_circle_class should return "user-circle-bot" for connected bots
    const circle_class = await page.evaluate((bot_id: number) => {
        return zulip_test.get_user_circle_class(bot_id);
    }, test_bot_id);

    assert.equal(circle_class, "user-circle-bot", "Connected bot should have user-circle-bot class");

    // Set bot as disconnected
    await page.evaluate(
        (bot_id: number, timestamp: number) => {
            zulip_test.update_presence(
                bot_id,
                {active_timestamp: undefined, idle_timestamp: timestamp, is_bot: true},
                timestamp,
            );
        },
        test_bot_id,
        now,
    );

    await page.evaluate(() => {
        zulip_test.redraw_buddy_list();
    });

    // Check that the offline class is used for disconnected bots
    const offline_class = await page.evaluate((bot_id: number) => {
        return zulip_test.get_user_circle_class(bot_id);
    }, test_bot_id);

    assert.equal(
        offline_class,
        "user-circle-offline",
        "Disconnected bot should have user-circle-offline class",
    );
}

async function bot_presence_test(page: Page): Promise<void> {
    await common.log_in(page);
    await test_bots_section_exists(page);
    await test_bot_presence_updates(page);
    await test_bot_presence_indicator_classes(page);
}

await common.run_test(bot_presence_test);
