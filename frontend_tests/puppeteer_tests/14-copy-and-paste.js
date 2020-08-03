"use strict";

const {strict: assert} = require("assert");

const common = require("../puppeteer_lib/common");

async function copy_messages(page, start_message, end_message) {
    return await page.evaluate(
        (start_message, end_message) => {
            function get_message_node(message) {
                return $('.message_row .message_content:contains("' + message + '")').get(0);
            }

            // select messages from start_message to end_message
            const selectedRange = document.createRange();
            selectedRange.setStartAfter(get_message_node(start_message));
            selectedRange.setEndBefore(get_message_node(end_message));
            window.getSelection().removeAllRanges();
            window.getSelection().addRange(selectedRange);

            // Remove existing copy/paste divs, which may linger from the previous
            // example.  (The code clears these out with a zero-second timeout, which
            // is probably sufficient for human users, but which causes problems here.)
            $("#copytempdiv").remove();

            // emulate copy event
            $("body").trigger($.Event("keydown", {which: 67, ctrlKey: true}));

            // find temp div with copied text
            const temp_div = $("#copytempdiv");
            return temp_div
                .children("p")
                .get()
                .map((p) => p.textContent);
        },
        start_message,
        end_message,
    );
}

async function test_copying_first_message_from_topic(page) {
    const actual_copied_lines = await copy_messages(page, "copy paste test C", "copy paste test C");
    const expected_copied_lines = [];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_last_message_from_topic(page) {
    const actual_copied_lines = await copy_messages(page, "copy paste test E", "copy paste test E");
    const expected_copied_lines = [];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_first_two_messages_from_topic(page) {
    const actual_copied_lines = await copy_messages(page, "copy paste test C", "copy paste test D");
    const expected_copied_lines = ["Desdemona: copy paste test C", "Desdemona: copy paste test D"];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_all_messages_from_topic(page) {
    const actual_copied_lines = await copy_messages(page, "copy paste test C", "copy paste test E");
    const expected_copied_lines = [
        "Desdemona: copy paste test C",
        "Desdemona: copy paste test D",
        "Desdemona: copy paste test E",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_last_from_prev_first_from_next(page) {
    const actual_copied_lines = await copy_messages(page, "copy paste test B", "copy paste test C");
    const expected_copied_lines = [
        "Verona > copy-paste-topic #1 Today",
        "Desdemona: copy paste test B",
        "Verona > copy-paste-topic #2 Today",
        "Desdemona: copy paste test C",
    ];
    assert.deepStrictEqual(actual_copied_lines, expected_copied_lines);
}

async function test_copying_last_from_prev_all_from_next(page) {
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

async function test_copying_all_from_prev_first_from_next(page) {
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

async function test_copying_messages_from_several_topics(page) {
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

async function copy_paste_test(page) {
    await common.log_in(page);

    await common.send_multiple_messages(page, [
        {stream: "Verona", topic: "copy-paste-topic #1", content: "copy paste test A"},

        {stream: "Verona", topic: "copy-paste-topic #1", content: "copy paste test B"},

        {stream: "Verona", topic: "copy-paste-topic #2", content: "copy paste test C"},

        {stream: "Verona", topic: "copy-paste-topic #2", content: "copy paste test D"},

        {stream: "Verona", topic: "copy-paste-topic #2", content: "copy paste test E"},

        {stream: "Verona", topic: "copy-paste-topic #3", content: "copy paste test F"},

        {stream: "Verona", topic: "copy-paste-topic #3", content: "copy paste test G"},
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
