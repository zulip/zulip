"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const {trim_and_dedent} = require("./lib/dedent.cjs");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const dom = new JSDOM(`<!DOCTYPE html>`);
global.document = dom.window.document;
global.Node = dom.window.Node;
const html = zrequire("html");

run_test("sanity check on trim_and_dedent", () => {
    assert.equal(trim_and_dedent(""), "");
    assert.equal(trim_and_dedent("\n\n\n  foo\n\n\n\n"), "foo");
    assert.equal(trim_and_dedent("\n  foo\n\n  bar\n"), "foo\n\nbar");
    assert.equal(trim_and_dedent("\n  foo\nbar\n"), "foo\nINDENT ERROR: bar");
});

run_test("test TrustedSimpleString", () => {
    assert.equal(html.trusted_simple_string("hello").to_source(), "hello");
});

run_test("test trusted_html", () => {
    const widget = html.trusted_html("<b>hello world</b>");
    assert.equal(widget.to_source(""), "<b>hello world</b>");
});

function styled_span(color, text) {
    const style_key = "style"; // fool the linter
    return `<span ${style_key}="background-color: ${color};">${text}</span>`;
}

run_test("test orange sorry", () => {
    const widget = html.div_tag({
        children: [new html.SorryBlock("TBD")],
    });
    assert.equal(widget.to_source(""), "<div>TBD</div>");
    const actual_html = widget.to_dom().innerHTML;
    assert.equal(actual_html, styled_span("orange", "TBD"));
});

run_test("test pink text_var", () => {
    const widget = html.div_tag({
        children: [
            html.text_var({
                label: "whatever",
                s: html.unescaped_text_string("wonky"),
                pink: true,
            }),
        ],
    });
    const actual_html = widget.to_dom().innerHTML;
    assert.equal(actual_html, styled_span("pink", "wonky"));
});

run_test("test pink InputTextTag", () => {
    const widget = html.input_text_tag({
        placeholder_value: html.translated_attr_value({
            translated_string: "hi",
        }),
        classes: ["hello"],
        pink: true,
    });
    assert.equal(
        widget.to_source(""),
        `<input type="text" class="hello" placeholder="{{t 'hi'}}" />`,
    );
    const actual_html = widget.as_raw_html();
    const style = "style"; // fool the linter
    assert.equal(
        actual_html,
        `<input type="text" class="hello" placeholder="hi" ${style}="background-color: pink;">`,
    );
});

run_test("test pink translated_text", () => {
    const widget = html.div_tag({
        children: [
            html.translated_text({
                translated_text: "hello",
                pink: true,
            }),
        ],
    });
    assert.equal(widget.to_source(""), `<div>{{t "hello" }}</div>`);
    const actual_html = widget.to_dom().innerHTML;
    assert.equal(actual_html, styled_span("pink", "hello"));
});

run_test("test blocks ignore comments", () => {
    const block = html.block({
        elements: [html.comment("Ignore this")],
    });
    assert.equal(block.to_source(""), `{{!-- Ignore this --}}\n`);
    assert.equal(block.as_raw_html(), "");
});
