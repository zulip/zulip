"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const {page_params} = require("./lib/zpage_params");

const copy_and_paste = zrequire("copy_and_paste");

run_test("paste_handler_converter", () => {
    page_params.development_environment = true;

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
    input = `<meta http-equiv="content-type" content="text/html; charset=utf-8"><p style="margin: 3px 0px; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">zulip code block in python</p><div class="codehilite zulip-code-block" data-code-language="Python" style="background-color: rgb(33, 45, 59); display: block !important; border: none !important; background-image: none !important; background-position: initial !important; background-size: initial !important; background-repeat: initial !important; background-attachment: initial !important; background-origin: initial !important; background-clip: initial !important; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;"><pre style="padding: 5px 7px 3px; font-family: &quot;Source Code Pro&quot;, monospace; font-size: 0.825em; color: rgb(163, 206, 255); border-radius: 4px; display: block; margin: 5px 0px; line-height: 1.4; word-break: break-all; overflow-wrap: normal; white-space: pre; background-color: rgb(29, 38, 48); border: 1px solid rgba(0, 0, 0, 0.15); direction: ltr; overflow-x: auto;"><span></span><code style="font-family: &quot;Source Code Pro&quot;, monospace; font-size: inherit; unicode-bidi: embed; direction: ltr; color: rgb(163, 206, 255); white-space: inherit; padding: 0px; background-color: rgb(29, 38, 48); border: 0px rgba(0, 0, 0, 0.5); border-radius: 3px; overflow-x: scroll;"><span class="nb" style="color: rgb(239, 239, 143);">print</span><span class="p" style="color: rgb(65, 113, 113);">(</span><span class="s2" style="color: rgb(204, 147, 147);">"hello world"</span><span class="p" style="color: rgb(65, 113, 113);">)</span></code></pre></div></meta>`;
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        'zulip code block in python\n\n```Python\nprint("hello world")\n```',
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
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><span style="color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;">emojis:<span> </span></span><span aria-label="smile" class="emoji emoji-1f642" role="img" title="smile" style="height: 20px; width: 20px; position: relative; margin-top: -7px; vertical-align: middle; top: 3px; background-position: 55% 46.667%; display: inline-block; background-image: url(&quot;http://localhost:9991/webpack/files/srv/zulip-npm-cache/287cb53c1a095fe79651f095d5d8d60f7060baa7/node_modules/emoji-datasource-google/img/google/sheets-256/64.png&quot;); background-size: 6100%; background-repeat: no-repeat; text-indent: 100%; white-space: nowrap; overflow: hidden; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">:smile:</span><span style="color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-indent: 0px; text-transform: none; white-space: normal; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial; display: inline !important; float: none;"><span> </span></span><span aria-label="family man woman girl" class="emoji emoji-1f468-200d-1f469-200d-1f467" role="img" title="family man woman girl" style="height: 20px; width: 20px; position: relative; margin-top: -7px; vertical-align: middle; top: 3px; background-position: 23.333% 75%; display: inline-block; background-image: url(&quot;http://localhost:9991/webpack/files/srv/zulip-npm-cache/287cb53c1a095fe79651f095d5d8d60f7060baa7/node_modules/emoji-datasource-google/img/google/sheets-256/64.png&quot;); background-size: 6100%; background-repeat: no-repeat; text-indent: 100%; white-space: nowrap; overflow: hidden; color: rgb(221, 222, 238); font-family: &quot;Source Sans 3&quot;, sans-serif; font-size: 14px; font-style: normal; font-variant-ligatures: normal; font-variant-caps: normal; font-weight: 400; letter-spacing: normal; orphans: 2; text-align: start; text-transform: none; widows: 2; word-spacing: 0px; -webkit-text-stroke-width: 0px; background-color: rgb(33, 45, 59); text-decoration-thickness: initial; text-decoration-style: initial; text-decoration-color: initial;">:family_man_woman_girl:</span>';
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

    // Pasting code from VS Code / Gmail
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><div style="color: #ffffff;background-color: #002451;font-family: Consolas, &quot;Courier New&quot;, monospace;font-weight: normal;font-size: 14px;line-height: 19px;white-space: pre;"><div><span style="color: #ebbbff;">const</span><span style="color: #ffffff;"> </span><span style="color: #ff9da4;">compose_ui</span><span style="color: #ffffff;"> </span><span style="color: #99ffff;">=</span><span style="color: #ffffff;"> </span><span style="color: #bbdaff;">mock_esm</span><span style="color: #ffffff;">(</span><span style="color: #d1f1a9;">"../src/compose_ui"</span><span style="color: #ffffff;">);</span></div><div><span style="color: #bbdaff;">set_global</span><span style="color: #ffffff;">(</span><span style="color: #d1f1a9;">"document"</span><span style="color: #ffffff;">, </span><span style="color: #ff9da4;">document</span><span style="color: #ffffff;">);</span></div></div>';
    assert.equal(
        copy_and_paste.paste_handler_converter(input),
        'const compose_ui = mock_esm("../src/compose_ui");\n\nset_global("document", document);',
    );

    // Pasting from Google Sheets (remove <style> elements completely)
    input =
        '<meta http-equiv="content-type" content="text/html; charset=utf-8"><style type="text/css"><!--td {border: 1px solid #cccccc;}br {mso-data-placement:same-cell;}--></style><span style="font-size:10pt;font-family:Arial;font-style:normal;text-align:right;" data-sheets-value="{&quot;1&quot;:3,&quot;3&quot;:123}" data-sheets-userformat="{&quot;2&quot;:769,&quot;3&quot;:{&quot;1&quot;:0},&quot;11&quot;:3,&quot;12&quot;:0}">123</span>';
    assert.equal(copy_and_paste.paste_handler_converter(input), "123");
});
