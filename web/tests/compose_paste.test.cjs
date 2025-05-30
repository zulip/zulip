"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const katex_tests = require("../../zerver/tests/fixtures/katex_test_cases.json");
const {parse} = require("../src/markdown.ts");

const {zrequire, set_global} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {window} = new JSDOM();

const compose_paste = zrequire("compose_paste");
const stream_data = zrequire("stream_data");

set_global("document", {});
stream_data.add_sub({
    stream_id: 4,
    name: "Rome",
});
stream_data.add_sub({
    stream_id: 5,
    name: "Romeo`s lair",
});

run_test("try_stream_topic_syntax_text", () => {
    const test_cases = [
        [
            "http://zulip.zulipdev.com/#narrow/channel/4-Rome/topic/old.20FAILED.20EXPORT",
            "#**Rome>old FAILED EXPORT**",
        ],
        [
            "http://zulip.zulipdev.com/#narrow/channel/4-Rome/topic/100.25.20profits",
            "#**Rome>100% profits**",
        ],
        [
            "http://zulip.zulipdev.com/#narrow/channel/4-Rome/topic/old.20API.20wasn't.20compiling.20erratically",
            "#**Rome>old API wasn't compiling erratically**",
        ],

        ["http://different.origin.com/#narrow/channel/4-Rome/topic/old.20FAILED.20EXPORT"],
        [
            "http://zulip.zulipdev.com/#narrow/channel/4-Rome/topic/old.20FAILED.20EXPORT/near/100",
            "#**Rome>old FAILED EXPORT@100**",
        ],
        ["http://zulip.zulipdev.com/#narrow/channel/4-Rome/topic//near/100", "#**Rome>@100**"],
        [
            "http://zulip.zulipdev.com/#narrow/channel/4-Rome/topic/old.20FAILED.20EXPORT/with/100",
            "#**Rome>old FAILED EXPORT**",
        ],
        // malformed urls
        ["http://zulip.zulipdev.com/narrow/channel/4-Rome/topic/old.20FAILED.20EXPORT"],
        ["http://zulip.zulipdev.com/#not_narrow/channel/4-Rome/topic/old.20FAILED.20EXPORT"],
        ["http://zulip.zulipdev.com/#narrow/not_stream/4-Rome/topic/old.20FAILED.20EXPORT"],
        ["http://zulip.zulipdev.com/#narrow/channel/4-Rome/not_topic/old.20FAILED.20EXPORT"],
        ["http://zulip.zulipdev.com/#narrow/channel/4-Rome/", "#**Rome**"],
        ["http://zulip.zulipdev.com/#narrow/channel/4-Rome/topic"],
        ["http://zulip.zulipdev.com/#narrow/topic/cheese"],
        ["http://zulip.zulipdev.com/#narrow/topic/pizza/stream/Rome"],
        ["http://zulip.zulipdev.com/#narrow/channel/4-Rome/topic/old.20FAILED.20EXPORT/near/"],

        // When a url containing characters which are known to produce broken
        // #**stream>topic** urls is pasted, a normal markdown link syntax is produced.
        [
            "http://zulip.zulipdev.com/#narrow/stream/4-Rome/topic/100.25.20profits.60",
            "[#Rome > 100% profits&#96;](#narrow/channel/4-Rome/topic/100.25.20profits.60)",
        ],
        [
            "http://zulip.zulipdev.com/#narrow/stream/4-Rome/topic/100.25.20*profits",
            "[#Rome > 100% &#42;profits](#narrow/channel/4-Rome/topic/100.25.20*profits)",
        ],
        [
            "http://zulip.zulipdev.com/#narrow/stream/4-Rome/topic/.24.24 100.25.20profits",
            "[#Rome > &#36;&#36; 100% profits](#narrow/channel/4-Rome/topic/.24.24.20100.25.20profits)",
        ],
        [
            "http://zulip.zulipdev.com/#narrow/stream/4-Rome/topic/>100.25.20profits",
            "[#Rome > &gt;100% profits](#narrow/channel/4-Rome/topic/.3E100.25.20profits)",
        ],
        [
            "http://zulip.zulipdev.com/#narrow/stream/5-Romeo.60s-lair/topic/normal",
            "[#Romeo&#96;s lair > normal](#narrow/channel/5-Romeo.60s-lair/topic/normal)",
        ],
        [
            "http://zulip.zulipdev.com/#narrow/stream/4-Rome/topic/100.25.20profits.60/near/20",
            "[#Rome > 100% profits&#96; @ 💬](#narrow/channel/4-Rome/topic/100.25.20profits.60/near/20)",
        ],
    ];

    for (const test_case of test_cases) {
        const result = compose_paste.try_stream_topic_syntax_text(test_case[0]);
        const expected = test_case[1] ?? null;
        assert.equal(result, expected, "Failed for url: " + test_case[0]);
    }
});

run_test("maybe_transform_html", () => {
    // Copied HTML from VS Code
    let paste_html = `<div style="color: #cccccc;background-color: #1f1f1f;font-family: 'Droid Sans Mono', 'monospace', monospace;font-weight: normal;font-size: 14px;line-height: 19px;white-space: pre;"><div><span style="color: #c586c0;">if</span><span style="color: #cccccc;"> (</span><span style="color: #9cdcfe;">$preview_src</span><span style="color: #cccccc;">.</span><span style="color: #dcdcaa;">endsWith</span><span style="color: #cccccc;">(</span><span style="color: #ce9178;">"&amp;size=full"</span><span style="color: #cccccc;">))</span></div></div>`;
    let paste_text = `if ($preview_src.endsWith("&size=full"))`;
    const escaped_paste_text = "if ($preview_src.endsWith(&quot;&amp;size=full&quot;))";
    const expected_output = "<pre><code>" + escaped_paste_text + "</code></pre>";
    assert.equal(compose_paste.maybe_transform_html(paste_html, paste_text), expected_output);

    // Untransformed HTML
    paste_html = "<div><div>Hello</div><div>World!</div></div>";
    paste_text = "Hello\nWorld!";
    assert.equal(compose_paste.maybe_transform_html(paste_html, paste_text), paste_html);
});

run_test("paste_handler_converter", () => {
    /*
        Pasting from another Zulip message
    */
    global.document = window.document;
    global.window = window;
    global.Node = window.Node;
    global.HTMLElement = window.HTMLElement;
    global.HTMLAnchorElement = window.HTMLAnchorElement;
    // Bold text
    let input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: hsl(0, 0%, 13%); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;"><span> </span>love the<span> </span><b>Zulip</b><b> </b></span><b style="color: hsl(0, 0%, 13%); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;">Organization</b><span style="color: hsl(0, 0%, 13%); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;">.</span>';
    assert.equal(
        compose_paste.paste_handler_converter(input),
        " love the **Zulip** **Organization**.",
    );

    // Inline code
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: hsl(210, 12%, 16%); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;">The<span> </span></span><code style="box-sizing: border-box; font-family: SFMono-Regular, Consolas, &quot;Liberation Mono&quot;, Menlo, Courier, monospace; font-size: 13.6px; padding: 0.2em 0.4em; margin: 0px; background-color: hsla(210, 13%, 12%, 0.05); border-radius: 3px; color: hsl(210, 12%, 16%); font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial;">JSDOM</code><span style="color: hsl(210, 12%, 16%); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;"><span> </span>constructor</span>';
    assert.equal(compose_paste.paste_handler_converter(input), "The `JSDOM` constructor");

    // A python code block
    input = `<meta http-equiv="content-type" content="text/html; charset=utf-8"><p>zulip code block in python</p><div class="codehilite zulip-code-block" data-code-language="Python"><pre><span></span><code><span class="nb">print</span><span class="p">(</span><span class="s2">"hello"</span><span class="p">)</span>\n<span class="nb">print</span><span class="p">(</span><span class="s2">"world"</span><span class="p">)</span></code></pre></div></meta>`;
    assert.equal(
        compose_paste.paste_handler_converter(input),
        'zulip code block in python\n\n```Python\nprint("hello")\nprint("world")\n```',
    );

    // Single line in a code block
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><pre><code>single line</code></pre>';
    assert.equal(compose_paste.paste_handler_converter(input), "`single line`");

    // No code formatting if the given text area has a backtick at the cursor position
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><pre><code>single line</code></pre>';
    assert.equal(
        compose_paste.paste_handler_converter(input, {
            caret: () => 6,
            val: () => "e.g. `",
        }),
        "single line",
    );

    // Yes code formatting if the given text area has a backtick but not at the cursor position
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><pre><code>single line</code></pre>';
    assert.equal(
        compose_paste.paste_handler_converter(input, {
            caret: () => 0,
        }),
        "`single line`",
    );

    // Raw links without custom text
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><a href="https://zulip.readthedocs.io/en/latest/subsystems/logging.html" target="_blank" title="https://zulip.readthedocs.io/en/latest/subsystems/logging.html" style="color: hsl(200, 100%, 40%); text-decoration: none; cursor: pointer; font-family: &quot;Source Sans 3&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%);">https://zulip.readthedocs.io/en/latest/subsystems/logging.html</a>';
    assert.equal(
        compose_paste.paste_handler_converter(input),
        "https://zulip.readthedocs.io/en/latest/subsystems/logging.html",
    );

    // Links with custom text
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><a class="reference external" href="https://zulip.readthedocs.io/en/latest/contributing/contributing.html" style="box-sizing: border-box; color: hsl(283, 39%, 53%); text-decoration: none; cursor: pointer; outline: 0px; font-family: Lato, proxima-nova, &quot;Helvetica Neue&quot;, Arial, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 99%);">Contributing guide</a>';
    assert.equal(
        compose_paste.paste_handler_converter(input),
        "[Contributing guide](https://zulip.readthedocs.io/en/latest/contributing/contributing.html)",
    );

    // Only numbered list (list style retained)
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><ol><li>text</li></ol>';
    assert.equal(compose_paste.paste_handler_converter(input), "1. text");

    // Heading
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><h1 style="box-sizing: border-box; font-size: 2em; margin-top: 0px !important; margin-right: 0px; margin-bottom: 16px; margin-left: 0px; font-weight: 600; line-height: 1.25; padding-bottom: 0.3em; border-bottom: 1px solid hsl(216, 14%, 93%); color: hsl(210, 12%, 16%); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial;">Zulip overview</h1><p>normal text</p>';
    assert.equal(compose_paste.paste_handler_converter(input), "# Zulip overview\n\nnormal text");
    // Only heading (strip heading style)
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><h1 style="box-sizing: border-box; font-size: 2em; margin-top: 0px !important; margin-right: 0px; margin-bottom: 16px; margin-left: 0px; font-weight: 600; line-height: 1.25; padding-bottom: 0.3em; border-bottom: 1px solid hsl(216, 14%, 93%); color: hsl(210, 12%, 16%); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial;">Zulip overview</h1>';
    assert.equal(compose_paste.paste_handler_converter(input), "Zulip overview");

    // Italic text
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8">normal text <i style="box-sizing: inherit; color: hsl(0, 0%, 0%); font-family: Verdana, sans-serif; font-size: 15px; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;">This text is italic</i>';
    assert.equal(compose_paste.paste_handler_converter(input), "normal text *This text is italic*");

    // Strikethrough text
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8">normal text <del style="box-sizing: inherit; color: hsl(0, 0%, 0%); font-family: Verdana, sans-serif; font-size: 15px; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;">This text is struck through</del>';
    assert.equal(
        compose_paste.paste_handler_converter(input),
        "normal text ~~This text is struck through~~",
    );

    // Emojis
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;">emojis:<span> </span></span><span aria-label="smile" class="emoji emoji-1f604" role="img" title="smile" style="height: 20px; width: 20px; position: relative; margin-top: -7px; vertical-align: middle; top: 3px; background-position: 55% 46.667%; display: inline-block; background-image: url(&quot;http://localhost:9991/webpack/files/generated/emoji/google.webp&quot;); background-size: 6100%; background-repeat: no-repeat; text-indent: 100%; white-space: nowrap; overflow: hidden; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">:smile:</span><span style="color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;"><span> </span></span><span aria-label="family man woman girl" class="emoji emoji-1f468-200d-1f469-200d-1f467" role="img" title="family man woman girl" style="height: 20px; width: 20px; position: relative; margin-top: -7px; vertical-align: middle; top: 3px; background-position: 23.333% 75%; display: inline-block; background-image: url(&quot;http://localhost:9991/webpack/files/generated/emoji/google.webp&quot;); background-size: 6100%; background-repeat: no-repeat; text-indent: 100%; white-space: nowrap; overflow: hidden; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">:family_man_woman_girl:</span>';
    assert.equal(
        compose_paste.paste_handler_converter(input),
        "emojis: :smile: :family_man_woman_girl:",
    );

    // Nested lists
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><ul style="padding: 0px; margin: 0px 0px 5px 20px; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"><li style="line-height: inherit;">bulleted</li><li style="line-height: inherit;">nested<ul style="padding: 0px; margin: 2px 0px 5px 20px;"><li style="line-height: inherit;">nested level 1</li><li style="line-height: inherit;">nested level 1 continue<ul style="padding: 0px; margin: 2px 0px 5px 20px;"><li style="line-height: inherit;">nested level 2</li><li style="line-height: inherit;">nested level 2 continue</li></ul></li></ul></li></ul>';
    assert.equal(
        compose_paste.paste_handler_converter(input),
        "* bulleted\n* nested\n  * nested level 1\n  * nested level 1 continue\n    * nested level 2\n    * nested level 2 continue",
    );

    // Heading from https://arxiv.org/abs/1301.3191
    input =
        '<html><body><!--StartFragment--><h1 class="title mathjax" style="font-size: 1.8em !important; font-weight: 700; line-height: 27.9936px; display: block; margin-block: 12px; margin: 0.25em 0px 12px 20px; margin-inline: 20px 0px; color: rgb(0, 0, 0); font-family: &quot;Lucida Grande&quot;, Helvetica, Arial, sans-serif; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: normal; background-color: rgb(255, 255, 255); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">Enriched categories as a free cocompletion</h1><br class="Apple-interchange-newline"><!--EndFragment--></body></html>';
    assert.equal(
        compose_paste.paste_handler_converter(input),
        "Enriched categories as a free cocompletion",
    );

    // Heading from https://www.sciencedirect.com/science/article/pii/S0001870815004715
    input =
        '<html><body><!--StartFragment--><h2 class="section-title u-h4 u-margin-l-top u-margin-xs-bottom" style="box-sizing: border-box; margin-top: 32px !important; margin-right: 0px; margin-bottom: 8px !important; margin-left: 0px; padding: 0px; font-weight: normal !important; font-size: 20px !important; line-height: var(--sd-ui-line-height) !important; color: rgb(31, 31, 31); font-family: ElsevierGulliver, Georgia, "Times New Roman", Times, STIXGeneral, "Cambria Math", "Lucida Sans Unicode", "Microsoft Sans Serif", "Segoe UI Symbol", "Arial Unicode MS", serif, sans-serif; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: normal; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">Abstract</h2><div id="as0010" style="box-sizing: border-box; margin: 0px; padding: 0px; color: rgb(31, 31, 31); font-family: ElsevierGulliver, Georgia, "Times New Roman", Times, STIXGeneral, "Cambria Math", "Lucida Sans Unicode", "Microsoft Sans Serif", "Segoe UI Symbol", "Arial Unicode MS", serif, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: normal; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"><br class="Apple-interchange-newline"><!--EndFragment--></body></html>';
    assert.equal(compose_paste.paste_handler_converter(input), "Abstract");

    // Heading from https://en.wikipedia.org/wiki/James_Madison
    input =
        '<html><body><!--StartFragment--><h1 id="firstHeading" class="firstHeading mw-first-heading" style="color: var(--color-emphasized,#101418); font-weight: normal; margin: 0px; padding: 0px; display: flow-root; word-break: break-word; border: 0px; font-size: 1.8em; font-family: &quot;Linux Libertine&quot;, Georgia, Times, &quot;Source Serif Pro&quot;, serif; line-height: 1.375; overflow-wrap: break-word; flex-grow: 1; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: normal; background-color: rgb(255, 255, 255); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"><span class="mw-page-title-main">James Madison</span></h1><div id="p-lang-btn" class="vector-dropdown mw-portlet mw-portlet-lang" style="position: relative; float: right; box-sizing: border-box; flex-shrink: 0; margin-right: -12px; color: rgb(32, 33, 34); font-family: sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: normal; background-color: rgb(255, 255, 255); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"></div><br class="Apple-interchange-newline"><!--EndFragment--></body></html>';
    assert.equal(compose_paste.paste_handler_converter(input), "James Madison");

    // Heading from https://customer-identity-access-management.hashnode.dev/from-words-to-vectors-understanding-the-magic-of-text-embedding
    input = `<html><body><!--StartFragment--><div class="mt-6 break-words px-4 text-center font-heading text-3xl font-bold text-slate-900 dark:text-white md:mt-10 md:px-5 md:text-4xl lg:px-8 xl:px-20 xl:text-5xl mb-8 md:mb-14" style="box-sizing: border-box; ...">
    <h1 class="leading-tight" data-query="post-title">From Words to Vectors: Understanding the Magic of Text Embedding</h1>
    </div></body></html>`;
    assert.equal(
        compose_paste.paste_handler_converter(input),
        "From Words to Vectors: Understanding the Magic of Text Embedding",
    );

    // Check we don't double-convert HTML to text.
    input = `<del>turtles are cool</del>`;
    assert.equal(compose_paste.paste_handler_converter(input), "turtles are cool");

    input = `<span style="color: rgb(31, 35, 40); font-family: ui-monospace, SFMono-Regular, &quot;SF Mono&quot;, Menlo, Consolas, &quot;Liberation Mono&quot;, monospace; font-size: 11.9px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; white-space: break-spaces; background-color: rgba(129, 139, 152, 0.12); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;">&lt;del&gt;turtles are cool&lt;/del&gt;</span>`;
    assert.equal(compose_paste.paste_handler_converter(input), "<del>turtles are cool</del>");

    // 2 paragraphs with line break/s in between
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><p>paragraph 1</p><br><p>paragraph 2</p>';
    assert.equal(compose_paste.paste_handler_converter(input), "paragraph 1\n\nparagraph 2");

    // Pasting from external sources
    // Pasting list from GitHub
    input =
        '<div class="preview-content"><div class="comment"><div class="comment-body markdown-body js-preview-body" style="min-height: 131px;"><p>Test list:</p><ul><li>Item 1</li><li>Item 2</li></ul></div></div></div>';
    assert.equal(compose_paste.paste_handler_converter(input), "Test list:\n* Item 1\n* Item 2");

    // Pasting list from VS Code
    input =
        '<div class="ace-line gutter-author-d-iz88z86z86za0dz67zz78zz78zz74zz68zjz80zz71z9iz90za3z66zs0z65zz65zq8z75zlaz81zcz66zj6g2mz78zz76zmz66z22z75zfcz69zz66z ace-ltr focused-line" dir="auto" id="editor-3-ace-line-41"><span>Test list:</span></div><div class="ace-line gutter-author-d-iz88z86z86za0dz67zz78zz78zz74zz68zjz80zz71z9iz90za3z66zs0z65zz65zq8z75zlaz81zcz66zj6g2mz78zz76zmz66z22z75zfcz69zz66z line-list-type-bullet ace-ltr" dir="auto" id="editor-3-ace-line-42"><ul class="listtype-bullet listindent1 list-bullet1"><li><span class="ace-line-pocket-zws" data-faketext="" data-contentcollector-ignore-space-at="end"></span><span class="ace-line-pocket" data-faketext="" contenteditable="false"></span><span class="ace-line-pocket-zws" data-faketext="" data-contentcollector-ignore-space-at="start"></span><span>Item 1</span></li></ul></div><div class="ace-line gutter-author-d-iz88z86z86za0dz67zz78zz78zz74zz68zjz80zz71z9iz90za3z66zs0z65zz65zq8z75zlaz81zcz66zj6g2mz78zz76zmz66z22z75zfcz69zz66z line-list-type-bullet ace-ltr" dir="auto" id="editor-3-ace-line-43"><ul class="listtype-bullet listindent1 list-bullet1"><li><span class="ace-line-pocket-zws" data-faketext="" data-contentcollector-ignore-space-at="end"></span><span class="ace-line-pocket" data-faketext="" contenteditable="false"></span><span class="ace-line-pocket-zws" data-faketext="" data-contentcollector-ignore-space-at="start"></span><span>Item 2</span></li></ul></div>';
    assert.equal(compose_paste.paste_handler_converter(input), "Test list:\n* Item 1\n* Item 2");

    // Pasting from Google Sheets (remove <style> elements completely)
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><style type="text/css"><!--td {border: 1px solid #cccccc;}br {mso-data-placement:same-cell;}--></style><span style="font-size:10pt;font-family:Arial;font-style:normal;text-align:right;" data-sheets-value="{&quot;1&quot;:3,&quot;3&quot;:123}" data-sheets-userformat="{&quot;2&quot;:769,&quot;3&quot;:{&quot;1&quot;:0},&quot;11&quot;:3,&quot;12&quot;:0}">123</span>';
    assert.equal(compose_paste.paste_handler_converter(input), "123");

    // Pasting from Excel
    input = `<html xmlns:v="urn:schemas-microsoft-com:vml"\nxmlns:o="urn:schemas-microsoft-com:office:office"\nxmlns:x="urn:schemas-microsoft-com:office:excel"\nxmlns="http://www.w3.org/TR/REC-html40">\n<head>\n<meta http-equiv=Content-Type content="text/html; charset=utf-8">\n<meta name=ProgId content=Excel.Sheet>\n<meta name=Generator content="Microsoft Excel 15">\n<link id=Main-File rel=Main-File\nhref="file:///C:/Users/ADMINI~1/AppData/Local/Temp/msohtmlclip1/01/clip.htm">\n<link rel=File-List\nhref="file:///C:/Users/ADMINI~1/AppData/Local/Temp/msohtmlclip1/01/clip_filelist.xml">\n<style>\n<!--table\n    {mso-displayed-decimal-separator:"\\.";\n    mso-displayed-thousand-separator:"\\,";}\n@page\n    {margin:.75in .7in .75in .7in;\n    mso-header-margin:.3in;\n    mso-footer-margin:.3in;}\ntr\n    {mso-height-source:auto;}\ncol\n    {mso-width-source:auto;}\nbr\n    {mso-data-placement:same-cell;}\ntd\n    {padding-top:1px;\n    padding-right:1px;\n    padding-left:1px;\n    mso-ignore:padding;\n    color:black;\n    font-size:11.0pt;\n    font-weight:400;\n    font-style:normal;\n    text-decoration:none;\n    font-family:Calibri, sans-serif;\n    mso-font-charset:0;\n    mso-number-format:General;\n    text-align:general;\n    vertical-align:bottom;\n    border:none;\n    mso-background-source:auto;\n    mso-pattern:auto;\n    mso-protection:locked visible;\n    white-space:nowrap;\n    mso-rotate:0;}\n.xl65\n    {mso-number-format:"_\\(\\0022$\\0022* \\#\\,\\#\\#0\\.00_\\)\\;_\\(\\0022$\\0022* \\\\\\(\\#\\,\\#\\#0\\.00\\\\\\)\\;_\\(\\0022$\\0022* \\0022-\\0022??_\\)\\;_\\(\\@_\\)";}\n-->\n</style>\n</head>\n<body link="#0563C1" vlink="#954F72">\n<table border=0 cellpadding=0 cellspacing=0 width=88 style='border-collapse:\n collapse;width:66pt'>\n<!--StartFragment-->\n <col width=88 style='mso-width-source:userset;mso-width-alt:3218;width:66pt'>\n <tr height=20 style='height:15.0pt'>\n  <td height=20 class=xl65 width=88 style='height:15.0pt;width:66pt;font-size:\n  11.0pt;color:black;font-weight:400;text-decoration:none;text-underline-style:\n  none;text-line-through:none;font-family:Calibri, sans-serif;border-top:.5pt solid #5B9BD5;\n  border-right:none;border-bottom:none;border-left:none'><span\n  style='mso-spacerun:yes'> </span>$<span style='mso-spacerun:yes'>\n  </span>20.00 </td>\n </tr>\n <tr height=20 style='height:15.0pt'>\n  <td height=20 class=xl65 style='height:15.0pt;font-size:11.0pt;color:black;\n  font-weight:400;text-decoration:none;text-underline-style:none;text-line-through:\n  none;font-family:Calibri, sans-serif;border-top:.5pt solid #5B9BD5;\n  border-right:none;border-bottom:none;border-left:none'><span\n  style='mso-spacerun:yes'> </span>$<span\n  style='mso-spacerun:yes'>               </span>7.00 </td>\n </tr>\n<!--EndFragment-->\n</table>\n</body>\n</html>`;

    // Pasting from Excel using ^V should paste an image.
    assert.ok(compose_paste.is_single_image(input));

    // Pasting from Excel using ^⇧V should paste formatted text.
    assert.equal(compose_paste.paste_handler_converter(input), "     \n\n$ 20.00\n\n$ 7.00");

    // Pasting from LibreOffice Calc should paste an image.
    input = `<html><head><meta http-equiv="content-type" content="text/html; charset=utf-8"><title></title><meta name="generator" content="LibreOffice 25.2.3.2 (Windows)"><style type="text/css"> body,div,table,thead,tbody,tfoot,tr,th,td,p { font-family:"Arial"; font-size:x-small } a.comment-indicator:hover + comment { background:#ffd; position:absolute; display:block; border:1px solid black; padding:0.5em; } a.comment-indicator { background:red; display:inline-block; border:1px solid black; width:0.5em; height:0.5em; } comment { display:none; } </style></head><body><table cellspacing="0" border="0"><colgroup span="4" width="107"></colgroup><tbody><tr><td height="24" align="left" data-sheets-value="{ &quot;1&quot;: 2, &quot;2&quot;: &quot;Kathleen&quot;}">Kathleen</td><td align="left" data-sheets-value="{ &quot;1&quot;: 2, &quot;2&quot;: &quot;Hanner&quot;}">Hanner</td><td align="left" data-sheets-value="{ &quot;1&quot;: 2, &quot;2&quot;: &quot;Female&quot;}">Female</td><td align="left" data-sheets-value="{ &quot;1&quot;: 2, &quot;2&quot;: &quot;United States&quot;}">United States</td></tr><tr><td height="24" align="left" data-sheets-value="{ &quot;1&quot;: 2, &quot;2&quot;: &quot;Nereida&quot;}">Nereida</td><td align="left" data-sheets-value="{ &quot;1&quot;: 2, &quot;2&quot;: &quot;Magwood&quot;}">Magwood</td><td align="left" data-sheets-value="{ &quot;1&quot;: 2, &quot;2&quot;: &quot;Female&quot;}">Female</td><td align="left" data-sheets-value="{ &quot;1&quot;: 2, &quot;2&quot;: &quot;United States&quot;}">United States</td></tr></tbody></table></body></html>`;
    assert.ok(compose_paste.is_single_image(input));

    // This contains three child elements inside the body tag, pasted
    // from LibreOffice Writer, which is correctly classified as not an image.
    input = `<html><head><meta http-equiv="content-type" content="text/html; charset=utf-8"/><title></title><meta name="generator" content="LibreOffice 25.2.3.2 (Windows)"/><style type="text/css">@page { size: 8.5in 11in; margin: 0.79in }td p { orphans: 0; widows: 0; background: transparent }p { line-height: 115%; margin-bottom: 0.1in; background: transparent }</style></head><body lang="en-US" link="#000080" vlink="#800000" dir="ltr"><p style="line-height: 100%; margin-bottom: 0in">ello world</p><table width="100%" cellpadding="0" cellspacing="0"><col width="51*"/><col width="51*"/><col width="51*"/><col width="51*"/><col width="51*"/><tr valign="top"><td width="20%" style="border: none; padding: 0in"><p>X</p></td><td width="20%" style="border: none; padding: 0in"><p>as</p></td><td width="20%" style="border: none; padding: 0in"><p>Jak</p></td><td width="20%" style="border: none; padding: 0in"><p>J</p></td><td width="20%" style="border: none; padding: 0in"><p>Nm</p></td></tr><tr valign="top"><td width="20%" style="border: none; padding: 0in"><p>,mn</p></td><td width="20%" style="border: none; padding: 0in"><p>,nnf</p></td><td width="20%" style="border: none; padding: 0in"><p>Adlk</p></td><td width="20%" style="border: none; padding: 0in"><p>Asn</p></td><td width="20%" style="border: none; padding: 0in"><p>,amns</p></td></tr><tr valign="top"><td width="20%" style="border: none; padding: 0in"><p>Nm</p></td><td width="20%" style="border: none; padding: 0in"><p>Oi</p></td><td width="20%" style="border: none; padding: 0in"><p>Poi</p></td><td width="20%" style="border: none; padding: 0in"><p>B</p></td><td width="20%" style="border: none; padding: 0in"><p>Ijo</p></td></tr><tr valign="top"><td width="20%" style="border: none; padding: 0in"><p>,mn,</p></td><td width="20%" style="border: none; padding: 0in"><p>;ih</p></td><td width="20%" style="border: none; padding: 0in"><p>Oug</p></td><td width="20%" style="border: none; padding: 0in"><p>Iu</p></td><td width="20%" style="border: none; padding: 0in"><p>G</p></td></tr><tr valign="top"><td width="20%" style="border: none; padding: 0in"><p>Ug</p></td><td width="20%" style="border: none; padding: 0in"><p>Bkjb</p></td><td width="20%" style="border: none; padding: 0in"><p>Kjbk</p></td><td width="20%" style="border: none; padding: 0in"><p>;jbj</p></td><td width="20%" style="border: none; padding: 0in"><p>;jb;</p></td></tr><tr valign="top"><td width="20%" style="border: none; padding: 0in"><p>Bkjb</p></td><td width="20%" style="border: none; padding: 0in"><p>Ugug</p></td><td width="20%" style="border: none; padding: 0in"><p>I9</p></td><td width="20%" style="border: none; padding: 0in"><p>68</p></td><td width="20%" style="border: none; padding: 0in"><p>0</p></td></tr><tr valign="top"><td width="20%" style="border: none; padding: 0in"><p>90kjb</p></td><td width="20%" style="border: none; padding: 0in"><p>,bnbiu</p></td><td width="20%" style="border: none; padding: 0in"><p>Ofif</p></td><td width="20%" style="border: none; padding: 0in"><p>P8gp</p></td><td width="20%" style="border: none; padding: 0in"><p>pugp</p></td></tr></table><p style="line-height: 100%; margin-bottom: 0in"><br/></p></body></html>`;
    assert.ok(!compose_paste.is_single_image(input));

    // <body> has a single child element which is not a <table> pasted
    // from LibreOffice Writer should get pasted normally.
    input = `<html><head><meta http-equiv="content-type" content="text/html; charset=utf-8"/><title></title><meta name="generator" content="LibreOffice 25.2.3.2 (Windows)"/><style type="text/css">@page { size: 8.5in 11in; margin: 0.79in }p { line-height: 115%; margin-bottom: 0.1in; background: transparent }</style></head><body lang="en-US" link="#000080" vlink="#800000" dir="ltr"><p style="line-height: 100%; margin-bottom: 0in">Hello world this is some random text.</p></body></html>`;
    assert.ok(!compose_paste.is_single_image(input));

    // A single table pasted from LibreOffice Writer is incorrectly
    // detected as a LibreOffice Calc table.
    // See https://github.com/zulip/zulip/pull/34752/#discussion_r2113598064
    input = `<html><head><meta http-equiv="content-type" content="text/html; charset=utf-8"/><title></title><meta name="generator" content="LibreOffice 25.2.3.2 (Windows)"/><style type="text/css">@page { size: 8.5in 11in; margin: 0.79in }p { line-height: 115%; margin-bottom: 0.1in; background: transparent }</style></head><body lang="en-US" link="#000080" vlink="#800000" dir="ltr"><table width="258" cellpadding="2" cellspacing="0"><col width="83"/><col width="81"/><col width="81"/><tr valign="bottom"><td width="83" height="16" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">Melgar</font></p></td><td width="81" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">Female</font></p></td><td width="81" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">UnitedStates</font></p></td></tr><tr valign="bottom"><td width="83" height="16" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">Weiland</font></p></td><td width="81" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">Female</font></p></td><td width="81" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">UnitedStates</font></p></td></tr><tr valign="bottom"><td width="83" height="16" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">Winward</font></p></td><td width="81" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">Female</font></p></td><td width="81" style="border: none; padding: 0in"><p align="left"><font face="Arial, serif">GreatBritain</font></p></td></tr></table></body></html>`;
    assert.ok(compose_paste.is_single_image(input));

    // Pasting from the mac terminal
    input =
        '<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd"><html><head><meta http-equiv="Content-Type" content="text/html; charset=UTF-8"><meta http-equiv="Content-Style-Type" content="text/css"><title></title><meta name="Generator" content="Cocoa HTML Writer"><meta name="CocoaVersion" content="2575.4"><style type="text/css">p.p1 {margin: 0.0px 0.0px 0.0px 0.0px; font: 11.0px Menlo; color: #000000}span.s1 {font-variant-ligatures: no-common-ligatures}</style></head><body><p class="p1"><span class="s1">insertions</span></p></body></html>';
    assert.equal(compose_paste.paste_handler_converter(input), "insertions");

    // Math block tests

    /*
      This first batch of math block tests uses captured fixtures
        (`input`). This lets us verify behavior like the empty
        `.katex-display` divs in case of newlines in the
        `original_markdown` See
        https://github.com/zulip/zulip/pull/32629#discussion_r1883810127
    */

    for (const math_block_test of katex_tests.math_block_tests) {
        input = math_block_test.input;
        assert.equal(compose_paste.paste_handler_converter(input), math_block_test.expected_output);
    }

    // This next batch of tests round-trips the LaTeX syntax through
    // the Markdown processor and then the paste handler.
    const dummy_helper_config = {
        should_translate_emoticons: () => false,
        get_linkifier_map: () => new Map(),
    };
    assert.equal(dummy_helper_config.should_translate_emoticons(), false);
    assert.deepEqual(dummy_helper_config.get_linkifier_map(), new Map());

    for (const inline_math_expression_test of katex_tests.inline_math_expression_tests) {
        const paste_html = parse({
            raw_content: inline_math_expression_test.original_markup,
            helper_config: dummy_helper_config,
        }).content;
        assert.equal(
            compose_paste.paste_handler_converter(paste_html),
            inline_math_expression_test.expected_output,
        );
    }

    for (const span_conversion_test of katex_tests.text_node_to_span_conversion_tests) {
        const paste_html = parse({
            raw_content: span_conversion_test.original_markup,
            helper_config: dummy_helper_config,
        }).content;
        assert.equal(
            compose_paste.paste_handler_converter(paste_html),
            span_conversion_test.expected_output,
        );
    }
});
