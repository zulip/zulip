"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {window} = new JSDOM();
set_global("Node", window.Node);
set_global("Element", window.Element);

const copy_messages = zrequire("copy_messages");

function get_plain_text(copy_div_html) {
    const copy_div = window.document.createElement("div");
    copy_div.innerHTML = copy_div_html;
    return copy_messages.get_plain_text_for_copy_div(copy_div);
}

run_test("messages from one recipient", () => {
    const copy_div_html =
        '<b>Desdemona: </b><div>See the <a href="https://zulip.com/help">docs</a>.</div>' +
        '<p></p><b>Desdemona: </b><div>Hello <span class="user-mention silent" data-user-id="8">Cordelia</span></div>\n' +
        "<p>Second paragraph</p>";
    assert.equal(
        get_plain_text(copy_div_html),
        "Desdemona:\nSee the docs.\n\nDesdemona:\nHello Cordelia\n\nSecond paragraph",
    );
});

run_test("messages from several recipients", () => {
    const copy_div_html =
        '<p data-message-header-paragraph="true"><strong>Verona &gt; copy-paste-topic #1</strong><span> | Today</span></p>' +
        "<b>Desdemona: </b><div>copy paste test B</div>" +
        '<p data-message-header-paragraph="true"><strong>Verona &gt; copy-paste-topic #2</strong><span> | Today</span></p>' +
        "<b>Desdemona: </b><div>copy paste test C</div>";
    assert.equal(
        get_plain_text(copy_div_html),
        "Verona > copy-paste-topic #1 | Today\n" +
            "Desdemona:\ncopy paste test B\n\n" +
            "Verona > copy-paste-topic #2 | Today\n" +
            "Desdemona:\ncopy paste test C",
    );
});

run_test("blocks within a message", () => {
    const copy_div_html =
        "<div>line one<br>\nline two</div>\n" +
        "<ul>\n<li>item one</li>\n<li>item two</li>\n</ul>\n" +
        "<blockquote>\n<p>quoted</p>\n</blockquote>\n" +
        "<h1>Heading</h1>\n" +
        "<p>After the heading</p>";
    assert.equal(
        get_plain_text(copy_div_html),
        "line one\nline two\nitem one\nitem two\n\nquoted\n\nHeading\n\nAfter the heading",
    );
});

run_test("whitespace", () => {
    const copy_div_html =
        "<p>collapsed   spaces\nand <code>inline  code</code> and " +
        '<a class="stream-topic" href="#narrow/channel/9-two-spaces">' +
        '<span class="decorated-channel-name-wrapper inline-decorated-channel-name">' +
        '<span class="channel-privacy-type-icon"><i class="zulip-icon zulip-icon-hashtag"></i></span>' +
        '<span class="decorated-channel-name">two  spaces</span></span></a></p>';
    assert.equal(
        get_plain_text(copy_div_html),
        "collapsed spaces and inline  code and two  spaces",
    );
});

run_test("code blocks", () => {
    // The code buttons are added to the `<pre>` of a rendered message,
    // so they appear in a partially selected message.
    const copy_div_html =
        "<p>Hamlet once said</p>\n" +
        '<div class="codehilite" data-code-language="Python"><pre>' +
        '<div class="code-buttons-container">\n' +
        '    <span class="copy_codeblock copy-button copy-button-square" role="button">\n' +
        '        <i class="zulip-icon zulip-icon-copy" aria-hidden="true"></i>\n' +
        "    </span></div>" +
        '<span></span><code><span class="k">def</span> <span class="nf">func</span><span class="p">():</span>\n' +
        '    <span class="n">x</span> <span class="o">=</span> <span class="mi">1</span>\n' +
        "\n" +
        '    <span class="n">y</span> <span class="o">=</span> <span class="mi">2</span>\n' +
        "</code></pre></div>\n" +
        "<p>And all was good.</p>";
    assert.equal(
        get_plain_text(copy_div_html),
        "Hamlet once said\n\ndef func():\n    x = 1\n\n    y = 2\n\nAnd all was good.",
    );
});

run_test("tables", () => {
    const copy_div_html =
        "<table>\n<thead>\n<tr>\n<th>Name</th>\n<th>Role</th>\n</tr>\n</thead>\n" +
        "<tbody>\n<tr>\n<td>Desdemona</td>\n<td>Owner</td>\n</tr>\n</tbody>\n</table>";
    assert.equal(get_plain_text(copy_div_html), "Name\tRole\nDesdemona\tOwner");
});
