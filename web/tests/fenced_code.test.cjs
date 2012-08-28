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
    const header = '<div class="codehilite"><pre><span></span><code>';
    const footer = "</code></pre></div>";

    // Without language: no data-code-language attribute.
    assert.equal(fenced_code.wrap_code("hello\n"), header + "hello\n" + footer);

    // With empty string language: treated the same as no language.
    assert.equal(fenced_code.wrap_code("hello\n", ""), header + "hello\n" + footer);

    // HTML escaping in code content.
    assert.equal(
        fenced_code.wrap_code('<script>alert("xss")</script>'),
        header + "&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;\n" + footer,
    );

    // Trailing newlines are trimmed to just one.
    assert.equal(fenced_code.wrap_code("code\n\n\n"), header + "code\n" + footer);

    // Leading newlines are trimmed.
    assert.equal(fenced_code.wrap_code("\n\ncode"), header + "code\n" + footer);
});

run_test("wrap_code_with_language", () => {
    const footer = "</code></pre></div>";

    function header_with_lang(lang) {
        return `<div class="codehilite" data-code-language="${lang}"><pre><span></span><code>`;
    }

    // Before initialize(), the lang string itself is used.
    assert.equal(
        fenced_code.wrap_code("x = 1", "mylang"),
        header_with_lang("mylang") + "x = 1\n" + footer,
    );

    // After initialize(), known languages use pretty_name.
    fenced_code.initialize({
        langs: {
            python: {priority: 1, pretty_name: "Python"},
            js: {priority: 2, pretty_name: "JavaScript"},
        },
    });

    assert.equal(
        fenced_code.wrap_code("x = 1", "python"),
        header_with_lang("Python") + "x = 1\n" + footer,
    );
    assert.equal(
        fenced_code.wrap_code("var x;", "js"),
        header_with_lang("JavaScript") + "var x;\n" + footer,
    );

    // Unknown language still works after initialize.
    assert.equal(
        fenced_code.wrap_code("fn main() {}", "rust"),
        header_with_lang("rust") + "fn main() {}\n" + footer,
    );

    // Language with HTML special chars is escaped.
    assert.equal(
        fenced_code.wrap_code("code", 'a<b>"c'),
        header_with_lang("a&lt;b&gt;&quot;c") + "code\n" + footer,
    );
});

run_test("process_fenced_code_quote", () => {
    const input = "```quote\nhello world\nline two\n```";
    const output = fenced_code.process_fenced_code(input);
    assert.equal(output, "\n> hello world\n> line two\n\n");
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
    assert.ok(stashed.some((s) => s.includes("spoiler-block")));

    // Restore the default no-op stash func.
    fenced_code.set_stash_func((text) => text);
});

run_test("process_fenced_code_tilde_fence", () => {
    const input = "~~~\ntilde fenced\n~~~";
    const output = fenced_code.process_fenced_code(input);
    assert.equal(
        output,
        '\n<div class="codehilite"><pre><span></span><code>tilde fenced\n</code></pre></div>\n\n',
    );
});

run_test("process_fenced_code_language_specifier", () => {
    fenced_code.initialize({
        langs: {
            python: {priority: 1, pretty_name: "Python"},
        },
    });

    const input = "```python\nprint('hello')\n```";
    const output = fenced_code.process_fenced_code(input);
    assert.ok(output.includes('data-code-language="Python"'));
    assert.ok(output.includes("print(&#39;hello&#39;)"));
});

run_test("process_fenced_code_unclosed", () => {
    // An unclosed code block should auto-close at EOF.
    const input = "before\n```\nunclosed code";
    const output = fenced_code.process_fenced_code(input);
    assert.equal(
        output,
        'before\n\n<div class="codehilite"><pre><span></span><code>unclosed code\n</code></pre></div>\n\n',
    );
});
