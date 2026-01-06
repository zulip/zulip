"use strict";

const assert = require("node:assert/strict");
const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const html = zrequire("html");

run_test("Fix missing coverage for html.ts", () => {
    // Helper to create a proper text element object (satisfies .to_source requirement)
    const mock_text = (val) => html.text_var({
        label: "text", 
        s: html.unescaped_text_string(val)
    });

    // 1. Hits Lines 502 & 522: Multi-element Block loops
    const multi_block = html.block({
        elements: [
            html.div_tag({children: [mock_text("1")]}),
            html.div_tag({children: [mock_text("2")]}),
        ],
    });
    
    // Forces the to_source() loop (Line 502+) 
    // Checking for "\n" confirms line 508 was hit.
    const source = multi_block.to_source("");
    assert.equal(source, "<div>1</div>\n<div>2</div>\n");
    
    // Forces the to_dom() loop (Line 522+)
    const frag = multi_block.to_dom();
    assert.equal(frag.childNodes.length, 2);

    // 2. Hits Line 690: Conditional Attribute Skip
    // We pass an empty string for "data-empty" to force the 'if (render_val)' branch to false.
    const active_attr = html.attr("data-active", html.trusted_simple_string("true"));
    const empty_attr = html.attr("data-empty", html.trusted_simple_string(""));

    const tagged_element = html.div_tag({
        attrs: [active_attr, empty_attr],
    });

    const dom_element = tagged_element.to_dom();
    assert.equal(dom_element.getAttribute("data-active"), "true");
    // SUCCESS: If this is false, we proved line 690 skipped the empty attribute.
    assert.equal(dom_element.hasAttribute("data-empty"), false);

    // 3. Hits Lines 708-712: ParenthesizedTag
    // This logic wraps a tag in literal parentheses in the DOM.
    const inner = html.span_tag({children: [mock_text("test")]});
    const paren_tag = html.parenthesized_tag(inner);
    
    // Test to_source (704-706)
    assert.equal(paren_tag.to_source(""), "(<span>test</span>)");
    
    // Test to_dom (708-712)
    const paren_dom = paren_tag.to_dom();
    assert.equal(paren_dom.tagName, "DIV");
    assert.equal(paren_dom.innerHTML, "(<span>test</span>)");
});