import {strict as assert} from "assert";

import type {Page} from "puppeteer";

import * as common from "./lib/common";

async function copy_messages(
    page: Page,
    start_message: string,
    end_message: string,
): Promise<string[]> {
    return await page.evaluate(
        (start_message: string, end_message: string) => {
            function get_message_node(message: string): Element {
                return [...document.querySelectorAll("#zhome .message_content")].find(
                    (node) => node.textContent?.trim() === message,
                )!;
            }

            // select messages from start_message to end_message
            const selectedRange = document.createRange();
            selectedRange.setStartAfter(get_message_node(start_message));
            selectedRange.setEndBefore(get_message_node(end_message));
            window.getSelection()!.removeAllRanges();
            window.getSelection()!.addRange(selectedRange);

            // Remove existing copy/paste divs, which may linger from the previous
            // example.  (The code clears these out with a zero-second timeout, which
            // is probably sufficient for human users, but which causes problems here.)
            document.querySelector("#copytempdiv")?.remove();

            // emulate copy event
            document.dispatchEvent(
                new KeyboardEvent("keydown", {
                    key: "c",
                    code: "KeyC",
                    ctrlKey: true,
                    keyCode: 67,
                    which: 67,
                } as KeyboardEventInit),
            );

            // find temp div with copied text
            return [...document.querySelectorAll("#copytempdiv > p")].map((p) => p.textContent!);
        },
        start_message,
        end_message,
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
    const expected_copied_lines = ["Desdemona: copy paste test C", "Desdemona: copy paste test D"];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_all_messages_from_topic(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test C", "copy paste test E");
    const expected_copied_lines = [
        "Desdemona: copy paste test C",
        "Desdemona: copy paste test D",
        "Desdemona: copy paste test E",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_last_from_prev_first_from_next(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test B", "copy paste test C");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 Today",
        "Desdemona: copy paste test B",
        "Verona > copy-paste-topic #2 Today",
        "Desdemona: copy paste test C",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_last_from_prev_all_from_next(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test B", "copy paste test E");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 Today",
        "Desdemona: copy paste test B",
        "Verona > copy-paste-topic #2 Today",
        "Desdemona: copy paste test C",
        "Desdemona: copy paste test D",
        "Desdemona: copy paste test E",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_all_from_prev_first_from_next(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test A", "copy paste test C");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 Today",
        "Desdemona: copy paste test A",
        "Desdemona: copy paste test B",
        "Verona > copy-paste-topic #2 Today",
        "Desdemona: copy paste test C",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_messages_from_several_topics(page: Page): Promise<void> {
    const actual_copied_lines = await copy_messages(page, "copy paste test B", "copy paste test F");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 Today",
        "Desdemona: copy paste test B",
        "Verona > copy-paste-topic #2 Today",
        "Desdemona: copy paste test C",
        "Desdemona: copy paste test D",
        "Desdemona: copy paste test E",
        "Verona > copy-paste-topic #3 Today",
        "Desdemona: copy paste test F",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function copy_paste_test(page: Page): Promise<void> {
    await common.log_in(page);
    await page.click(".top_left_all_messages");
    await page.waitForSelector("#zhome .message_row", {visible: true});

    await common.send_multiple_messages(page, [
        {stream_name: "Verona", topic: "copy-paste-topic #1", content: "copy paste test A"},

        {stream_name: "Verona", topic: "copy-paste-topic #1", content: "copy paste test B"},

        {stream_name: "Verona", topic: "copy-paste-topic #2", content: "copy paste test C"},

        {stream_name: "Verona", topic: "copy-paste-topic #2", content: "copy paste test D"},

        {stream_name: "Verona", topic: "copy-paste-topic #2", content: "copy paste test E"},

        {stream_name: "Verona", topic: "copy-paste-topic #3", content: "copy paste test F"},

        {stream_name: "Verona", topic: "copy-paste-topic #3", content: "copy paste test G"},
    ]);

    await common.check_messages_sent(page, "zhome", [
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
}

common.run_test(copy_paste_test);
