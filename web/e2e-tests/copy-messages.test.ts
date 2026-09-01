import assert from "node:assert/strict";

import type {Page} from "puppeteer";

import * as common from "./lib/common.ts";

type PartialSelectionConfig = {
    select_start_message_partially: boolean;
    select_end_message_partially: boolean;
    start_text_node_offset?: number;
    end_text_node_offset?: number;
};
async function copy_messages(
    page: Page,
    start_message: string,
    end_message: string,
    partial_selection_config?: PartialSelectionConfig,
): Promise<string[]> {
    return await page.evaluate(
        (
            start_message: string,
            end_message: string,
            partial_selection_config?: PartialSelectionConfig,
        ) => {
            function get_message_node(message: string): Element {
                return [...document.querySelectorAll(".message-list .message_content")].find(
                    (node) => node.textContent?.trim() === message,
                )!;
            }

            // select messages from start_message to end_message
            const selectedRange = document.createRange();
            if (partial_selection_config?.select_start_message_partially) {
                const offset = partial_selection_config.start_text_node_offset!;
                const start_message_text_node =
                    get_message_node(start_message).querySelector("p")?.firstChild;
                if (!(start_message_text_node instanceof Text)) {
                    throw new TypeError("Expected a Text node");
                }
                selectedRange.setStart(start_message_text_node, offset);
            } else {
                selectedRange.setStartBefore(get_message_node(start_message));
            }
            if (partial_selection_config?.select_end_message_partially) {
                const offset = partial_selection_config.end_text_node_offset!;
                const end_message_text_node =
                    get_message_node(end_message).querySelector("p")?.firstChild;
                if (!(end_message_text_node instanceof Text)) {
                    throw new TypeError("Expected a Text node");
                }
                // For the last message, the offset will be from the end of the message,
                // just like how selecting text in the browser would work.
                selectedRange.setEnd(end_message_text_node, end_message_text_node.length - offset);
            } else {
                selectedRange.setEndAfter(get_message_node(end_message));
            }
            window.getSelection()!.removeAllRanges();
            window.getSelection()!.addRange(selectedRange);

            // emulate copy event
            const clipboard_data = new DataTransfer();
            const copy_event = new ClipboardEvent("copy", {
                bubbles: true,
                cancelable: true,
                clipboardData: clipboard_data,
            });
            document.dispatchEvent(copy_event);

            const copied_html = clipboard_data.getData("text/html");

            // Convert the copied HTML into separate message strings
            const parser = new DOMParser();
            const doc = parser.parseFromString(copied_html, "text/html");

            // Empty paragraphs are inserted only to separate consecutive
            // messages with a blank line; skip them when collecting lines.
            return [...doc.body.children]
                .map((el) => el.textContent.trim())
                .filter((line) => line !== "");
        },
        start_message,
        end_message,
        partial_selection_config,
    );
}

async function test_copying_first_message_from_topic(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test C", "copy paste test C");
    const expected_copied_lines: string[] = [];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_last_message_from_topic(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test E", "copy paste test E");
    const expected_copied_lines: string[] = [];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_first_two_messages_from_topic(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test C", "copy paste test D");
    const expected_copied_lines = [
        "Desdemona:",
        "copy paste test C",
        "Desdemona:",
        "copy paste test D",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_all_messages_from_topic(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test C", "copy paste test E");
    const expected_copied_lines = [
        "Desdemona:",
        "copy paste test C",
        "Desdemona:",
        "copy paste test D",
        "Desdemona:",
        "copy paste test E",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_last_from_prev_first_from_next(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test B", "copy paste test C");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 | Today",
        "Desdemona:",
        "copy paste test B",
        "Verona > copy-paste-topic #2 | Today",
        "Desdemona:",
        "copy paste test C",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_last_from_prev_all_from_next(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test B", "copy paste test E");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 | Today",
        "Desdemona:",
        "copy paste test B",
        "Verona > copy-paste-topic #2 | Today",
        "Desdemona:",
        "copy paste test C",
        "Desdemona:",
        "copy paste test D",
        "Desdemona:",
        "copy paste test E",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_all_from_prev_first_from_next(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test A", "copy paste test C");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 | Today",
        "Desdemona:",
        "copy paste test A",
        "Desdemona:",
        "copy paste test B",
        "Verona > copy-paste-topic #2 | Today",
        "Desdemona:",
        "copy paste test C",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_messages_from_several_topics(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test B", "copy paste test F");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 | Today",
        "Desdemona:",
        "copy paste test B",
        "Verona > copy-paste-topic #2 | Today",
        "Desdemona:",
        "copy paste test C",
        "Desdemona:",
        "copy paste test D",
        "Desdemona:",
        "copy paste test E",
        "Verona > copy-paste-topic #3 | Today",
        "Desdemona:",
        "copy paste test F",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_timestamp_clipboard_has_datetime(page: Page): Promise<void> {
    // Verify that copying a rendered timestamp injects <span data-datetime> into the
    // selection HTML so Chrome's clipboard serializer cannot silently drop the datetime.
    const copied_html = await page.evaluate(() => {
        const time_el = document.querySelector<HTMLElement>(
            '.message-list time[datetime="2026-05-23T17:30:00Z"]',
        );
        if (!time_el) {
            return null;
        }
        const range = document.createRange();
        range.selectNodeContents(time_el);
        window.getSelection()!.removeAllRanges();
        window.getSelection()!.addRange(range);

        // Dispatch copy: copy_handler runs improve_time_selection_range, which
        // injects <span data-datetime> into the DOM and expands the range to
        // cover the full <time>. For a single-message selection copy_handler
        // returns false (browser handles clipboard natively), so the DataTransfer
        // stays empty — but the selection range now contains the mutated DOM.
        document.dispatchEvent(
            new ClipboardEvent("copy", {
                bubbles: true,
                cancelable: true,
                clipboardData: new DataTransfer(),
            }),
        );

        // Serialize the mutated, expanded selection: this is what Chrome writes
        // to the clipboard. Even when Chrome strips <time>, <span data-datetime>
        // survives as a plain span and the paste handler can recover <time:ISO>.
        const div = document.createElement("div");
        div.append(window.getSelection()!.getRangeAt(0).cloneContents());
        return div.innerHTML;
    });

    assert.ok(
        copied_html?.includes('data-datetime="2026-05-23T17:30:00Z"'),
        `Expected data-datetime="2026-05-23T17:30:00Z" in clipboard HTML, got: ${copied_html}`,
    );
}

async function test_multiple_message_selection_with_partially_selected_bookend_messages(
    page: Page,
): Promise<void> {
    const actual_copied_lines = await copy_messages(
        page,
        "copy paste test B",
        "copy paste test F",
        {
            select_start_message_partially: true,
            select_end_message_partially: true,
            start_text_node_offset: 5,
            end_text_node_offset: 7,
        },
    );
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 | Today",
        "Desdemona:",
        // w/o partial selection: "copy paste test B",
        "...paste test B",
        "Verona > copy-paste-topic #2 | Today",
        "Desdemona:",
        "copy paste test C",
        "Desdemona:",
        "copy paste test D",
        "Desdemona:",
        "copy paste test E",
        "Verona > copy-paste-topic #3 | Today",
        "Desdemona:",
        // w/o partial selection: "copy paste test F",
        "copy paste...",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function copy_paste_test(page: Page): Promise<void> {
    await common.log_in(page);
    await common.send_multiple_messages(page, [
        {
            stream_name: "Verona",
            topic: "copy-paste-topic #0",
            content: "<time:2026-05-23T17:30:00Z>",
        },

        {stream_name: "Verona", topic: "copy-paste-topic #1", content: "copy paste test A"},

        {stream_name: "Verona", topic: "copy-paste-topic #1", content: "copy paste test B"},

        {stream_name: "Verona", topic: "copy-paste-topic #2", content: "copy paste test C"},

        {stream_name: "Verona", topic: "copy-paste-topic #2", content: "copy paste test D"},

        {stream_name: "Verona", topic: "copy-paste-topic #2", content: "copy paste test E"},

        {stream_name: "Verona", topic: "copy-paste-topic #3", content: "copy paste test F"},

        {stream_name: "Verona", topic: "copy-paste-topic #3", content: "copy paste test G"},
    ]);

    await page.click("#left-sidebar-navigation-list .top_left_all_messages");
    const message_list_id = await common.get_current_msg_list_id(page, true);
    await common.check_messages_sent(page, message_list_id, [
        ["Verona > copy-paste-topic #0", ["Sat, May 23, 2026, 5:30 PM"]],
        ["Verona > copy-paste-topic #1", ["copy paste test A", "copy paste test B"]],
        [
            "Verona > copy-paste-topic #2",
            ["copy paste test C", "copy paste test D", "copy paste test E"],
        ],
        ["Verona > copy-paste-topic #3", ["copy paste test F", "copy paste test G"]],
    ]);
    console.log("Messages were sent successfully");

    await test_copying_first_message_from_topic(page);
    await test_copying_last_message_from_topic(page);
    await test_copying_first_two_messages_from_topic(page);
    await test_copying_all_messages_from_topic(page);
    await test_copying_last_from_prev_first_from_next(page);
    await test_copying_last_from_prev_all_from_next(page);
    await test_copying_all_from_prev_first_from_next(page);
    await test_copying_messages_from_several_topics(page);
    await test_timestamp_clipboard_has_datetime(page);
    await test_multiple_message_selection_with_partially_selected_bookend_messages(page);
}

await common.run_test(copy_paste_test);
