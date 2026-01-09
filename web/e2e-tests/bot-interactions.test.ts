/**
 * End-to-end tests for bot interactions.
 *
 * These tests run with --with-queue-worker flag which:
 * 1. Starts the test server WITHOUT --streamlined (includes queue workers)
 * 2. Starts a test bot HTTP server
 *
 * This allows us to test the full flow:
 * User clicks button -> API -> Queue -> Worker -> HTTP to bot -> Response processed
 *
 * Run with: ./tools/test-js-with-puppeteer --with-queue-worker bot-interactions
 */

import assert from "node:assert/strict";
import {setTimeout as sleep} from "node:timers/promises";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

const OUTGOING_WEBHOOK_BOT_TYPE = "3";
const BOT_SERVER_PORT = process.env["TEST_BOT_SERVER_PORT"] ?? "9877";
const BOT_SERVER_URL = `http://127.0.0.1:${BOT_SERVER_PORT}`;

interface BotInteractionRequest {
    type: string;
    token: string;
    bot_email: string;
    bot_full_name: string;
    interaction_type: string;
    custom_id: string;
    data: Record<string, unknown>;
    message: Record<string, unknown>;
    user: Record<string, unknown>;
}

async function reset_bot_server(): Promise<void> {
    await fetch(`${BOT_SERVER_URL}/control/reset`, {method: "POST"});
}

async function set_bot_response(response: Record<string, unknown>): Promise<void> {
    await fetch(`${BOT_SERVER_URL}/control/response`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(response),
    });
}

async function get_bot_requests(): Promise<BotInteractionRequest[]> {
    const response = await fetch(`${BOT_SERVER_URL}/control/requests`);
    const data = (await response.json()) as {requests: BotInteractionRequest[]};
    return data.requests;
}

async function wait_for_bot_request(timeout_ms: number = 10000): Promise<BotInteractionRequest> {
    const start = Date.now();
    while (Date.now() - start < timeout_ms) {
        const requests = await get_bot_requests();
        if (requests.length > 0) {
            return requests[requests.length - 1]!;
        }
        await sleep(200);
    }
    throw new Error("Timeout waiting for bot to receive interaction");
}

async function navigate_to_settings_bots(page: Page): Promise<void> {
    await page.goto("http://zulip.zulipdev.com:9981/#settings/your-bots");
    await page.waitForSelector("#admin-bot-list", {visible: true});
    await sleep(500);
}

interface BotCredentials {
    user_id: number;
    email: string;
    api_key: string;
}

async function create_webhook_bot(
    page: Page,
    bot_name: string,
    bot_short_name: string,
    webhook_url: string,
): Promise<BotCredentials> {
    // Click add new bot button
    await page.click("#admin-bot-list .add-a-new-bot");
    await common.wait_for_micromodal_to_open(page);

    // Fill the bot creation form
    await common.fill_form(page, "#create_bot_form", {
        bot_name,
        bot_short_name,
        bot_type: OUTGOING_WEBHOOK_BOT_TYPE,
        payload_url: webhook_url,
    });

    // Submit
    await page.click(".micromodal .dialog_submit_button");
    await common.wait_for_micromodal_to_close(page);

    // Wait for bot to appear in list
    await sleep(1000);

    // Get the bot's user ID
    const user_id = await common.get_user_id_from_name(page, bot_name);
    assert.ok(user_id, `Failed to get user_id for bot ${bot_name}`);

    // Open bot management modal to get API key
    const manage_button_selector = `#admin_your_bots_table .user_row[data-user-id="${user_id}"] .manage-user-button`;
    await page.waitForSelector(manage_button_selector, {visible: true});
    await page.click(manage_button_selector);
    await common.wait_for_micromodal_to_open(page);

    // Click the download zuliprc button to populate the hidden link
    const download_zuliprc_selector = ".download-bot-zuliprc";
    await page.waitForSelector(download_zuliprc_selector, {visible: true});
    await page.click(download_zuliprc_selector);

    // Get the bot's email and API key from the hidden zuliprc download link
    const zuliprc_selector = ".micromodal .hidden-zuliprc-download";
    await page.waitForSelector(`${zuliprc_selector}[href^="data:"]`);

    const zuliprc_content = await page.$eval(zuliprc_selector, (el) => {
        const href = (el as HTMLAnchorElement).href;
        return decodeURIComponent(href.replace("data:application/octet-stream;charset=utf-8,", ""));
    });

    // Parse the zuliprc content to get email and key
    const email_match = zuliprc_content.match(/email=(.+)/);
    const key_match = zuliprc_content.match(/key=(.+)/);
    assert.ok(email_match && key_match, "Failed to extract bot credentials from zuliprc");

    const email = email_match[1]!.trim();
    const api_key = key_match[1]!.trim();

    // Close the modal
    await page.click(".micromodal .modal__close");
    await common.wait_for_micromodal_to_close(page);

    return {user_id, email, api_key};
}

async function send_widget_message_as_bot(
    bot: BotCredentials,
    stream_name: string,
    topic: string,
    content: string,
    widget_content: object,
): Promise<void> {
    // Send message using bot's API credentials (Basic Auth)
    const auth = Buffer.from(`${bot.email}:${bot.api_key}`).toString("base64");

    const formData = new URLSearchParams();
    formData.append("type", "stream");
    formData.append("to", stream_name);
    formData.append("topic", topic);
    formData.append("content", content);
    formData.append("widget_content", JSON.stringify(widget_content));

    const response = await fetch("http://zulip.zulipdev.com:9981/api/v1/messages", {
        method: "POST",
        headers: {
            Authorization: `Basic ${auth}`,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        body: formData.toString(),
    });

    if (!response.ok) {
        const text = await response.text();
        throw new Error(`Failed to send message as bot: ${response.status} - ${text}`);
    }

    await sleep(2000);
}

async function navigate_to_stream_topic(
    page: Page,
    stream_name: string,
    topic: string,
): Promise<void> {
    await page.goto(
        `http://zulip.zulipdev.com:9981/#narrow/stream/${encodeURIComponent(stream_name)}/topic/${encodeURIComponent(topic)}`,
    );
    await page.waitForSelector("#message_view_header", {visible: true});
    await sleep(1000);
}

async function test_button_click_interaction(page: Page, bot: BotCredentials): Promise<void> {
    console.log("Testing button click interaction...");

    await reset_bot_server();

    // Navigate to the stream
    await navigate_to_stream_topic(page, "Verona", "bot-interaction-test");

    // Send a widget message with a button (buttons must be wrapped in action_row)
    // IMPORTANT: The message must be sent BY the bot so interactions are routed to it
    const widget_content = {
        widget_type: "interactive",
        extra_data: {
            content: "Test interaction:",
            components: [
                {
                    type: "action_row",
                    components: [
                        {
                            type: "button",
                            custom_id: "test_button_1",
                            label: "Click Me",
                            style: "primary",
                        },
                    ],
                },
            ],
        },
    };

    await send_widget_message_as_bot(
        bot,
        "Verona",
        "bot-interaction-test",
        "Test button interaction:",
        widget_content,
    );

    // Wait for the widget to render
    await page.waitForSelector('.widget-interactive button[data-custom-id="test_button_1"]', {
        visible: true,
        timeout: 15000,
    });

    // Click the button
    await page.click('.widget-interactive button[data-custom-id="test_button_1"]');

    // Wait for the interaction to be delivered to the bot server
    const interaction = await wait_for_bot_request();

    // Verify the interaction payload
    assert.equal(interaction.type, "interaction", "Should be an interaction event");
    assert.equal(interaction.interaction_type, "button_click", "Should be a button_click");
    assert.equal(interaction.custom_id, "test_button_1", "Should have correct custom_id");
    assert.ok(interaction.message, "Should include message context");
    assert.ok(interaction.user, "Should include user context");

    console.log("Button click interaction test passed!");
}

async function test_select_menu_interaction(page: Page, bot: BotCredentials): Promise<void> {
    console.log("Testing select menu interaction...");

    await reset_bot_server();

    // Navigate to the stream
    await navigate_to_stream_topic(page, "Verona", "bot-interaction-test-2");

    // Send a widget message with a select menu (must be wrapped in action_row)
    const widget_content = {
        widget_type: "interactive",
        extra_data: {
            content: "Select an option:",
            components: [
                {
                    type: "action_row",
                    components: [
                        {
                            type: "select_menu",
                            custom_id: "test_select_1",
                            placeholder: "Choose an option",
                            options: [
                                {label: "Option A", value: "a"},
                                {label: "Option B", value: "b"},
                                {label: "Option C", value: "c"},
                            ],
                        },
                    ],
                },
            ],
        },
    };

    await send_widget_message_as_bot(
        bot,
        "Verona",
        "bot-interaction-test-2",
        "Test select menu:",
        widget_content,
    );

    // Wait for the widget to render
    await page.waitForSelector('.widget-interactive select[data-custom-id="test_select_1"]', {
        visible: true,
        timeout: 15000,
    });

    // Select an option
    await page.select('.widget-interactive select[data-custom-id="test_select_1"]', "b");

    // Wait for the interaction to be delivered to the bot server
    const interaction = await wait_for_bot_request();

    // Verify the interaction payload
    assert.equal(interaction.type, "interaction", "Should be an interaction event");
    assert.equal(interaction.interaction_type, "select_menu", "Should be a select_menu");
    assert.equal(interaction.custom_id, "test_select_1", "Should have correct custom_id");
    assert.deepEqual(interaction.data, {values: ["b"]}, "Should have selected value");

    console.log("Select menu interaction test passed!");
}

async function test_bot_response_creates_message(page: Page, bot: BotCredentials): Promise<void> {
    console.log("Testing bot response creates message...");

    await reset_bot_server();

    // Configure the bot to respond with a message
    await set_bot_response({
        content: "I received your button click!",
    });

    // Navigate to the stream
    await navigate_to_stream_topic(page, "Verona", "bot-interaction-test-3");

    // Send a widget message with a button (must be wrapped in action_row)
    const widget_content = {
        widget_type: "interactive",
        extra_data: {
            content: "Click to get response:",
            components: [
                {
                    type: "action_row",
                    components: [
                        {
                            type: "button",
                            custom_id: "response_test_button",
                            label: "Get Response",
                            style: "primary",
                        },
                    ],
                },
            ],
        },
    };

    await send_widget_message_as_bot(
        bot,
        "Verona",
        "bot-interaction-test-3",
        "Click for response:",
        widget_content,
    );

    // Wait for the widget to render
    await page.waitForSelector(
        '.widget-interactive button[data-custom-id="response_test_button"]',
        {
            visible: true,
            timeout: 15000,
        },
    );

    // Click the button
    await page.click('.widget-interactive button[data-custom-id="response_test_button"]');

    // Wait for the bot's response message to appear
    // Use waitForFunction since Puppeteer doesn't support :has-text selector
    await page.waitForFunction(
        (expectedText) => {
            const messages = document.querySelectorAll(".message_content");
            for (const msg of messages) {
                if (msg.textContent?.includes(expectedText)) {
                    return true;
                }
            }
            return false;
        },
        {timeout: 20000},
        "I received your button click!",
    );

    console.log("Bot response creates message test passed!");
}

async function bot_interactions_test(page: Page): Promise<void> {
    // Verify test bot server is available
    try {
        const health_response = await fetch(`${BOT_SERVER_URL}/control/health`);
        if (!health_response.ok) {
            throw new Error("Bot server not healthy");
        }
    } catch (error) {
        console.error(
            "Test bot server is not available. Run with --with-queue-worker flag to start it.",
        );
        throw error;
    }

    console.log(`Test bot server available at ${BOT_SERVER_URL}`);

    // Log in
    await common.log_in(page);

    // Create a webhook bot pointing to our test server
    await navigate_to_settings_bots(page);
    const bot = await create_webhook_bot(
        page,
        "Interaction Test Bot",
        "interaction-test",
        BOT_SERVER_URL,
    );
    console.log(`Created webhook bot with user_id: ${bot.user_id}, email: ${bot.email}`);

    // Run interaction tests - pass bot credentials so messages are sent AS the bot
    await test_button_click_interaction(page, bot);
    await test_select_menu_interaction(page, bot);
    await test_bot_response_creates_message(page, bot);

    console.log("All bot interaction e2e tests passed!");
}

await common.run_test(bot_interactions_test);
