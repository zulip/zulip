"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const fenced_code = zrequire("fenced_code");

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

run_test("wrap_code", () => {
    // Without language: no data-code-language attribute.
    const basic = fenced_code.wrap_code("hello\n");
    assert.ok(basic.startsWith('<div class="codehilite"><pre>'));
    assert.ok(!basic.includes("data-code-language"));
    assert.ok(basic.includes("hello\n</code></pre></div>"));

    // With empty string language: treated the same as no language.
    const empty_lang = fenced_code.wrap_code("hello\n", "");
    assert.ok(!empty_lang.includes("data-code-language"));

    // HTML escaping in code content.
    const escaped = fenced_code.wrap_code('<script>alert("xss")</script>');
    assert.ok(escaped.includes("&lt;script&gt;"));
    assert.ok(!escaped.includes("<script>"));

    // Trailing newlines are trimmed to just one.
    const trimmed = fenced_code.wrap_code("code\n\n\n");
    assert.ok(trimmed.includes("code\n</code>"));

    // Leading newlines are trimmed.
    const leading = fenced_code.wrap_code("\n\ncode");
    assert.ok(leading.includes(">code\n</code>"));
});

run_test("wrap_code_with_language", () => {
    // With an unknown language, the lang string itself is used.
    const unknown = fenced_code.wrap_code("x = 1", "mylang");
    assert.ok(unknown.includes('data-code-language="mylang"'));

    // After initialize(), known languages use pretty_name.
    fenced_code.initialize({
        langs: {
            python: {priority: 1, pretty_name: "Python"},
            js: {priority: 2, pretty_name: "JavaScript"},
        },
    });

    const python = fenced_code.wrap_code("x = 1", "python");
    assert.ok(python.includes('data-code-language="Python"'));

    const js = fenced_code.wrap_code("var x;", "js");
    assert.ok(js.includes('data-code-language="JavaScript"'));

    // Unknown language still works after initialize.
    const rust = fenced_code.wrap_code("fn main() {}", "rust");
    assert.ok(rust.includes('data-code-language="rust"'));

    // Language with HTML special chars is escaped.
    const special = fenced_code.wrap_code("code", 'a<b>"c');
    assert.ok(special.includes("data-code-language="));
    assert.ok(!special.includes('a<b>"c'));
});

run_test("process_fenced_code_quote", () => {
    const input = "```quote\nhello world\nline two\n```";
    const output = fenced_code.process_fenced_code(input);
    assert.ok(output.includes("> hello world"));
    assert.ok(output.includes("> line two"));
});

run_test("process_fenced_code_math", () => {
    // Valid LaTeX renders via KaTeX.
    const input = "```math\nx^2\n```";
    const output = fenced_code.process_fenced_code(input);
    assert.ok(output.includes("katex"));

    // Invalid LaTeX produces a tex-error span.
    const bad_input = "```math\n\\invalid{}{}{}\n```";
    const bad_output = fenced_code.process_fenced_code(bad_input);
    assert.ok(bad_output.includes("tex-error"));
});

run_test("process_fenced_code_spoiler", () => {
    const stashed = [];
    fenced_code.set_stash_func((text) => {
        stashed.push(text);
        return "STASHED";
    });

    const input = "```spoiler Click to reveal\nhidden content\n```";
    const output = fenced_code.process_fenced_code(input);
    assert.ok(output.includes("Click to reveal"));
    assert.ok(output.includes("hidden content"));
    // The stash function should have been called for the spoiler HTML wrappers.
    assert.ok(stashed.some((s) => s.includes("spoiler-block")));

    // Reset stash func for subsequent tests.
    fenced_code.set_stash_func((text) => text);
});

run_test("process_fenced_code_tilde_fence", () => {
    const input = "~~~\ntilde fenced\n~~~";
    const output = fenced_code.process_fenced_code(input);
    assert.ok(output.includes("codehilite"));
    assert.ok(output.includes("tilde fenced"));
});

run_test("process_fenced_code_language_specifier", () => {
    const input = "```python\nprint('hello')\n```";
    const output = fenced_code.process_fenced_code(input);
    assert.ok(output.includes('data-code-language="Python"'));
    assert.ok(output.includes("print(&#39;hello&#39;)"));
});

run_test("process_fenced_code_unclosed", () => {
    // An unclosed code block should auto-close at EOF.
    const input = "before\n```\nunclosed code";
    const output = fenced_code.process_fenced_code(input);
    assert.ok(output.includes("before"));
    assert.ok(output.includes("codehilite"));
    assert.ok(output.includes("unclosed code"));
});
