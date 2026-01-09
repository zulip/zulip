import assert from "node:assert/strict";
import {setTimeout as sleep} from "node:timers/promises";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

async function send_widget_message(
    page: Page,
    stream_name: string,
    topic: string,
    content: string,
    widget_content: object,
): Promise<void> {
    // Send a message with widget_content directly
    // This bypasses the outgoing webhook flow which doesn't work in e2e tests
    // because the queue worker isn't running with --streamlined
    await page.evaluate(
        async (stream: string, topic: string, content: string, widget_json: string) => {
            // Get CSRF token
            const csrf_token = document.querySelector<HTMLInputElement>(
                'input[name="csrfmiddlewaretoken"]',
            )?.value;

            const formData = new FormData();
            formData.append("type", "stream");
            formData.append("to", stream);
            formData.append("topic", topic);
            formData.append("content", content);
            formData.append("widget_content", widget_json);

            await fetch("/json/messages", {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrf_token ?? "",
                },
                body: formData,
            });
        },
        stream_name,
        topic,
        content,
        JSON.stringify(widget_content),
    );

    // Wait for message to be processed
    await sleep(2000);
}

async function test_rich_embed_widget(page: Page): Promise<void> {
    console.log("Testing rich embed widget...");

    // Send widget message directly (bypassing outgoing webhook which requires queue worker)
    const widget_content = {
        widget_type: "rich_embed",
        extra_data: {
            title: "Basic Embed Test",
            description: "This is a simple embed with just a title and description.",
            color: 3447003, // Blue
        },
    };

    await send_widget_message(
        page,
        "Verona",
        "widget-test",
        "**Rich Embed (Basic)** widget:",
        widget_content,
    );

    // Wait for widget to render
    await page.waitForSelector(".widget-rich-embed", {visible: true, timeout: 15000});

    // Verify basic embed elements
    const embed_title = await page.$(".widget-rich-embed .embed-title");
    assert.ok(embed_title, "Rich embed should have a title");

    const embed_description = await page.$(".widget-rich-embed .embed-description");
    assert.ok(embed_description, "Rich embed should have a description");

    console.log("Rich embed widget test passed");
}

async function test_rich_embed_full(page: Page): Promise<void> {
    console.log("Testing full-featured rich embed widget...");

    const widget_content = {
        widget_type: "rich_embed",
        extra_data: {
            title: "Full Embed Test",
            description: "This embed has all features enabled.",
            color: 15105570, // Orange
            author: {
                name: "Test Author",
            },
            fields: [
                {name: "Field 1", value: "Value 1", inline: true},
                {name: "Field 2", value: "Value 2", inline: true},
            ],
            footer: {
                text: "Footer text",
            },
        },
    };

    await send_widget_message(
        page,
        "Verona",
        "widget-test",
        "**Rich Embed (Full)** widget:",
        widget_content,
    );

    // Wait for widget with fields
    await page.waitForSelector(".widget-rich-embed .embed-fields", {visible: true, timeout: 15000});

    // Verify full embed elements
    const embed_author = await page.$(".widget-rich-embed .embed-author");
    assert.ok(embed_author, "Full rich embed should have an author");

    const embed_fields = await page.$$(".widget-rich-embed .embed-field");
    assert.ok(embed_fields.length > 0, "Full rich embed should have fields");

    const embed_footer = await page.$(".widget-rich-embed .embed-footer");
    assert.ok(embed_footer, "Full rich embed should have a footer");

    console.log("Full rich embed widget test passed");
}

async function test_button_widget(page: Page): Promise<void> {
    console.log("Testing interactive button widget...");

    const widget_content = {
        widget_type: "interactive",
        extra_data: {
            content: "Choose an option:",
            components: [
                {
                    type: "action_row",
                    components: [
                        {type: "button", label: "Primary", style: "primary", custom_id: "btn_primary"},
                        {type: "button", label: "Secondary", style: "secondary", custom_id: "btn_secondary"},
                        {type: "button", label: "Success", style: "success", custom_id: "btn_success"},
                        {type: "button", label: "Danger", style: "danger", custom_id: "btn_danger"},
                    ],
                },
            ],
        },
    };

    await send_widget_message(
        page,
        "Verona",
        "widget-test",
        "**Button Styles** widget:",
        widget_content,
    );

    // Wait for interactive widget with buttons
    await page.waitForSelector(".widget-interactive .widget-button", {visible: true, timeout: 15000});

    // Verify different button styles
    const primary_button = await page.$(".widget-button-primary");
    assert.ok(primary_button, "Should have a primary button");

    const secondary_button = await page.$(".widget-button-secondary");
    assert.ok(secondary_button, "Should have a secondary button");

    const success_button = await page.$(".widget-button-success");
    assert.ok(success_button, "Should have a success button");

    const danger_button = await page.$(".widget-button-danger");
    assert.ok(danger_button, "Should have a danger button");

    console.log("Button widget test passed");
}

async function test_select_menu_widget(page: Page): Promise<void> {
    console.log("Testing select menu widget...");

    const widget_content = {
        widget_type: "interactive",
        extra_data: {
            content: "Select options:",
            components: [
                {
                    type: "action_row",
                    components: [
                        {
                            type: "select_menu",
                            custom_id: "user_select",
                            placeholder: "Choose a user",
                            options: [
                                {label: "Alice", value: "user_alice", description: "First user"},
                                {label: "Bob", value: "user_bob", description: "Second user"},
                            ],
                        },
                    ],
                },
                {
                    type: "action_row",
                    components: [
                        {
                            type: "select_menu",
                            custom_id: "role_select",
                            placeholder: "Choose a role",
                            options: [
                                {label: "Admin", value: "role_admin"},
                                {label: "User", value: "role_user"},
                            ],
                        },
                    ],
                },
            ],
        },
    };

    await send_widget_message(
        page,
        "Verona",
        "widget-test",
        "**Select Menus** widget:",
        widget_content,
    );

    // Wait for select menus
    await page.waitForSelector(".widget-interactive .widget-select", {visible: true, timeout: 15000});

    const select_menus = await page.$$(".widget-select");
    assert.ok(select_menus.length >= 2, "Should have multiple select menus");

    console.log("Select menu widget test passed");
}

async function test_approval_workflow(page: Page): Promise<void> {
    console.log("Testing approval workflow widget...");

    const widget_content = {
        widget_type: "interactive",
        extra_data: {
            content: "Request #123 needs approval",
            components: [
                {
                    type: "action_row",
                    components: [
                        {type: "button", label: "Approve", style: "success", custom_id: "approve_123"},
                        {type: "button", label: "Reject", style: "danger", custom_id: "reject_123"},
                    ],
                },
            ],
        },
    };

    await send_widget_message(
        page,
        "Verona",
        "widget-test",
        "**Approval Workflow** widget:",
        widget_content,
    );

    // Wait for approval buttons
    await page.waitForSelector(".widget-interactive .widget-button-success", {visible: true, timeout: 15000});

    // Verify approve and reject buttons exist
    const approve_button = await page.$('.widget-button-success[data-custom-id^="approve"]');
    assert.ok(approve_button, "Should have an approve button");

    const reject_button = await page.$('.widget-button-danger[data-custom-id^="reject"]');
    assert.ok(reject_button, "Should have a reject button");

    console.log("Approval workflow test passed");
}

async function test_modal_widget(page: Page): Promise<void> {
    console.log("Testing modal widget...");

    // Test that a button with modal data can be rendered
    const widget_content = {
        widget_type: "interactive",
        extra_data: {
            content: "Click to open a form:",
            components: [
                {
                    type: "action_row",
                    components: [
                        {
                            type: "button",
                            label: "Open Feedback Form",
                            style: "primary",
                            custom_id: "open_feedback_modal",
                            modal: {
                                custom_id: "feedback_modal",
                                title: "Submit Feedback",
                                components: [
                                    {
                                        type: "action_row",
                                        components: [
                                            {
                                                type: "text_input",
                                                custom_id: "feedback_subject",
                                                label: "Subject",
                                                style: "short",
                                                placeholder: "Enter subject",
                                            },
                                        ],
                                    },
                                ],
                            },
                        },
                    ],
                },
            ],
        },
    };

    await send_widget_message(
        page,
        "Verona",
        "widget-test",
        "**Modal Forms** widget:",
        widget_content,
    );

    // Wait for button that opens modal
    await page.waitForSelector('.widget-button[data-custom-id="open_feedback_modal"]', {
        visible: true,
        timeout: 15000,
    });

    // Verify the button exists
    const modal_button = await page.$('.widget-button[data-custom-id="open_feedback_modal"]');
    assert.ok(modal_button, "Should have a button that opens a modal");

    console.log("Modal widget test passed");
}

export async function test_freeform_counter_widget(page: Page): Promise<void> {
    console.log("Testing freeform counter widget...");

    const widget_content = {
        widget_type: "freeform",
        extra_data: {
            html: `
                <div class="counter-widget">
                    <h3>Interactive Counter</h3>
                    <div class="counter-display">
                        <span id="count">0</span>
                    </div>
                    <div class="counter-buttons">
                        <button id="increment" class="btn btn-plus">+</button>
                        <button id="decrement" class="btn btn-minus">-</button>
                    </div>
                </div>
            `,
            css: `
                .counter-widget { text-align: center; padding: 15px; background: #f0f0f0; border-radius: 8px; }
                .counter-display { font-size: 32px; font-weight: bold; margin: 10px 0; }
                .btn { padding: 8px 16px; margin: 0 5px; border: none; border-radius: 4px; cursor: pointer; }
                .btn-plus { background: #22c55e; color: white; }
                .btn-minus { background: #ef4444; color: white; }
            `,
            js: `
                let count = 0;
                function updateDisplay() {
                    container.querySelector('#count').textContent = count;
                }
                ctx.on('click', '#increment', () => { count++; updateDisplay(); });
                ctx.on('click', '#decrement', () => { count--; updateDisplay(); });
            `,
        },
    };

    await send_widget_message(
        page,
        "Verona",
        "widget-test",
        "**Freeform Counter** widget:",
        widget_content,
    );

    // Wait for freeform widget to render
    await page.waitForSelector(".widget-freeform .counter-widget", {visible: true, timeout: 15000});

    // Verify counter elements exist
    const counter_display = await page.$(".widget-freeform #count");
    assert.ok(counter_display, "Counter should have a display element");

    const increment_btn = await page.$(".widget-freeform #increment");
    assert.ok(increment_btn, "Counter should have an increment button");

    // Test clicking the increment button
    await increment_btn.click();
    await sleep(100);

    // Verify count updated
    const count_text = await page.$eval(".widget-freeform #count", (el) => el.textContent);
    assert.equal(count_text, "1", "Count should be 1 after clicking increment");

    console.log("Freeform counter widget test passed");
}

export async function test_freeform_poll_widget(page: Page): Promise<void> {
    console.log("Testing freeform poll widget...");

    const widget_content = {
        widget_type: "freeform",
        extra_data: {
            html: `
                <div class="poll-widget">
                    <h3>Quick Poll</h3>
                    <div class="poll-options">
                        <button class="poll-option" data-option="a">Option A</button>
                        <button class="poll-option" data-option="b">Option B</button>
                    </div>
                    <div class="poll-results"></div>
                </div>
            `,
            css: `
                .poll-widget { padding: 15px; background: #e8f4f8; border-radius: 8px; }
                .poll-option { display: block; width: 100%; padding: 10px; margin: 5px 0; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor: pointer; }
                .poll-option:hover { background: #2563eb; }
            `,
        },
    };

    await send_widget_message(
        page,
        "Verona",
        "widget-test",
        "**Freeform Poll** widget:",
        widget_content,
    );

    // Wait for poll widget to render
    await page.waitForSelector(".widget-freeform .poll-widget", {visible: true, timeout: 15000});

    // Verify poll elements exist
    const poll_options = await page.$$(".widget-freeform .poll-option");
    assert.ok(poll_options.length >= 2, "Poll should have at least 2 options");

    console.log("Freeform poll widget test passed");
}

async function navigate_to_test_stream(page: Page): Promise<void> {
    // Navigate to the Verona stream
    await page.goto("http://zulip.zulipdev.com:9981/#narrow/stream/Verona/topic/widget-test");
    await page.waitForSelector("#message_view_header", {visible: true});
    await sleep(1000);
}

async function advanced_bot_widgets_test(page: Page): Promise<void> {
    // Note: This test sends widget messages directly rather than through an outgoing
    // webhook bot, because the e2e test server runs with --streamlined which doesn't
    // include the queue worker needed to process outgoing webhooks.

    // Log in
    await common.log_in(page);

    // Navigate to test stream
    await navigate_to_test_stream(page);

    // Run widget tests
    await test_rich_embed_widget(page);
    await test_rich_embed_full(page);
    await test_button_widget(page);
    await test_select_menu_widget(page);
    await test_approval_workflow(page);
    await test_modal_widget(page);
    // Note: Freeform widgets (test_freeform_counter_widget, test_freeform_poll_widget)
    // are exported but not called here - they require a trusted bot to send.
    // They cannot be sent by regular users for security reasons (they execute arbitrary JS).
    // These can only be tested via actual bot integration.

    console.log("All advanced bot widget tests passed!");
}

await common.run_test(advanced_bot_widgets_test);
