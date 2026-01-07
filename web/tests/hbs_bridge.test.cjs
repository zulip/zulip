"use strict";

const assert = require("node:assert/strict");

const {JSDOM} = require("jsdom");

const {trim_and_dedent} = require("./lib/dedent.cjs");
const {set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const dom = new JSDOM(`<!DOCTYPE html>`);
set_global("document", dom.window.document);
// global.Node = dom.window.Node;

const hbs = zrequire("hbs_bridge");
const h = zrequire("html");

function assert_dom_is_empty(dom) {
    // We get a DocumentFragment, and in node.js we don't have easy access to types.
    // so we just assert no children
    assert.ok(dom.childNodes.length === 0);
}

function only_child_element_of(dom) {
    assert.equal(dom.children.length, 1);
    return dom.children[0];
}

run_test("trusted_if_else_string", () => {
    function test(b, expected_val) {
        const spec = h.trusted_if_else_string({
            bool: h.bool_var({
                label: "some_bool",
                b,
            }),
            yes_val: h.trusted_simple_string("yes"),
            no_val: h.trusted_simple_string("no"),
        });
        assert.equal(spec.render_val(), expected_val);
        assert.equal(spec.to_source(), `{{#if some_bool}}yes{{else}}no{{/if}}`);
    }
    test(true, "yes");
    test(false, "no");
});

run_test("test IfBlock", () => {
    let frag = hbs.if_bool_then_block({
        bool: h.bool_var({label: "condition", b: true}),
        block: h.block({elements: [h.div_tag({})]}),
    });
    assert.equal(only_child_element_of(frag.to_dom()).tagName, "DIV");

    frag = hbs.if_bool_then_block({
        bool: h.bool_var({label: "condition", b: false}),
        block: h.block({elements: [h.div_tag({})]}),
    });
    const dom = frag.to_dom();
    assert_dom_is_empty(dom);

    frag = hbs.if_bool_then_block({
        source_format: "block",
        bool: h.bool_var({label: "condition", b: true}),
        block: h.block({elements: [h.div_tag({})]}),
    });
    assert.equal(
        trim_and_dedent(`
            {{#if condition}}
                <div></div>
            {{/if}}
            `),
        frag.to_source(""),
    );
});

run_test("test UnlessBlock", () => {
    let frag = hbs.unless_bool_then_block({
        bool: h.bool_var({label: "condition", b: false}),
        block: h.block({elements: [h.div_tag({})]}),
    });
    assert.equal(only_child_element_of(frag.to_dom()).tagName, "DIV");

    frag = hbs.unless_bool_then_block({
        bool: h.bool_var({label: "condition", b: true}),
        block: h.block({elements: [h.div_tag({})]}),
    });
    const dom = frag.to_dom();
    assert_dom_is_empty(dom);

    frag = hbs.unless_bool_then_block({
        source_format: "block",
        bool: h.bool_var({label: "condition", b: false}),
        block: h.block({elements: [h.div_tag({})]}),
    });
    assert.equal(
        trim_and_dedent(`
            {{#unless condition}}
                <div></div>
            {{/unless}}
            `),
        frag.to_source(""),
    );
});

run_test("test IfElseIfElseBlock", () => {
    function get_if_else_if_else_block(if_boolean, else_if_boolean) {
        const if_spec = {
            bool: h.bool_var({label: "if_condition", b: if_boolean}),
            block: h.block({
                elements: [
                    h.div_tag({
                        source_format: "block",
                        children: [
                            h.text_var({
                                label: "if_block_text",
                                s: h.unescaped_text_string("if_block_text"),
                            }),
                        ],
                    }),
                ],
            }),
        };
        const else_if_spec = {
            bool: h.bool_var({label: "else_if_condition", b: else_if_boolean}),
            block: h.block({
                elements: [
                    h.div_tag({
                        source_format: "block",
                        children: [
                            h.text_var({
                                label: "else_if_block_text",
                                s: h.unescaped_text_string("else_if_block_text"),
                            }),
                        ],
                    }),
                ],
            }),
        };
        const else_block = h.block({
            elements: [
                h.div_tag({
                    source_format: "block",
                    children: [
                        h.text_var({
                            label: "else_block_text",
                            s: h.unescaped_text_string("else_block_text"),
                        }),
                    ],
                }),
            ],
        });
        return hbs.if_bool_then_x_else_if_bool_then_y_else_z({
            if_info: if_spec,
            else_if_info: else_if_spec,
            else_block,
        });
    }

    const if_true_block = get_if_else_if_else_block(true, true);
    assert.equal(
        trim_and_dedent(`
    {{#if if_condition}}
        <div>
            {{if_block_text}}
        </div>
    {{else if else_if_condition}}
        <div>
            {{else_if_block_text}}
        </div>
    {{else}}
        <div>
            {{else_block_text}}
        </div>
    {{/if}}
        `),
        if_true_block.to_source(""),
    );

    let frag = if_true_block.to_dom();
    assert.equal(only_child_element_of(frag).textContent, "if_block_text");

    const else_if_true_block = get_if_else_if_else_block(false, true);
    frag = else_if_true_block.to_dom();
    assert.equal(only_child_element_of(frag).textContent, "else_if_block_text");

    const else_block = get_if_else_if_else_block(false, false);
    frag = else_block.to_dom();
    assert.equal(only_child_element_of(frag).textContent, "else_block_text");
});
