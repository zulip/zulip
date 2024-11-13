"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const copy_and_paste = zrequire("copy_and_paste");
const stream_data = zrequire("stream_data");

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
        const result = copy_and_paste.try_stream_topic_syntax_text(test_case[0]);
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
    assert.equal(copy_and_paste.maybe_transform_html(paste_html, paste_text), expected_output);

    // Untransformed HTML
    paste_html = "<div><div>Hello</div><div>World!</div></div>";
    paste_text = "Hello\nWorld!";
    assert.equal(copy_and_paste.maybe_transform_html(paste_html, paste_text), paste_html);
});

run_test("paste_handler_converter", () => {
    /*
        Pasting from another Zulip message
    */

    // Bold text
    let input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: hsl(0, 0%, 13%); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;"><span> </span>love the<span> </span><b>Zulip</b><b> </b></span><b style="color: hsl(0, 0%, 13%); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;">Organization</b><span style="color: hsl(0, 0%, 13%); font-family: arial, sans-serif; font-size: 12.8px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;">.</span>';
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        " love the **Zulip** **Organization**.",
    );

    // Inline code
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: hsl(210, 12%, 16%); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;">The<span> </span></span><code style="box-sizing: border-box; font-family: SFMono-Regular, Consolas, &quot;Liberation Mono&quot;, Menlo, Courier, monospace; font-size: 13.6px; padding: 0.2em 0.4em; margin: 0px; background-color: hsla(210, 13%, 12%, 0.05); border-radius: 3px; color: hsl(210, 12%, 16%); font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial;">JSDOM</code><span style="color: hsl(210, 12%, 16%); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;"><span> </span>constructor</span>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "The `JSDOM` constructor");

    // A python code block
    input = `<meta http-equiv="content-type" content="text/html; charset=utf-8"><p>zulip code block in python</p><div class="codehilite zulip-code-block" data-code-language="Python"><pre><span></span><code><span class="nb">print</span><span class="p">(</span><span class="s2">"hello"</span><span class="p">)</span>\n<span class="nb">print</span><span class="p">(</span><span class="s2">"world"</span><span class="p">)</span></code></pre></div></meta>`;
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        'zulip code block in python\n\n```Python\nprint("hello")\nprint("world")\n```',
    );

    // Single line in a code block
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><pre><code>single line</code></pre>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "`single line`");

    // Raw links without custom text
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><a href="https://zulip.readthedocs.io/en/latest/subsystems/logging.html" target="_blank" title="https://zulip.readthedocs.io/en/latest/subsystems/logging.html" style="color: hsl(200, 100%, 40%); text-decoration: none; cursor: pointer; font-family: &quot;Source Sans 3&quot;, &quot;Helvetica Neue&quot;, Helvetica, Arial, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%);">https://zulip.readthedocs.io/en/latest/subsystems/logging.html</a>';
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        "https://zulip.readthedocs.io/en/latest/subsystems/logging.html",
    );

    // Links with custom text
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><a class="reference external" href="https://zulip.readthedocs.io/en/latest/contributing/contributing.html" style="box-sizing: border-box; color: hsl(283, 39%, 53%); text-decoration: none; cursor: pointer; outline: 0px; font-family: Lato, proxima-nova, &quot;Helvetica Neue&quot;, Arial, sans-serif; font-size: 16px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 99%);">Contributing guide</a>';
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        "[Contributing guide](https://zulip.readthedocs.io/en/latest/contributing/contributing.html)",
    );

    // Only numbered list (list style retained)
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><ol><li>text</li></ol>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "1. text");

    // Heading
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><h1 style="box-sizing: border-box; font-size: 2em; margin-top: 0px !important; margin-right: 0px; margin-bottom: 16px; margin-left: 0px; font-weight: 600; line-height: 1.25; padding-bottom: 0.3em; border-bottom: 1px solid hsl(216, 14%, 93%); color: hsl(210, 12%, 16%); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial;">Zulip overview</h1><p>normal text</p>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "# Zulip overview\n\nnormal text");
    // Only heading (strip heading style)
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><h1 style="box-sizing: border-box; font-size: 2em; margin-top: 0px !important; margin-right: 0px; margin-bottom: 16px; margin-left: 0px; font-weight: 600; line-height: 1.25; padding-bottom: 0.3em; border-bottom: 1px solid hsl(216, 14%, 93%); color: hsl(210, 12%, 16%); font-family: -apple-system, BlinkMacSystemFont, &quot;Segoe UI&quot;, Helvetica, Arial, sans-serif, &quot;Apple Color Emoji&quot;, &quot;Segoe UI Emoji&quot;, &quot;Segoe UI Symbol&quot;; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-style: initial; text-decoration-color: initial;">Zulip overview</h1>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "Zulip overview");

    // Italic text
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8">normal text <i style="box-sizing: inherit; color: hsl(0, 0%, 0%); font-family: Verdana, sans-serif; font-size: 15px; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;">This text is italic</i>';
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        "normal text *This text is italic*",
    );

    // Strikethrough text
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8">normal text <del style="box-sizing: inherit; color: hsl(0, 0%, 0%); font-family: Verdana, sans-serif; font-size: 15px; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: hsl(0, 0%, 100%); text-decoration-style: initial; text-decoration-color: initial;">This text is struck through</del>';
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        "normal text ~~This text is struck through~~",
    );

    // Emojis
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;">emojis:<span> </span></span><span aria-label="smile" class="emoji emoji-1f642" role="img" title="smile" style="height: 20px; width: 20px; position: relative; margin-top: -7px; vertical-align: middle; top: 3px; background-position: 55% 46.667%; display: inline-block; background-image: url(&quot;http://localhost:9991/webpack/files/generated/emoji/google.webp&quot;); background-size: 6100%; background-repeat: no-repeat; text-indent: 100%; white-space: nowrap; overflow: hidden; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">:smile:</span><span style="color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;"><span> </span></span><span aria-label="family man woman girl" class="emoji emoji-1f468-200d-1f469-200d-1f467" role="img" title="family man woman girl" style="height: 20px; width: 20px; position: relative; margin-top: -7px; vertical-align: middle; top: 3px; background-position: 23.333% 75%; display: inline-block; background-image: url(&quot;http://localhost:9991/webpack/files/generated/emoji/google.webp&quot;); background-size: 6100%; background-repeat: no-repeat; text-indent: 100%; white-space: nowrap; overflow: hidden; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">:family_man_woman_girl:</span>';
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        "emojis: :smile: :family_man_woman_girl:",
    );

    // Nested lists
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><ul style="padding: 0px; margin: 0px 0px 5px 20px; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"><li style="line-height: inherit;">bulleted</li><li style="line-height: inherit;">nested<ul style="padding: 0px; margin: 2px 0px 5px 20px;"><li style="line-height: inherit;">nested level 1</li><li style="line-height: inherit;">nested level 1 continue<ul style="padding: 0px; margin: 2px 0px 5px 20px;"><li style="line-height: inherit;">nested level 2</li><li style="line-height: inherit;">nested level 2 continue</li></ul></li></ul></li></ul>';
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        "* bulleted\n* nested\n  * nested level 1\n  * nested level 1 continue\n    * nested level 2\n    * nested level 2 continue",
    );

    // 2 paragraphs with line break/s in between
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><p>paragraph 1</p><br><p>paragraph 2</p>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "paragraph 1\n\nparagraph 2");

    // Pasting from external sources
    // Pasting list from GitHub
    input =
        '<div class="preview-content"><div class="comment"><div class="comment-body markdown-body js-preview-body" style="min-height: 131px;"><p>Test list:</p><ul><li>Item 1</li><li>Item 2</li></ul></div></div></div>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "Test list:\n* Item 1\n* Item 2");

    // Pasting list from VS Code
    input =
        '<div class="ace-line gutter-author-d-iz88z86z86za0dz67zz78zz78zz74zz68zjz80zz71z9iz90za3z66zs0z65zz65zq8z75zlaz81zcz66zj6g2mz78zz76zmz66z22z75zfcz69zz66z ace-ltr focused-line" dir="auto" id="editor-3-ace-line-41"><span>Test list:</span></div><div class="ace-line gutter-author-d-iz88z86z86za0dz67zz78zz78zz74zz68zjz80zz71z9iz90za3z66zs0z65zz65zq8z75zlaz81zcz66zj6g2mz78zz76zmz66z22z75zfcz69zz66z line-list-type-bullet ace-ltr" dir="auto" id="editor-3-ace-line-42"><ul class="listtype-bullet listindent1 list-bullet1"><li><span class="ace-line-pocket-zws" data-faketext="" data-contentcollector-ignore-space-at="end"></span><span class="ace-line-pocket" data-faketext="" contenteditable="false"></span><span class="ace-line-pocket-zws" data-faketext="" data-contentcollector-ignore-space-at="start"></span><span>Item 1</span></li></ul></div><div class="ace-line gutter-author-d-iz88z86z86za0dz67zz78zz78zz74zz68zjz80zz71z9iz90za3z66zs0z65zz65zq8z75zlaz81zcz66zj6g2mz78zz76zmz66z22z75zfcz69zz66z line-list-type-bullet ace-ltr" dir="auto" id="editor-3-ace-line-43"><ul class="listtype-bullet listindent1 list-bullet1"><li><span class="ace-line-pocket-zws" data-faketext="" data-contentcollector-ignore-space-at="end"></span><span class="ace-line-pocket" data-faketext="" contenteditable="false"></span><span class="ace-line-pocket-zws" data-faketext="" data-contentcollector-ignore-space-at="start"></span><span>Item 2</span></li></ul></div>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "Test list:\n* Item 1\n* Item 2");

    // Pasting from Google Sheets (remove <style> elements completely)
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><style type="text/css"><!--td {border: 1px solid #cccccc;}br {mso-data-placement:same-cell;}--></style><span style="font-size:10pt;font-family:Arial;font-style:normal;text-align:right;" data-sheets-value="{&quot;1&quot;:3,&quot;3&quot;:123}" data-sheets-userformat="{&quot;2&quot;:769,&quot;3&quot;:{&quot;1&quot;:0},&quot;11&quot;:3,&quot;12&quot;:0}">123</span>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "123");
});
