"use strict";

const {strict: assert} = require("assert");

const {mock_esm, zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const compose_split_messages = zrequire("../src/compose_split_messages");

compose_split_messages.set_split_messages_enabled(true);
run_test("trim_except_whitespace_before_text", () => {
    assert.equal(compose_split_messages.trim_except_whitespace_before_text("\n\n\nhello"), "hello");
    assert.equal(
        compose_split_messages.trim_except_whitespace_before_text("\n\n\n    \n\nhello"),
        "hello",
    );
    assert.equal(
        compose_split_messages.trim_except_whitespace_before_text("    \n\n\n    hello"),
        "    hello",
    );
    assert.equal(
        compose_split_messages.trim_except_whitespace_before_text("\n \n \n hello"),
        " hello",
    );
});

mock_esm("../src/compose_textarea", {
    position_inside_code_block(content, position) {
        const first = content.slice(0, position);
        const second = content.slice(position);
        // a simplified version of what compose_ui.position_inside_code_block does
        return first.includes("```") && second.includes("```");
    },
});

const test_messages = [
    `\n\n\n\n\n\nzulip\n\n\n`,
    `\n\n       \n\n \n\n \n\n   zulip\n\n\n    chat`,
    `\`\`\`\n\n\n\`\`\``,
    `\`\`\`python\n\n\n\n\n\nprint("hi")\n\n\n\`\`\`\n\n\n\n`,
    `\`\`\`python\n\n\n\n\n\nprint("hi")\n\n\n\`\`\`\n\n\n   ZULIP\n\n\n`,
];

run_test("delimiter_index_outside_code_block", () => {
    const first_delimiter_indices = [0, 25, -1, 32, 32];
    let i = 0;
    for (const message of test_messages) {
        assert.equal(
            compose_split_messages.delimiter_index_outside_code_block(message),
            first_delimiter_indices[i],
        );
        i += 1;
    }
});

run_test("split_message", () => {
    const split_messages = [
        ["zulip", ""],
        ["   zulip", "\n\n\n    chat"],
        [`\`\`\`\n\n\n\`\`\``, ""],
        [`\`\`\`python\n\n\n\n\n\nprint("hi")\n\n\n\`\`\``, ""],
        [`\`\`\`python\n\n\n\n\n\nprint("hi")\n\n\n\`\`\``, "\n\n\n   ZULIP"],
    ];
    let i = 0;
    for (const message of test_messages) {
        const actual = compose_split_messages.split_message(message);
        const expected = split_messages[i];
        assert.equal(actual[0], expected[0]);
        assert.equal(actual[1], expected[1]);
        i += 1;
    }
});

let dummy_message = `First line\n\n\nSecond line\n\n\n\n\n\n    third line\n\n\n\`\`\`python\n\n\n\n\n\nprint("code")\n\n\n\n\n\n\`\`\`\n\n\nafter code`;

mock_esm("../src/compose_state", {
    message_content() {
        return dummy_message;
    },
});

run_test("count_message_content_split_parts", () => {
    assert.equal(compose_split_messages.count_message_content_split_parts(), 5);
});

run_test("will_split_into_multiple_messages", () => {
    assert.equal(compose_split_messages.will_split_into_multiple_messages(), true);
    dummy_message = "\n\n\nThis will not split\n\n\n\n\n";
    assert.equal(compose_split_messages.will_split_into_multiple_messages(), false);
    compose_split_messages.set_split_messages_enabled(false);
    assert.equal(compose_split_messages.will_split_into_multiple_messages(), false);
});
