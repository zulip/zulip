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

type CopyRangeEndpoint = {
    role: "message_time" | "sender" | "content" | "topic_header" | "reminder";
    content: string;
};

async function copy_custom_range(
    page: Page,
    start: CopyRangeEndpoint,
    end: CopyRangeEndpoint,
    split_into_disjoint_ranges = false,
    end_text_node_offset?: number,
): Promise<{
    default_prevented: boolean;
    copied_lines: string[];
    selection_text: string;
    range_count: number;
}> {
    return await page.evaluate(
        (
            start: CopyRangeEndpoint,
            end: CopyRangeEndpoint,
            split_into_disjoint_ranges: boolean,
            end_text_node_offset: number | undefined,
        ) => {
            function find_content(text: string): Element {
                const node = [...document.querySelectorAll(".message-list .message_content")].find(
                    (candidate) => candidate.textContent?.trim() === text,
                );
                if (!node) {
                    throw new Error(`Expected message content: ${text}`);
                }
                return node;
            }

            function endpoint_node(endpoint: CopyRangeEndpoint): Node {
                if (endpoint.role === "topic_header") {
                    const header = document.querySelector(
                        `.message-list .message_header[data-topic-name="${CSS.escape(endpoint.content)}"]`,
                    );
                    const header_contents = header?.querySelector(".message-header-contents");
                    if (!header_contents) {
                        throw new Error(`Expected topic header: ${endpoint.content}`);
                    }
                    return header_contents;
                }
                const content = find_content(endpoint.content);
                const row = content.closest(".message_row");
                if (!row) {
                    throw new Error("Expected a message row");
                }
                if (endpoint.role === "content") {
                    return content;
                }
                if (endpoint.role === "sender") {
                    const sender = row.querySelector(".sender_name");
                    if (!sender) {
                        throw new Error("Expected a sender name");
                    }
                    return sender;
                }
                if (endpoint.role === "reminder") {
                    const reminder = row.querySelector(".message-reminder");
                    if (!reminder) {
                        throw new Error("Expected a reminder");
                    }
                    return reminder;
                }
                const time = row.querySelector(".message-time");
                if (!time) {
                    throw new Error("Expected a message timestamp");
                }
                return time;
            }

            const start_node = endpoint_node(start);
            const end_node = endpoint_node(end);
            const selection = window.getSelection()!;
            selection.removeAllRanges();
            if (split_into_disjoint_ranges) {
                // Firefox <147 does this around `user-select: none`
                // nodes. Chrome usually keeps only the first range.
                const start_range = document.createRange();
                start_range.selectNode(start_node);
                selection.addRange(start_range);
                const end_range = document.createRange();
                end_range.selectNode(end_node);
                selection.addRange(end_range);
            } else {
                const range = document.createRange();
                range.setStartBefore(start_node);
                if (end_text_node_offset !== undefined) {
                    const end_text = find_content(end.content).querySelector("p")?.firstChild;
                    if (!(end_text instanceof Text)) {
                        throw new TypeError("Expected a Text node");
                    }
                    range.setEnd(end_text, end_text.length - end_text_node_offset);
                } else {
                    range.setEndAfter(end_node);
                }
                selection.addRange(range);
            }

            const clipboard_data = new DataTransfer();
            const copy_event = new ClipboardEvent("copy", {
                bubbles: true,
                cancelable: true,
                clipboardData: clipboard_data,
            });
            document.dispatchEvent(copy_event);

            const copied_html = clipboard_data.getData("text/html");
            const parser = new DOMParser();
            const doc = parser.parseFromString(copied_html, "text/html");
            return {
                default_prevented: copy_event.defaultPrevented,
                copied_lines: [...doc.body.children]
                    .map((el) => el.textContent.trim())
                    .filter((line) => line !== ""),
                selection_text: window.getSelection()!.toString(),
                range_count: window.getSelection()!.rangeCount,
            };
        },
        start,
        end,
        split_into_disjoint_ranges,
        end_text_node_offset,
    );
}

async function test_copying_selection_with_no_message_content(page: Page): Promise<void> {
    // A recipient header plus the first message's sender name has no
    // `.message_content`.
    const result = await page.evaluate(() => {
        const header = document.querySelector(
            '.message-list .message_header[data-topic-name="copy-paste-topic #2"]',
        );
        const sender_name = header
            ?.closest(".recipient_row")
            ?.querySelector(":scope .message_row .sender_name");
        const header_contents = header?.querySelector(".message-header-contents");
        if (!header_contents || !sender_name) {
            throw new Error("Expected topic header and sender name");
        }

        const range = document.createRange();
        range.setStart(header_contents, 0);
        range.setEndAfter(sender_name);
        window.getSelection()!.removeAllRanges();
        window.getSelection()!.addRange(range);

        const clipboard_data = new DataTransfer();
        const copy_event = new ClipboardEvent("copy", {
            bubbles: true,
            cancelable: true,
            clipboardData: clipboard_data,
        });
        document.dispatchEvent(copy_event);

        return {
            default_prevented: copy_event.defaultPrevented,
            copied_html: clipboard_data.getData("text/html"),
            copied_text: clipboard_data.getData("text/plain"),
            selection_text: window.getSelection()!.toString(),
        };
    });

    // Synthetic ClipboardEvent: native copy does not fill clipboard_data.
    // defaultPrevented === false is what shows the handler stepped aside.
    assert.equal(result.default_prevented, false);
    assert.equal(result.copied_html, "");
    assert.equal(result.copied_text, "");
    assert.ok(result.selection_text.includes("Desdemona"));
}

async function test_copying_me_timestamp_through_next_sender(page: Page): Promise<void> {
    // /me timestamp through the next sender: no message body.
    const result = await copy_custom_range(
        page,
        {role: "message_time", content: "is posing for copy tests"},
        {role: "sender", content: "regular after me for copy tests"},
    );
    assert.equal(result.default_prevented, false);
    assert.deepStrictEqual(result.copied_lines, []);
    assert.ok(result.selection_text.includes("Desdemona"));
}

async function test_copying_me_timestamp_through_next_body(page: Page): Promise<void> {
    // /me timestamp through the next message body.
    const result = await copy_custom_range(
        page,
        {role: "message_time", content: "is posing for copy tests"},
        {role: "content", content: "regular after me for copy tests"},
    );
    assert.equal(result.default_prevented, true);
    assert.deepStrictEqual(result.copied_lines, ["Desdemona:", "regular after me for copy tests"]);
}

async function test_copying_me_timestamp_through_partial_next_body(page: Page): Promise<void> {
    const result = await copy_custom_range(
        page,
        {role: "message_time", content: "is posing for copy tests"},
        {role: "content", content: "regular after me for copy tests"},
        false,
        6,
    );
    assert.equal(result.default_prevented, true);
    assert.deepStrictEqual(result.copied_lines, ["Desdemona:", "regular after me for copy..."]);
}

async function test_copying_me_timestamp_through_later_sender(page: Page): Promise<void> {
    // /me timestamp through a later /me sender.
    const result = await copy_custom_range(
        page,
        {role: "message_time", content: "is posing for copy tests"},
        {role: "sender", content: "is posing again for copy tests"},
    );
    assert.equal(result.default_prevented, true);
    assert.deepStrictEqual(result.copied_lines, [
        "Desdemona:",
        "regular after me for copy tests",
        "Desdemona:",
        "regular last after two mes",
    ]);
}

async function test_copying_me_timestamp_through_later_body(page: Page): Promise<void> {
    const result = await copy_custom_range(
        page,
        {role: "message_time", content: "is posing for copy tests"},
        {role: "content", content: "regular last after two mes"},
    );
    assert.equal(result.default_prevented, true);
    assert.deepStrictEqual(result.copied_lines, [
        "Desdemona:",
        "regular after me for copy tests",
        "Desdemona:",
        "regular last after two mes",
    ]);
}

async function test_copying_disjoint_ranges_with_no_message_content(page: Page): Promise<void> {
    // Firefox <147 splits a selection around `user-select: none`.
    const header_and_sender = await copy_custom_range(
        page,
        {role: "topic_header", content: "copy-paste-topic #2"},
        {role: "sender", content: "copy paste test C"},
        true,
    );
    assert.ok(header_and_sender.range_count >= 1);
    assert.equal(header_and_sender.default_prevented, false);
    assert.deepStrictEqual(header_and_sender.copied_lines, []);

    const me_time_and_next_sender = await copy_custom_range(
        page,
        {role: "message_time", content: "is posing for copy tests"},
        {role: "sender", content: "regular after me for copy tests"},
        true,
    );
    assert.ok(me_time_and_next_sender.range_count >= 1);
    assert.equal(me_time_and_next_sender.default_prevented, false);
    assert.deepStrictEqual(me_time_and_next_sender.copied_lines, []);
}

async function test_copying_disjoint_ranges_with_later_body(page: Page): Promise<void> {
    // Firefox <147: disjoint /me timestamp range and next-body range.
    const result = await copy_custom_range(
        page,
        {role: "message_time", content: "is posing for copy tests"},
        {role: "content", content: "regular after me for copy tests"},
        true,
    );
    if (result.range_count > 1) {
        assert.equal(result.default_prevented, true);
        assert.deepStrictEqual(result.copied_lines, [
            "Desdemona:",
            "regular after me for copy tests",
        ]);
    } else {
        // Chrome ignored the second range; a lone /me timestamp is a
        // same-message selection and is copied natively.
        assert.equal(result.default_prevented, false);
        assert.deepStrictEqual(result.copied_lines, []);
    }
}

async function schedule_reminder_on_message(page: Page, content: string): Promise<void> {
    await page.evaluate(async (content: string) => {
        const node = [...document.querySelectorAll(".message-list .message_content")].find(
            (candidate) => candidate.textContent?.trim() === content,
        );
        const message_id = node?.closest(".message_row")?.getAttribute("data-message-id");
        const csrf = document.querySelector<HTMLInputElement>(
            "input[name=csrfmiddlewaretoken]",
        )?.value;
        if (!message_id || !csrf) {
            throw new Error("Expected message id and csrf token");
        }
        const res = await fetch("/json/reminders", {
            method: "POST",
            headers: {
                "X-CSRFToken": csrf,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body: new URLSearchParams({
                message_id,
                scheduled_delivery_timestamp: String(Math.floor(Date.now() / 1000) + 86400),
            }),
        });
        if (!res.ok) {
            throw new Error(`Failed to schedule reminder: ${res.status}`);
        }
    }, content);
    await page.waitForSelector(".message-list .message-reminder", {visible: true});
}

async function test_copying_from_reminder_through_next_body(page: Page): Promise<void> {
    // Reminder text through the next message.
    await schedule_reminder_on_message(page, "copy paste test F");
    const regular_through_body = await copy_custom_range(
        page,
        {role: "reminder", content: "copy paste test F"},
        {role: "content", content: "copy paste test G"},
    );
    assert.equal(regular_through_body.default_prevented, true);
    assert.deepStrictEqual(regular_through_body.copied_lines, ["Desdemona:", "copy paste test G"]);

    await schedule_reminder_on_message(page, "is posing for copy tests");
    const through_sender = await copy_custom_range(
        page,
        {role: "reminder", content: "is posing for copy tests"},
        {role: "sender", content: "regular after me for copy tests"},
    );
    assert.equal(through_sender.default_prevented, false);
    assert.deepStrictEqual(through_sender.copied_lines, []);

    const through_body = await copy_custom_range(
        page,
        {role: "reminder", content: "is posing for copy tests"},
        {role: "content", content: "regular after me for copy tests"},
    );
    assert.equal(through_body.default_prevented, true);
    assert.deepStrictEqual(through_body.copied_lines, [
        "Desdemona:",
        "regular after me for copy tests",
    ]);
}

async function test_copying_through_trailing_sender_name(page: Page): Promise<void> {
    // Selection ends on a sender name.
    const result = await copy_custom_range(
        page,
        {role: "content", content: "is posing for copy tests"},
        {role: "sender", content: "regular after me for copy tests"},
    );
    assert.equal(result.default_prevented, true);
    assert.deepStrictEqual(result.copied_lines, ["Desdemona:", "is posing for copy tests"]);
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

        {
            stream_name: "Verona",
            topic: "copy-paste-topic #4",
            content: "/me is posing for copy tests",
        },

        {
            stream_name: "Verona",
            topic: "copy-paste-topic #4",
            content: "regular after me for copy tests",
        },

        {
            stream_name: "Verona",
            topic: "copy-paste-topic #4",
            content: "regular last after two mes",
        },

        {
            stream_name: "Verona",
            topic: "copy-paste-topic #4",
            content: "/me is posing again for copy tests",
        },
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
        [
            "Verona > copy-paste-topic #4",
            [
                "is posing for copy tests",
                "regular after me for copy tests",
                "regular last after two mes",
                "is posing again for copy tests",
            ],
        ],
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
    await test_copying_selection_with_no_message_content(page);
    await test_copying_me_timestamp_through_next_sender(page);
    await test_copying_me_timestamp_through_next_body(page);
    await test_copying_me_timestamp_through_partial_next_body(page);
    await test_copying_me_timestamp_through_later_sender(page);
    await test_copying_me_timestamp_through_later_body(page);
    await test_copying_disjoint_ranges_with_no_message_content(page);
    await test_copying_disjoint_ranges_with_later_body(page);
    await test_copying_from_reminder_through_next_body(page);
    await test_copying_through_trailing_sender_name(page);
    await test_multiple_message_selection_with_partially_selected_bookend_messages(page);
}

await common.run_test(copy_paste_test);
