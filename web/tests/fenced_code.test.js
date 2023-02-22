"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");

const fenced_code = zrequire("../shared/src/fenced_code");

// Check the default behavior of fenced code blocks
// works properly before Markdown is initialized.
run_test("fenced_block_defaults", () => {
    const input = "\n```\nfenced code\n```\n\nand then after\n";
    const expected =
        '\n\n<div class="codehilite"><pre><span></span><code>fenced code\n</code></pre></div>\n\n\nand then after\n\n';
    const output = fenced_code.process_fenced_code(input);
    assert.equal(output, expected);
});

run_test("get_unused_fence", () => {
    assert.equal(fenced_code.get_unused_fence("```js\nsomething\n```"), "`".repeat(4));
    assert.equal(fenced_code.get_unused_fence("````\nsomething\n````"), "`".repeat(5));
    assert.equal(fenced_code.get_unused_fence("```\n````\n``````"), "`".repeat(7));
    assert.equal(fenced_code.get_unused_fence("~~~\nsomething\n~~~"), "`".repeat(3));
    assert.equal(
        fenced_code.get_unused_fence("```code\nterminating fence is indented and longer\n   ````"),
        "`".repeat(5),
    );
    assert.equal(
        fenced_code.get_unused_fence("```code\nterminating fence is extra indented\n    ````"),
        "`".repeat(4),
    );
    let large_testcase = "";
    // ```
    // ````
    // `````
    // ... up to N chars
    // We insert a N + 1 character fence.
    for (let i = 3; i <= 20; i += 1) {
        large_testcase += "`".repeat(i) + "\n";
    }
    assert.equal(fenced_code.get_unused_fence(large_testcase), "`".repeat(21));
});
