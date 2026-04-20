import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

const stream_name = "Verona";
const topic_name = "near-read-test";
const realm_url = "http://zulip.zulipdev.com:9981/";

async function get_stream_id(page: Page): Promise<number> {
    const stream_id = await common.get_stream_id(page, stream_name);
    assert.ok(stream_id !== undefined);
    return stream_id;
}

async function navigate_to_settings_preferences(page: Page): Promise<void> {
    await common.open_personal_menu(page);
    await page.waitForSelector("#personal-menu-dropdown a[href^='#settings']", {visible: true});
    await page.click("#personal-menu-dropdown a[href^='#settings']");
    await page.waitForSelector("#settings_overlay_container.show", {visible: true});
    await page.waitForSelector('[data-section="preferences"]', {visible: true});
    await page.click('[data-section="preferences"]');
    await page.waitForSelector("#user_web_mark_read_on_scroll_policy", {visible: true});
}

async function change_mark_read_policy(page: Page, value: string): Promise<void> {
    await navigate_to_settings_preferences(page);
    await page.select("#user_web_mark_read_on_scroll_policy", value);
    await page.waitForSelector("#user-preferences .general-settings-status", {visible: true});
    await page.click("#settings_page .content-wrapper .exit");
    await page.waitForSelector("#settings_overlay_container", {hidden: true});
}

// Test 1: A /near/ narrow is treated as a conversation view.
async function test_near_narrow_is_conversation_view(page: Page): Promise<void> {
    console.log("Testing that near narrow is treated as a conversation view");

    await common.send_message(page, "stream", {
        stream_name,
        topic: topic_name,
        content: "message for near narrow test",
    });

    const stream_id = await get_stream_id(page);
    const msg_id = await page.evaluate(() => zulip_test.current_msg_list?.last()?.id);
    assert.ok(msg_id !== undefined, "Expected a message to be sent and visible");

    // Navigate away from the topic, then come back via /near/ URL.
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await common.get_current_msg_list_id(page, true);

    await page.goto(
        `${realm_url}#narrow/channel/${stream_id}-${stream_name}/topic/${topic_name}/near/${msg_id}`,
    );
    await common.get_current_msg_list_id(page, true);

    const is_conversation_view = await page.evaluate(() =>
        zulip_test.current_msg_list?.data.filter.is_conversation_view(),
    );
    assert.ok(is_conversation_view, "Near narrow should be treated as a conversation view");

    const is_conversation_view_with_near = await page.evaluate(() =>
        zulip_test.current_msg_list?.data.filter.is_conversation_view_with_near(),
    );
    assert.ok(
        is_conversation_view_with_near,
        "Near narrow should still identify as is_conversation_view_with_near",
    );
}

// Test 2: The reading gate clears immediately when all messages in the
// near narrow are already read, enabling normal mark-as-read behavior.
async function test_near_narrow_reading_gate_clears(page: Page): Promise<void> {
    console.log("Testing that reading gate clears when no unread messages in near view");

    // We are on the near narrow from test 1; get the last message ID.
    const stream_id = await get_stream_id(page);
    const msg_id = await page.evaluate(() => zulip_test.current_msg_list?.last()?.id);
    assert.ok(msg_id !== undefined);

    // Navigate away, then return via /near/ URL.  All messages were
    // already marked as read in test 1 when we first visited this topic.
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await common.get_current_msg_list_id(page, true);

    await page.goto(
        `${realm_url}#narrow/channel/${stream_id}-${stream_name}/topic/${topic_name}/near/${msg_id}`,
    );
    await common.get_current_msg_list_id(page, true);

    // The not_found case fires immediately (no unreads), clearing the gate
    // and resuming reading via resume_reading().
    await page.waitForFunction(
        () => zulip_test.current_msg_list?.near_view_reading_gate_pending === false,
        {timeout: 5000},
    );
    const reading_prevented = await page.evaluate(
        () => zulip_test.current_msg_list?.reading_prevented,
    );
    assert.equal(
        reading_prevented,
        false,
        "reading_prevented should be false after gate clears with no unreads",
    );
}

// Test 3: With conversation_only policy, near views don't show the
// "not a conversation view" banner because they're treated as conversation views.
async function test_near_narrow_no_conversation_only_banner(page: Page): Promise<void> {
    console.log("Testing banner behavior in near narrow with conversation_only policy");

    // We are on the near narrow from test 2.
    const stream_id = await get_stream_id(page);
    const msg_id = await page.evaluate(() => zulip_test.current_msg_list?.last()?.id);
    assert.ok(msg_id !== undefined);

    // Change policy to "Only in conversation views".
    await change_mark_read_policy(page, "2");

    // Navigate to a channel-only narrow (not a conversation view).
    // update_unread_banner() always sets the banner HTML on narrow change, so
    // verify the banner text contains "conversation" without requiring the banner
    // to be visible (which requires an unread message + scroll to trigger).
    await page.goto(`${realm_url}#narrow/channel/${stream_id}-${stream_name}`);
    await common.get_current_msg_list_id(page, true);
    await page.waitForFunction(
        () =>
            (
                document.querySelector("#mark_as_read_turned_off_content")?.textContent ?? ""
            ).includes("conversation"),
        {timeout: 5000},
    );
    const channel_banner_text = await page.$eval(
        "#mark_as_read_turned_off_content",
        (el) => el.textContent ?? "",
    );
    assert.ok(
        channel_banner_text.includes("conversation"),
        "Channel narrow should use 'not a conversation view' banner template",
    );

    // Navigate to a near narrow.  It should not show the "not a
    // conversation view" banner since near views are now conversation views.
    await page.goto(
        `${realm_url}#narrow/channel/${stream_id}-${stream_name}/topic/${topic_name}/near/${msg_id}`,
    );
    await common.get_current_msg_list_id(page, true);

    // Wait for the reading gate to clear (all messages are read, so
    // maybe_resume_reading_for_near_view fires the not_found path).
    await page.waitForFunction(
        () => zulip_test.current_msg_list?.near_view_reading_gate_pending === false,
        {timeout: 5000},
    );

    const near_banner_text = await page.$eval(
        "#mark_as_read_turned_off_content",
        (el) => el.textContent ?? "",
    );
    assert.ok(
        !near_banner_text.includes("conversation"),
        "Near narrow should not show 'not a conversation view' banner",
    );

    // Reset the policy to "Always".
    await change_mark_read_policy(page, "1");
}

// Test 4: The reading gate only clears once the first unread message
// has scrolled into the visible area of the viewport.
async function test_near_narrow_gate_requires_scroll(page: Page): Promise<void> {
    console.log("Testing that gate requires first unread to be visible before marking as read");

    const gate_topic = "near-gate-test";
    const stream_id = await get_stream_id(page);

    // Send 15 messages so that, when anchored at the last one, the first
    // message is well above the viewport and the gate cannot clear until
    // the user scrolls back to the top.
    const msgs = Array.from({length: 15}, (_, i) => ({
        stream_name,
        topic: gate_topic,
        content: `gate test message ${i + 1}`,
    }));
    await common.send_multiple_messages(page, msgs);
    const msg_last_id = await page.evaluate(() => zulip_test.current_msg_list?.last()?.id);
    assert.ok(msg_last_id !== undefined);

    // Navigate to the combined feed (all sent messages are now marked as read).
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await common.get_current_msg_list_id(page, true);

    // Mark all messages in the topic as unread so the gate has something to gate on.
    await page.evaluate(
        (sid: number, topic: string) => {
            zulip_test.mark_topic_as_unread(sid, topic);
        },
        stream_id,
        gate_topic,
    );

    // Wait for the client's unread state to reflect the server's response.
    await page.waitForFunction(
        (sid: number, topic: string) => zulip_test.num_unread_for_topic(sid, topic) > 0,
        {timeout: 10000},
        stream_id,
        gate_topic,
    );

    // Navigate via /near/ anchored at the last message.  The first unread
    // (message 1) is above the viewport, so the gate should stay pending.
    await page.goto(
        `${realm_url}#narrow/channel/${stream_id}-${stream_name}/topic/${gate_topic}/near/${msg_last_id}`,
    );
    await common.get_current_msg_list_id(page, true);

    // Gate must still be pending: the first unread is above the visible area.
    const gate_pending = await page.evaluate(
        () => zulip_test.current_msg_list?.near_view_reading_gate_pending,
    );
    assert.ok(gate_pending, "Gate should be pending when first unread is above the viewport");
    let reading_prevented = await page.evaluate(
        () => zulip_test.current_msg_list?.reading_prevented,
    );
    assert.equal(
        reading_prevented,
        true,
        "reading_prevented should be false after scrolling first unread into view",
    );
    // Scroll to the top so the first unread enters the visible area, then
    // directly call maybe_resume_reading_for_near_view to check whether
    // the gate clears.  We call it directly (rather than relying on the
    // scroll handler) because the test scroll and the initial render's
    // anchor scroll share a debounce timer, causing scroll_finished() to
    // fire once with update_selection_on_next_scroll=false and skip the
    // gate check. This matches how render_message_list_with_selected_message
    // calls the function directly during the initial render.
    await page.evaluate(() => {
        document.documentElement.scrollTop = 0;
        zulip_test.current_msg_list?.maybe_resume_reading_for_near_view();
    });

    // The gate should now clear since the first unread is visible.
    await page.waitForFunction(
        () => zulip_test.current_msg_list?.near_view_reading_gate_pending === false,
        {timeout: 5000},
    );
    reading_prevented = await page.evaluate(() => zulip_test.current_msg_list?.reading_prevented);
    assert.equal(
        reading_prevented,
        false,
        "reading_prevented should be false after scrolling first unread into view",
    );
}

async function mark_messages_read_near_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    await common.get_current_msg_list_id(page, true);

    await test_near_narrow_is_conversation_view(page);
    await test_near_narrow_reading_gate_clears(page);
    await test_near_narrow_no_conversation_only_banner(page);
    await test_near_narrow_gate_requires_scroll(page);
}

await common.run_test(mark_messages_read_near_test);
